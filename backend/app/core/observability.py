"""
Metrics (Prometheus) and structured logs (JSON on stdout -> Alloy -> Loki).

HTTP traffic metrics come from prometheus-fastapi-instrumentator:
  http_requests_total{handler,method,status}, http_request_duration_seconds{handler,method}
Everything below is CALARO-specific. No emails, names or meal text go into
metrics or logs; users are referred to by their database id only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from datetime import timedelta
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator.routing import get_route_name
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ------------------------------------------------------------------ metrics
SIGNUPS = Counter("calaro_signups_total", "New member accounts created")
LOGINS = Counter("calaro_logins_total", "Sign-in attempts", ["result"])
MEALS_LOGGED = Counter("calaro_meals_logged_total", "Meals saved", ["language"])
MEAL_CALORIES = Histogram("calaro_meal_calories", "Calories per saved meal",
                          buckets=(100, 200, 300, 400, 500, 650, 800, 1000, 1300, 1700, 2500))
VAANI_REQUESTS = Counter("calaro_vaani_requests_total", "Meal understanding requests", ["mode", "language", "outcome"])
VAANI_ITEMS = Histogram("calaro_vaani_items_matched", "Foods matched per request", buckets=(0, 1, 2, 3, 4, 6, 10))
BHASHINI_SECONDS = Histogram("calaro_bhashini_request_seconds", "Bhashini call latency", ["task", "mode"],
                             buckets=(0.25, 0.5, 1, 2, 3, 5, 8, 13, 20, 45))
BHASHINI_ERRORS = Counter("calaro_bhashini_errors_total", "Failed Bhashini calls", ["task", "mode"])
ONBOARDING_DONE = Counter("calaro_onboarding_completed_total", "Setup questions completed", ["goal", "diet"])
PASSWORD_RESETS = Counter("calaro_password_resets_total", "Password reset steps", ["stage"])
ADMIN_ACTIONS = Counter("calaro_admin_actions_total", "Admin and super-admin actions", ["action"])

USERS = Gauge("calaro_users", "Accounts by role", ["role"])
USERS_ONBOARDED = Gauge("calaro_users_onboarded", "Members who completed setup")
NEW_USERS = Gauge("calaro_new_users", "Accounts created in the window", ["window"])
ACTIVE_USERS = Gauge("calaro_active_users", "People who saved a meal in the window", ["window"])
MEALS_TODAY = Gauge("calaro_meals_today", "Meals saved since midnight IST")
MEALS_STORED = Gauge("calaro_meals_stored", "Meals stored in the database")
GOALS = Gauge("calaro_member_goals", "Members by onboarding goal", ["goal"])

IST = timedelta(hours=5, minutes=30)
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


async def refresh_gauges(db) -> None:
    from ..database import utcnow  # local import to avoid a cycle

    now = utcnow()
    for role in ("user", "admin", "superadmin"):
        USERS.labels(role).set(await db.users.count_documents({"role": role}))
    USERS_ONBOARDED.set(await db.users.count_documents({"onboarded_at": {"$ne": None}, "role": "user"}))
    for name, delta in WINDOWS.items():
        since = now - delta
        NEW_USERS.labels(name).set(await db.users.count_documents({"created_at": {"$gte": since}}))
        ACTIVE_USERS.labels(name).set(len(await db.food_logs.distinct("user_id", {"created_at": {"$gte": since}})))
    midnight = (now + IST).replace(hour=0, minute=0, second=0, microsecond=0) - IST
    MEALS_TODAY.set(await db.food_logs.count_documents({"created_at": {"$gte": midnight}}))
    MEALS_STORED.set(await db.food_logs.count_documents({}))
    seen = set()
    async for row in db.users.aggregate([{"$match": {"onboarding.goal": {"$exists": True}}},
                                         {"$group": {"_id": "$onboarding.goal", "n": {"$sum": 1}}}]):
        GOALS.labels(row["_id"]).set(row["n"])
        seen.add(row["_id"])
    for goal in ("lose", "maintain", "gain", "blood_sugar", "eat_better"):
        if goal not in seen:
            GOALS.labels(goal).set(0)


async def gauge_loop(get_db, interval: int = 60) -> None:
    log = logging.getLogger("calaro.metrics")
    while True:
        try:
            await refresh_gauges(get_db())
        except Exception as exc:  # keep the loop alive
            log.warning("gauge refresh failed: %s", exc)
        await asyncio.sleep(interval)


# ------------------------------------------------------------------ logging
class JsonFormatter(logging.Formatter):
    RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self.RESERVED and not k.startswith("_"):
                out[k] = v
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_logs: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our request log
    for noisy in ("httpx", "httpcore", "pymongo", "passlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


SKIP_PATHS = {"/metrics", "/health"}


class RequestLogMiddleware(BaseHTTPMiddleware):
    """One JSON line per API request: route, status, duration. No bodies, no personal data."""

    def __init__(self, app):
        super().__init__(app)
        self.log = logging.getLogger("calaro.request")

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        status: Optional[int] = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = rid
            return response
        except Exception:
            self.log.exception("unhandled error", extra={"request_id": rid, "path": request.url.path})
            raise
        finally:
            try:
                route = get_route_name(request, False) or "none"
            except Exception:
                route = "none"
            self.log.log(
                logging.WARNING if (status or 500) >= 500 else logging.INFO,
                "request",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    "route": route,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    "authed": "authorization" in request.headers,
                },
            )
