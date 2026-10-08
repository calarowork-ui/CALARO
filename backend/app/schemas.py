from datetime import datetime
from typing import Dict, List, Optional

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

LANG_CODES = {"hi", "ta", "te", "kn", "ml", "bn", "mr", "gu", "pa", "or", "as", "ur", "en"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>]")


def check_password(v: str) -> str:
    """8-128 characters with at least one letter and one number."""
    if v is None:
        return v
    if len(v) < 8 or len(v) > 128:
        raise ValueError("Password must be 8 to 128 characters.")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password needs at least one letter and one number.")
    if v.strip() != v:
        raise ValueError("Password can't start or end with a space.")
    return v


def clean_name(v):
    if v is None:
        return v
    v = " ".join(str(v).split())
    if not v:
        return None
    if len(v) > 80:
        raise ValueError("Name must be 80 characters or fewer.")
    if _CONTROL.search(v):
        raise ValueError("Name contains characters that aren't allowed.")
    return v


def check_lang(v):
    if v is None:
        return v
    if v not in LANG_CODES:
        raise ValueError("Unsupported language.")
    return v


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

    age: Optional[int] = Field(default=None, ge=0, le=120)
    height_cm: Optional[float] = Field(default=None, ge=50, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=20, le=300)
    sex: Optional[str] = Field(default=None)
    activity_level: Optional[str] = Field(default=None)
    preferred_language: Optional[str] = Field(default=None)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    _pw = field_validator("password")(classmethod(lambda cls, v: check_password(v)))
    _name = field_validator("full_name")(classmethod(lambda cls, v: clean_name(v)))
    _lang = field_validator("preferred_language")(classmethod(lambda cls, v: check_lang(v)))


class UserRead(UserBase):
    id: str
    role: str = "user"
    is_active: bool = True
    is_admin: bool = False
    is_superadmin: bool = False
    needs_onboarding: bool = False
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


def user_out(doc) -> "UserRead":
    role = doc.get("role") or "user"
    return UserRead(
        id=str(doc["_id"]),
        email=doc["email"],
        full_name=doc.get("full_name"),
        age=doc.get("age"), height_cm=doc.get("height_cm"), weight_kg=doc.get("weight_kg"),
        sex=doc.get("sex"), activity_level=doc.get("activity_level"),
        preferred_language=doc.get("preferred_language"),
        role=role,
        is_active=doc.get("is_active", True),
        is_admin=role in ("admin", "superadmin"),
        is_superadmin=role == "superadmin",
        needs_onboarding=role == "user" and not doc.get("onboarded_at"),
        created_at=doc.get("created_at"),
        last_login_at=doc.get("last_login_at"),
    )


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None


class UserProfileUpdate(BaseModel):
    age: Optional[int] = Field(default=None, ge=13, le=100)
    height_cm: Optional[float] = Field(default=None, ge=100, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=25, le=300)
    sex: Optional[str] = Field(default=None, pattern="^(female|male)$")
    activity_level: Optional[str] = Field(default=None, pattern="^(sedentary|light|moderate|active|very_active)$")
    preferred_language: Optional[str] = None

    _lang = field_validator("preferred_language")(classmethod(lambda cls, v: check_lang(v)))


class UserProfile(BaseModel):
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    sex: Optional[str] = None
    activity_level: Optional[str] = None
    preferred_language: Optional[str] = None
    tdee: Optional[float] = None


class FoodItem(BaseModel):
    name: str
    quantity: float
    unit: str
    calories: Optional[float] = None
    # Vaani / Indian food DB fields (all optional for backwards compatibility)
    food_id: Optional[str] = None
    native_name: Optional[str] = None
    grams: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fibre: Optional[float] = None
    matched: Optional[bool] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    unit_grams: Optional[Dict[str, float]] = None
    per_gram: Optional[Dict[str, float]] = None


class FoodLogBase(BaseModel):
    raw_text: str
    items: List[FoodItem]


class FoodItemIn(FoodItem):
    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=5000)
    unit: str = Field(min_length=1, max_length=20)
    calories: Optional[float] = Field(default=None, ge=0, le=10000)
    protein: Optional[float] = Field(default=None, ge=0, le=1000)
    carbs: Optional[float] = Field(default=None, ge=0, le=2000)
    fat: Optional[float] = Field(default=None, ge=0, le=1000)
    fibre: Optional[float] = Field(default=None, ge=0, le=500)
    grams: Optional[float] = Field(default=None, ge=0, le=10000)


