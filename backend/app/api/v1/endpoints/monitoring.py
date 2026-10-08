"""
Grafana inside the admin console, without a second login.

1. The admin console calls POST /admin/monitoring/session with the normal bearer token.
   We set a short-lived, HttpOnly cookie scoped to /grafana.
2. Every request to /grafana/* goes through Caddy's forward_auth, which calls
   GET /admin/monitoring/verify with that cookie. We re-check the account on each
   call (still an admin? still active?) and answer with X-WEBAUTH-* headers.
3. Grafana runs in auth-proxy mode and trusts those headers. It is never exposed
   directly, only through Caddy, and Caddy strips any X-WEBAUTH-* header a browser sends.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response, status
import jwt
from jwt import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from .... import crud
from ....core.config import settings
from ....database import Doc, get_db
from .auth import get_current_admin_user

router = APIRouter()

COOKIE = "calaro_mon"
SCOPE = "grafana"
DASHBOARDS = {
    "overview": "/grafana/d/calaro-overview/calaro-overview",
    "logs": "/grafana/d/calaro-logs/calaro-logs",
    "server": "/grafana/d/calaro-server/calaro-server",
}


def _is_https(request: Request) -> bool:
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


@router.post("/session", summary="Start a monitoring session (sets the Grafana cookie)")
async def start_session(request: Request, response: Response, admin: Doc = Depends(get_current_admin_user)):
    hours = settings.MONITORING_SESSION_HOURS
    token = jwt.encode(
        {"sub": admin.email, "scope": SCOPE, "exp": datetime.now(timezone.utc) + timedelta(hours=hours)},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )
    response.set_cookie(
        COOKIE, token, max_age=hours * 3600, path="/grafana", httponly=True,
        secure=_is_https(request), samesite="strict",
    )
    return {"dashboards": DASHBOARDS, "expires_in_hours": hours}


@router.post("/logout", status_code=204, summary="End the monitoring session")
async def end_session(response: Response):
    response.delete_cookie(COOKIE, path="/grafana")


@router.get("/verify", include_in_schema=False)
async def verify(request: Request, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Called by Caddy forward_auth for every /grafana request. 2xx = allow."""
    token = request.cookies.get(COOKIE)
    denied = Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Sign in to the CALARO admin console first.")
    if not token:
        return denied
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return denied
    if payload.get("scope") != SCOPE:
        return denied
    user = await crud.get_user_by_email(db, payload.get("sub") or "")
    if not user or not user.get("is_active", True) or user.get("role") not in (crud.ROLE_ADMIN, crud.ROLE_SUPER):
        return Response(status_code=status.HTTP_403_FORBIDDEN, content="Admins only.")
    super_ = user.get("role") == crud.ROLE_SUPER and crud.is_superadmin_email(user.email)
    return Response(status_code=200, headers={
        "X-Webauth-User": user.email,
        "X-Webauth-Name": (user.get("full_name") or user.email).encode("ascii", "ignore").decode() or user.email,
        "X-Webauth-Role": "Admin" if super_ else "Viewer",
    })
