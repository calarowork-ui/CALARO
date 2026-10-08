"""MongoDB access (Motor, async).

Collections
  users            one document per account; role is user | admin | superadmin
  food_logs        one document per saved meal
  password_resets  OTPs, auto-expired by a TTL index
  audit_log        admin/team changes made by the super-admin and admins
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from .core.config import settings

_client: Optional[Any] = None


def utcnow() -> datetime:
    """Naive UTC datetime (what MongoDB/BSON stores)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def set_client(client: Any) -> None:
    """Swap the client (tests use mongomock-motor)."""
    global _client
    _client = client


def get_client() -> Any:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI, uuidRepresentation="standard")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.MONGODB_DB]


async def get_db() -> AsyncIOMotorDatabase:
    return get_database()


def oid(value: Any) -> Optional[ObjectId]:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


class Doc(dict):
    """dict with attribute access and a string `id`, so documents read like objects."""

    def __getattr__(self, key: str) -> Any:
        if key == "id":
            return str(self.get("_id")) if self.get("_id") is not None else None
        return self.get(key)


def as_doc(raw: Optional[dict]) -> Optional[Doc]:
    return Doc(raw) if raw is not None else None


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.users.create_index([("role", ASCENDING)])
    await db.food_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.food_logs.create_index([("created_at", DESCENDING)])
    await db.password_resets.create_index([("email", ASCENDING)])
    await db.password_resets.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.audit_log.create_index([("at", DESCENDING)])
    await db.login_failures.create_index([("email", ASCENDING)])
    await db.login_failures.create_index([("at", ASCENDING)], expireAfterSeconds=settings.LOGIN_LOCK_MINUTES * 60)
