"""Async data access on MongoDB."""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from . import schemas
from .core.config import settings
from .core.security import get_password_hash, verify_password
from .database import Doc, as_doc, oid, utcnow

logger = logging.getLogger(__name__)

ROLE_USER, ROLE_ADMIN, ROLE_SUPER = "user", "admin", "superadmin"
PROFILE_FIELDS = ("age", "height_cm", "weight_kg", "sex", "activity_level", "preferred_language")


def norm_email(email: str) -> str:
    return (email or "").strip().lower()


def is_superadmin_email(email: str) -> bool:
    return norm_email(email) == norm_email(settings.SUPERADMIN_EMAIL)


# ------------------------------------------------------------------ users
async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[Doc]:
    return as_doc(await db.users.find_one({"email": norm_email(email)}))


async def get_user(db: AsyncIOMotorDatabase, user_id: Any) -> Optional[Doc]:
    _id = oid(user_id)
    return as_doc(await db.users.find_one({"_id": _id})) if _id else None


async def create_user(
    db: AsyncIOMotorDatabase, user_in: schemas.UserCreate, *, role: str = ROLE_USER, created_by: Optional[str] = None
) -> Doc:
    doc: Dict[str, Any] = {
        "email": norm_email(user_in.email),
        "full_name": user_in.full_name,
        "hashed_password": get_password_hash(user_in.password),
        "role": role,
        "is_active": True,
        "created_at": utcnow(),
        "created_by": created_by,
        "last_login_at": None,
    }
    for f in PROFILE_FIELDS:
        doc[f] = getattr(user_in, f, None)
    doc["preferred_language"] = doc.get("preferred_language") or "en"
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return Doc(doc)


async def authenticate_user(db: AsyncIOMotorDatabase, email: str, password: str) -> Optional[Doc]:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": utcnow()}})
    return user


async def update_user_profile(db: AsyncIOMotorDatabase, *, user: Doc, profile_in: schemas.UserProfileUpdate) -> Doc:
    changes = {f: getattr(profile_in, f) for f in PROFILE_FIELDS if getattr(profile_in, f) is not None}
    if changes:
        await db.users.update_one({"_id": user["_id"]}, {"$set": changes})
    return await get_user(db, user["_id"])


async def update_user_password(db: AsyncIOMotorDatabase, email: str, new_password: str) -> None:
    # bumping token_version signs out every existing session for this account
    await db.users.update_one({"email": norm_email(email)},
                              {"$set": {"hashed_password": get_password_hash(new_password)}, "$inc": {"token_version": 1}})


async def set_user_active(db: AsyncIOMotorDatabase, user_id: Any, active: bool) -> Optional[Doc]:
    update: Dict[str, Any] = {"$set": {"is_active": active}}
    if not active:
        update["$inc"] = {"token_version": 1}
    res = await db.users.find_one_and_update({"_id": oid(user_id)}, update, return_document=ReturnDocument.AFTER)
    return as_doc(res)


async def set_role(db: AsyncIOMotorDatabase, user_id: Any, role: str) -> Optional[Doc]:
    res = await db.users.find_one_and_update(
        {"_id": oid(user_id)}, {"$set": {"role": role}, "$inc": {"token_version": 1}}, return_document=ReturnDocument.AFTER
    )
    return as_doc(res)


async def list_users(db: AsyncIOMotorDatabase, *, q: str = "", role: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Doc]:
    filt: Dict[str, Any] = {}
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        filt["$or"] = [{"email": rx}, {"full_name": rx}]
    if role:
        filt["role"] = role if not isinstance(role, list) else {"$in": role}
    cursor = db.users.find(filt).sort("created_at", DESCENDING).skip(skip).limit(limit)
    return [Doc(u) async for u in cursor]


async def count_users(db: AsyncIOMotorDatabase, filt: Optional[dict] = None) -> int:
    return await db.users.count_documents(filt or {})


async def ensure_superadmin(db: AsyncIOMotorDatabase) -> None:
    """Guarantee exactly one super-admin: settings.SUPERADMIN_EMAIL."""
    email = norm_email(settings.SUPERADMIN_EMAIL)
    # Nobody else may hold the super-admin role.
    demoted = await db.users.update_many({"role": ROLE_SUPER, "email": {"$ne": email}}, {"$set": {"role": ROLE_ADMIN}})
    if demoted.modified_count:
        logger.warning("Demoted %s unexpected super-admin account(s) to admin", demoted.modified_count)

    existing = await db.users.find_one({"email": email})
    if existing:
        await db.users.update_one({"_id": existing["_id"]}, {"$set": {"role": ROLE_SUPER, "is_active": True}})
        return

    password = settings.SUPERADMIN_PASSWORD
    generated = False
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True
    try:
        await create_user(
            db,
            schemas.UserCreate(email=email, password=password, full_name="CALARO Super Admin"),
            role=ROLE_SUPER,
            created_by="system",
        )
    except DuplicateKeyError:
        return
    if generated:
        logger.warning(
            "\n%s\nSuper-admin %s created with a one-time password: %s\n"
            "Log in and change it, or set SUPERADMIN_PASSWORD in backend/.env before first start.\n%s",
            "=" * 64, email, password, "=" * 64,
        )
    else:
        logger.info("Super-admin %s created", email)


# ------------------------------------------------------------------ food logs
def _round(v: float) -> float:
    return round(float(v or 0), 1)


