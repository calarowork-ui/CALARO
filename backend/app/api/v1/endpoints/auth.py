from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from jwt import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from .... import crud, schemas
from ....core.config import settings
from ....core.observability import LOGINS, SIGNUPS
from ....core.ratelimit import client_ip, enforce
from ....core.security import create_access_token
from ....database import Doc, get_db

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(db: AsyncIOMotorDatabase = Depends(get_db), token: str = Depends(oauth2_scheme)) -> Doc:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session has expired. Sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    if payload.get("tv", 0) != user.get("token_version", 0):
        raise credentials_exception  # password changed, role changed or account deactivated since sign-in
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")
    return user


async def get_current_admin_user(current_user: Doc = Depends(get_current_user)) -> Doc:
    if current_user.get("role") not in (crud.ROLE_ADMIN, crud.ROLE_SUPER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only.")
    return current_user


async def get_current_superadmin(current_user: Doc = Depends(get_current_user)) -> Doc:
    if current_user.get("role") != crud.ROLE_SUPER or not crud.is_superadmin_email(current_user.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the super-admin can manage admins.")
    return current_user


def _activity_factor(level: Optional[str]) -> Optional[float]:
    return {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}.get(level or "")


def calculate_tdee_for_user(user) -> Optional[float]:
    if not all([user.age, user.height_cm, user.weight_kg, user.sex]):
        return None
    sex = (user.sex or "").lower()
    if sex not in {"male", "female"}:
        return None
    bmr = 10 * user.weight_kg + 6.25 * user.height_cm - 5 * user.age  # Mifflin-St Jeor
    bmr += 5 if sex == "male" else -161
    factor = _activity_factor(user.activity_level)
    return bmr * factor if factor else bmr * 1.2


def daily_goal(user) -> Optional[float]:
    """Plan calories when the person has done onboarding, otherwise plain TDEE."""
    plan = user.get("plan") if hasattr(user, "get") else None
    if plan and plan.get("targets", {}).get("calories"):
        return float(plan["targets"]["calories"])
    return calculate_tdee_for_user(user)


def _profile(user) -> schemas.UserProfile:
    tdee = daily_goal(user)
    return schemas.UserProfile(
        age=user.age, height_cm=user.height_cm, weight_kg=user.weight_kg, sex=user.sex,
        activity_level=user.activity_level, preferred_language=user.preferred_language,
        tdee=round(tdee) if tdee else None,
    )


@router.post("/register", response_model=schemas.UserRead, status_code=201)
async def register_user(user_in: schemas.UserCreate, request: Request, db: AsyncIOMotorDatabase = Depends(get_db)):
    enforce(f"register:{client_ip(request)}", settings.REGISTER_PER_HOUR_PER_IP, 3600, "sign-ups from this network")
    if crud.is_superadmin_email(user_in.email):
        raise HTTPException(status_code=400, detail="This email is reserved.")
    if await crud.get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists. Sign in instead.")
    try:
        user = await crud.create_user(db, user_in=user_in)  # always a normal user
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Sign in instead.")
    SIGNUPS.inc()
    return schemas.user_out(user)


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(request: Request, db: AsyncIOMotorDatabase = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    ip = client_ip(request)
    locked = await crud.login_lock_remaining(db, form_data.username, ip) if settings.RATE_LIMIT_ENABLED else None
    if locked:
        LOGINS.labels("locked").inc()
        minutes = max(1, round(locked / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many wrong passwords. For your safety, sign-in is paused for {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(locked)},
        )
    user = await crud.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        await crud.record_login_failure(db, form_data.username, ip)
        LOGINS.labels("failure").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")
    LOGINS.labels("success").inc()
    await crud.clear_login_failures(db, user.email)
    token = create_access_token(subject=user.email, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
                                token_version=user.get("token_version", 0))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserRead)
async def read_users_me(current_user: Doc = Depends(get_current_user)):
    return schemas.user_out(current_user)


@router.get("/profile", response_model=schemas.UserProfile)
async def get_profile(current_user: Doc = Depends(get_current_user)):
    return _profile(current_user)


@router.put("/profile", response_model=schemas.UserProfile)
async def update_profile(
    profile_in: schemas.UserProfileUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: Doc = Depends(get_current_user),
):
    user = await crud.update_user_profile(db, user=current_user, profile_in=profile_in)
    if user.get("onboarding"):
        # keep the plan in step with new body details
        from ....services.onboarding import OnboardingAnswers, build_plan
        merged = {**user["onboarding"], **{k: v for k, v in profile_in.model_dump().items() if v is not None}}
        try:
            answers = OnboardingAnswers(**merged)
            plan = build_plan(answers)
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"onboarding": answers.model_dump(), "plan": plan}})
            user = await crud.get_user(db, user["_id"])
        except ValueError:
            pass
    return _profile(user)