class FoodLogCreate(BaseModel):
    raw_text: str = Field(min_length=1, max_length=1000)
    items: List[FoodItemIn] = Field(min_length=1, max_length=30)
    language: Optional[str] = None
    native_text: Optional[str] = Field(default=None, max_length=1000)

    _lang = field_validator("language")(classmethod(lambda cls, v: check_lang(v)))


class FoodLogRead(FoodLogBase):
    id: str
    created_at: datetime
    total_calories: Optional[float] = None
    total_protein: Optional[float] = None
    total_carbs: Optional[float] = None
    total_fat: Optional[float] = None
    total_fibre: Optional[float] = None
    language: Optional[str] = None
    native_text: Optional[str] = None
    user_email: Optional[str] = None


def log_out(doc, user_email: Optional[str] = None) -> "FoodLogRead":
    return FoodLogRead(
        id=str(doc["_id"]),
        created_at=doc["created_at"],
        raw_text=doc.get("raw_text") or "",
        native_text=doc.get("native_text"),
        language=doc.get("language"),
        items=[FoodItem(**i) for i in doc.get("items", [])],
        total_calories=doc.get("total_calories"),
        total_protein=doc.get("total_protein"),
        total_carbs=doc.get("total_carbs"),
        total_fat=doc.get("total_fat"),
        total_fibre=doc.get("total_fibre"),
        user_email=user_email,
    )


class VoiceParseResponse(BaseModel):
    text: str
    items: List[FoodItem]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)

    _pw = field_validator("new_password")(classmethod(lambda cls, v: check_password(v)))



# ---------------------------------------------------------------- Vaani
class LanguageOut(BaseModel):
    code: str
    name: str
    native: str


class VaaniStatus(BaseModel):
    bhashini_configured: bool
    languages: List[LanguageOut]
    food_count: int


class VaaniVoiceRequest(BaseModel):
    audio_b64: str = Field(description="16 kHz mono WAV, base64")
    lang: str = "en"
    speak: bool = True


class VaaniTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    lang: str = "en"
    speak: bool = True


class MealTotals(BaseModel):
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    fibre: float = 0


class VaaniUnderstandResponse(BaseModel):
    lang: str
    native_text: str
    english_text: Optional[str] = None
    items: List[FoodItem]
    totals: MealTotals
    reply_english: str
    reply_text: Optional[str] = None
    reply_audio_b64: Optional[str] = None
    warnings: List[str] = []


class VaaniSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    lang: str
    from_english: bool = True


class VaaniSpeakResponse(BaseModel):
    text: str
    audio_b64: Optional[str] = None


class Targets(BaseModel):
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fibre: Optional[float] = None


class TodaySummary(BaseModel):
    totals: MealTotals
    targets: Optional[Targets] = None
    goal: Optional[float] = None
    remaining: Optional[float] = None
    meals: int
    streak: int


# ---------------------------------------------------------------- Admin
class AdminCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128, description="Required when the email has no account yet")

    _pw = field_validator("password")(classmethod(lambda cls, v: check_password(v)))
    _name = field_validator("full_name")(classmethod(lambda cls, v: clean_name(v)))


class UserStatusUpdate(BaseModel):
    is_active: bool


class AuditEntry(BaseModel):
    at: datetime
    actor_email: str
    action: str
    target_email: Optional[str] = None
    detail: str = ""


class DayCount(BaseModel):
    date: str
    meals: int
    users: int


class NameCount(BaseModel):
    name: str
    count: int


class OnboardingResult(BaseModel):
    user: UserRead
    plan: Dict


class AdminOverview(BaseModel):
    total_users: int
    active_users_7d: int
    new_users_7d: int
    total_meals: int
    meals_today: int
    avg_calories_per_meal: float
    admins: int
    languages: List[NameCount]
    top_foods: List[NameCount]
    daily: List[DayCount]
    goals: List[NameCount] = []
    diets: List[NameCount] = []
    conditions: List[NameCount] = []
    onboarded: int = 0


class AdminUserRow(UserRead):
    meals: int = 0