async def create_food_log(db: AsyncIOMotorDatabase, *, user_id: Any, food_log_in: schemas.FoodLogCreate) -> Doc:
    items = food_log_in.items

    def _sum(field: str) -> float:
        return _round(sum(float(getattr(i, field) or 0.0) for i in items))

    doc = {
        "user_id": oid(user_id),
        "created_at": utcnow(),
        "raw_text": food_log_in.raw_text,
        "native_text": food_log_in.native_text,
        "language": food_log_in.language,
        "items": [i.model_dump(exclude={"unit_grams", "per_gram"}, exclude_none=True) for i in items],
        "total_calories": _sum("calories"),
        "total_protein": _sum("protein"),
        "total_carbs": _sum("carbs"),
        "total_fat": _sum("fat"),
        "total_fibre": _sum("fibre"),
    }
    res = await db.food_logs.insert_one(doc)
    doc["_id"] = res.inserted_id
    return Doc(doc)


async def delete_food_log(db: AsyncIOMotorDatabase, *, user_id: Any, log_id: Any) -> bool:
    res = await db.food_logs.delete_one({"_id": oid(log_id), "user_id": oid(user_id)})
    return res.deleted_count == 1


async def get_food_logs_for_user(db: AsyncIOMotorDatabase, *, user_id: Any, skip: int = 0, limit: int = 50) -> List[Doc]:
    cursor = db.food_logs.find({"user_id": oid(user_id)}).sort("created_at", DESCENDING).skip(skip).limit(limit)
    return [Doc(d) async for d in cursor]


async def get_food_logs_since(db: AsyncIOMotorDatabase, *, user_id: Any, since: datetime) -> List[Doc]:
    cursor = db.food_logs.find({"user_id": oid(user_id), "created_at": {"$gte": since}}).sort("created_at", DESCENDING)
    return [Doc(d) async for d in cursor]


async def get_logging_streak(db: AsyncIOMotorDatabase, *, user_id: Any, tz_offset_minutes: int = 330) -> int:
    since = utcnow() - timedelta(days=400)
    offset = timedelta(minutes=tz_offset_minutes)
    days = set()
    async for d in db.food_logs.find({"user_id": oid(user_id), "created_at": {"$gte": since}}, {"created_at": 1}):
        days.add((d["created_at"] + offset).date())
    today = (utcnow() + offset).date()
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ------------------------------------------------------------------ password reset
def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


async def create_password_reset(db: AsyncIOMotorDatabase, email: str) -> str:
    otp = "".join(secrets.choice(string.digits) for _ in range(6))
    email = norm_email(email)
    await db.password_resets.update_many({"email": email, "is_used": False}, {"$set": {"is_used": True}})
    await db.password_resets.insert_one({
        "email": email, "otp_hash": _hash_otp(otp), "created_at": utcnow(),
        "expires_at": utcnow() + timedelta(minutes=15), "is_used": False, "attempts": 0,
    })
    return otp


async def verify_and_use_password_reset(db: AsyncIOMotorDatabase, email: str, otp: str) -> bool:
    email = norm_email(email)
    entry = await db.password_resets.find_one(
        {"email": email, "is_used": False, "expires_at": {"$gt": utcnow()}}, sort=[("created_at", DESCENDING)]
    )
    if not entry or entry.get("attempts", 0) >= 5:
        return False
    if not secrets.compare_digest(entry["otp_hash"], _hash_otp(otp)):
        await db.password_resets.update_one({"_id": entry["_id"]}, {"$inc": {"attempts": 1}})
        return False
    await db.password_resets.update_one({"_id": entry["_id"]}, {"$set": {"is_used": True}})
    return True


# ------------------------------------------------------------------ audit
async def audit(db: AsyncIOMotorDatabase, *, actor: Doc, action: str, target_email: Optional[str] = None, detail: str = "") -> None:
    from .core.observability import ADMIN_ACTIONS
    ADMIN_ACTIONS.labels(action).inc()
    logger.info("admin action", extra={"event": "admin_action", "action": action, "actor_id": str(actor.get("_id"))})
    await db.audit_log.insert_one({
        "at": utcnow(), "actor_email": actor.email, "action": action, "target_email": target_email, "detail": detail,
    })


async def list_audit(db: AsyncIOMotorDatabase, limit: int = 50) -> List[Doc]:
    return [Doc(d) async for d in db.audit_log.find().sort("at", DESCENDING).limit(limit)]


# ------------------------------------------------------------------ login lockout
async def login_lock_remaining(db: AsyncIOMotorDatabase, email: str, ip: str) -> Optional[int]:
    """Seconds until the account (or IP) may try again, or None if not locked."""
    window = timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
    since = utcnow() - window
    by_email = [d async for d in db.login_failures.find({"email": norm_email(email), "at": {"$gte": since}}).sort("at", 1)]
    if len(by_email) >= settings.LOGIN_MAX_FAILURES:
        return max(1, int((by_email[-settings.LOGIN_MAX_FAILURES]["at"] + window - utcnow()).total_seconds()))
    by_ip = await db.login_failures.count_documents({"ip": ip, "at": {"$gte": since}})
    if by_ip >= settings.LOGIN_MAX_FAILURES_PER_IP:
        return int(window.total_seconds())
    return None


async def record_login_failure(db: AsyncIOMotorDatabase, email: str, ip: str) -> None:
    await db.login_failures.insert_one({"email": norm_email(email), "ip": ip, "at": utcnow()})


async def clear_login_failures(db: AsyncIOMotorDatabase, email: str) -> None:
    await db.login_failures.delete_many({"email": norm_email(email)})
