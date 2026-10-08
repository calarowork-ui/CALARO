"""
Admin console.

  Any admin (role admin or superadmin)
    GET   /admin/overview           platform analytics
    GET   /admin/users              search users (with meal counts)
    PATCH /admin/users/{id}         activate / deactivate a normal user
    GET   /admin/logs               latest meals across all users

  Super-admin only (settings.SUPERADMIN_EMAIL, default calaro@admin.calaro.com)
    GET    /admin/admins            every admin account
    POST   /admin/admins            create a new admin, or promote an existing user
    DELETE /admin/admins/{id}       revoke admin rights (account stays as a normal user)
    GET    /admin/audit             who changed what
"""
from collections import Counter
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from .... import crud, schemas
from ....database import Doc, get_db, oid, utcnow
from .auth import get_current_admin_user, get_current_superadmin

router = APIRouter()
IST = timedelta(hours=5, minutes=30)


@router.get("/overview", response_model=schemas.AdminOverview)
async def overview(db: AsyncIOMotorDatabase = Depends(get_db), admin: Doc = Depends(get_current_admin_user)):
    now = utcnow()
    week_ago = now - timedelta(days=7)
    local_midnight = (now + IST).replace(hour=0, minute=0, second=0, microsecond=0) - IST

    total_users = await db.users.count_documents({})
    new_users = await db.users.count_documents({"created_at": {"$gte": week_ago}})
    admins = await db.users.count_documents({"role": {"$in": [crud.ROLE_ADMIN, crud.ROLE_SUPER]}})
    total_meals = await db.food_logs.count_documents({})
    meals_today = await db.food_logs.count_documents({"created_at": {"$gte": local_midnight}})

    avg = 0.0
    async for row in db.food_logs.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$total_calories"}}}]):
        avg = float(row.get("avg") or 0)

    since = now - timedelta(days=13)
    since = (since + IST).replace(hour=0, minute=0, second=0, microsecond=0) - IST
    per_day: dict = {}
    active_7d = set()
    langs: Counter = Counter()
    foods: Counter = Counter()
    async for log in db.food_logs.find(
        {"created_at": {"$gte": since}}, {"created_at": 1, "user_id": 1, "language": 1, "items.name": 1}
    ):
        day = (log["created_at"] + IST).date().isoformat()
        bucket = per_day.setdefault(day, {"meals": 0, "users": set()})
        bucket["meals"] += 1
        bucket["users"].add(log.get("user_id"))
        if log["created_at"] >= week_ago:
            active_7d.add(log.get("user_id"))
        langs[log.get("language") or "en"] += 1
        for item in log.get("items", []):
            if item.get("name"):
                foods[item["name"]] += 1

    goals: Counter = Counter()
    diets: Counter = Counter()
    conds: Counter = Counter()
    onboarded = 0
    async for u in db.users.find({"onboarding": {"$exists": True}}, {"onboarding.goal": 1, "onboarding.diet": 1, "onboarding.conditions": 1}):
        ob = u.get("onboarding") or {}
        onboarded += 1
        goals[ob.get("goal", "unknown")] += 1
        diets[ob.get("diet", "unknown")] += 1
        for c in ob.get("conditions") or []:
            conds[c] += 1

    daily = []
    for i in range(14):
        d = ((since + IST) + timedelta(days=i)).date().isoformat()
        b = per_day.get(d, {"meals": 0, "users": set()})
        daily.append(schemas.DayCount(date=d, meals=b["meals"], users=len(b["users"])))

    return schemas.AdminOverview(
        total_users=total_users,
        active_users_7d=len(active_7d),
        new_users_7d=new_users,
        total_meals=total_meals,
        meals_today=meals_today,
        avg_calories_per_meal=round(avg, 1),
        admins=admins,
        languages=[schemas.NameCount(name=k, count=v) for k, v in langs.most_common()],
        top_foods=[schemas.NameCount(name=k, count=v) for k, v in foods.most_common(8)],
        daily=daily,
        goals=[schemas.NameCount(name=k, count=v) for k, v in goals.most_common()],
        diets=[schemas.NameCount(name=k, count=v) for k, v in diets.most_common()],
        conditions=[schemas.NameCount(name=k, count=v) for k, v in conds.most_common()],
        onboarded=onboarded,
    )


