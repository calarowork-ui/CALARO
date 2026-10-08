from fastapi import APIRouter

from .endpoints import admin, auth, food, voice, password_reset, vaani, onboarding, monitoring

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(password_reset.router, prefix="/password-reset", tags=["password_reset"])
api_router.include_router(food.router, prefix="/food", tags=["food"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(monitoring.router, prefix="/admin/monitoring", tags=["monitoring"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(vaani.router, prefix="/vaani", tags=["vaani"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
