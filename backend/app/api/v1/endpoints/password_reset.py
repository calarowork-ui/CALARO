import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from .... import crud, schemas
from ....core.config import settings
from ....core.observability import PASSWORD_RESETS
from ....core.ratelimit import client_ip, enforce
from ....database import get_db
from ....utils.email import send_email

logger = logging.getLogger(__name__)
router = APIRouter()

GENERIC = {"msg": "If an account exists for this email, a 6-digit code has been sent."}


@router.post("/request-otp", status_code=200)
async def request_password_reset_otp(request: schemas.PasswordResetRequest, http: Request, db: AsyncIOMotorDatabase = Depends(get_db)):
    enforce(f"reset:{request.email.lower()}", settings.RESET_REQUESTS_PER_15_MIN, 900, "reset requests for this email")
    enforce(f"reset-ip:{client_ip(http)}", settings.RESET_REQUESTS_PER_15_MIN * 4, 900, "reset requests from this network")
    PASSWORD_RESETS.labels("requested").inc()
    user = await crud.get_user_by_email(db, email=request.email)
    if not user:
        return GENERIC  # don't reveal which emails are registered
    otp = await crud.create_password_reset(db, email=request.email)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;background:#eef1ef;border-radius:12px">
      <h2 style="color:#14211c;margin:0 0 12px">CALARO</h2>
      <p style="color:#3d4a44">Use this code to reset your password. It expires in 15 minutes.</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:8px;color:#0f3d2e">{otp}</p>
      <p style="color:#6b7772;font-size:13px">If you didn't ask for this, you can ignore this email.</p>
    </div>"""
    await send_email(email_to=request.email, subject="Your CALARO reset code", html_content=html)
    return GENERIC


@router.post("/reset-password", status_code=200)
async def reset_password(confirm: schemas.PasswordResetConfirm, db: AsyncIOMotorDatabase = Depends(get_db)):
    if not await crud.verify_and_use_password_reset(db, email=confirm.email, otp=confirm.otp):
        PASSWORD_RESETS.labels("failed").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That code is wrong or has expired. Request a new one.")
    await crud.update_user_password(db, email=confirm.email, new_password=confirm.new_password)
    PASSWORD_RESETS.labels("completed").inc()
    return {"msg": "Password updated. Sign in with your new password."}