@router.get("/users", response_model=List[schemas.AdminUserRow])
async def list_users(
    q: str = "",
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: Doc = Depends(get_current_admin_user),
):
    users = await crud.list_users(db, q=q, skip=skip, limit=limit)
    ids = [u["_id"] for u in users]
    counts = {}
    async for row in db.food_logs.aggregate([
        {"$match": {"user_id": {"$in": ids}}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
    ]):
        counts[row["_id"]] = row["n"]
    return [schemas.AdminUserRow(**schemas.user_out(u).model_dump(), meals=counts.get(u["_id"], 0)) for u in users]


@router.patch("/users/{user_id}", response_model=schemas.UserRead)
async def set_user_status(
    user_id: str,
    body: schemas.UserStatusUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: Doc = Depends(get_current_admin_user),
):
    target = await crud.get_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.get("role") in (crud.ROLE_ADMIN, crud.ROLE_SUPER):
        raise HTTPException(status_code=403, detail="Admin accounts are managed from the Team page by the super-admin.")
    updated = await crud.set_user_active(db, user_id, body.is_active)
    await crud.audit(db, actor=admin, action="user_activated" if body.is_active else "user_deactivated", target_email=target.email)
    return schemas.user_out(updated)


@router.get("/logs", response_model=List[schemas.FoodLogRead])
async def list_all_logs(
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: Doc = Depends(get_current_admin_user),
):
    logs = [l async for l in db.food_logs.find().sort("created_at", -1).skip(skip).limit(limit)]
    emails = {}
    user_ids = list({l["user_id"] for l in logs if l.get("user_id")})
    async for u in db.users.find({"_id": {"$in": user_ids}}, {"email": 1}):
        emails[u["_id"]] = u["email"]
    return [schemas.log_out(l, emails.get(l.get("user_id"))) for l in logs]


# ---------------------------------------------------------------- super-admin
@router.get("/admins", response_model=List[schemas.UserRead])
async def list_admins(db: AsyncIOMotorDatabase = Depends(get_db), sa: Doc = Depends(get_current_superadmin)):
    admins = await crud.list_users(db, role=[crud.ROLE_SUPER, crud.ROLE_ADMIN], limit=500)
    admins.sort(key=lambda u: (u.get("role") != crud.ROLE_SUPER, u.get("created_at") or utcnow()))
    return [schemas.user_out(u) for u in admins]


@router.post("/admins", response_model=schemas.UserRead, status_code=201)
async def create_admin(body: schemas.AdminCreate, db: AsyncIOMotorDatabase = Depends(get_db), sa: Doc = Depends(get_current_superadmin)):
    if crud.is_superadmin_email(body.email):
        raise HTTPException(status_code=400, detail="That is the super-admin account.")
    existing = await crud.get_user_by_email(db, body.email)
    if existing:
        if existing.get("role") == crud.ROLE_ADMIN:
            raise HTTPException(status_code=400, detail="This person is already an admin.")
        updated = await crud.set_role(db, existing["_id"], crud.ROLE_ADMIN)
        await crud.audit(db, actor=sa, action="admin_promoted", target_email=existing.email)
        return schemas.user_out(updated)
    if not body.password:
        raise HTTPException(status_code=400, detail="No account exists for this email yet. Set a temporary password (8+ characters).")
    user = await crud.create_user(
        db,
        schemas.UserCreate(email=body.email, password=body.password, full_name=body.full_name),
        role=crud.ROLE_ADMIN,
        created_by=sa.email,
    )
    await crud.audit(db, actor=sa, action="admin_created", target_email=user.email)
    return schemas.user_out(user)


@router.delete("/admins/{user_id}", response_model=schemas.UserRead)
async def revoke_admin(user_id: str, db: AsyncIOMotorDatabase = Depends(get_db), sa: Doc = Depends(get_current_superadmin)):
    target = await crud.get_user(db, user_id)
    if not target or target.get("role") not in (crud.ROLE_ADMIN, crud.ROLE_SUPER):
        raise HTTPException(status_code=404, detail="Admin not found.")
    if target.get("role") == crud.ROLE_SUPER:
        raise HTTPException(status_code=400, detail="The super-admin can't be removed.")
    updated = await crud.set_role(db, target["_id"], crud.ROLE_USER)
    await crud.audit(db, actor=sa, action="admin_revoked", target_email=target.email)
    return schemas.user_out(updated)


@router.get("/audit", response_model=List[schemas.AuditEntry])
async def audit_log(limit: int = Query(50, le=200), db: AsyncIOMotorDatabase = Depends(get_db), sa: Doc = Depends(get_current_superadmin)):
    return [schemas.AuditEntry(**{k: v for k, v in e.items() if k != "_id"}) for e in await crud.list_audit(db, limit)]
