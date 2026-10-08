"""First-run questions for members, and the plan built from them."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .... import crud, schemas
from ....core.observability import ONBOARDING_DONE
from ....database import Doc, get_db, utcnow
from ....services.onboarding import OnboardingAnswers, build_plan
from .auth import get_current_user

router = APIRouter()


@router.post("", response_model=schemas.OnboardingResult, summary="Save onboarding answers and build the plan")
async def complete_onboarding(
    answers: OnboardingAnswers,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    plan = build_plan(answers)
    changes: Dict[str, Any] = {
        "onboarding": answers.model_dump(),
        "plan": plan,
        "onboarded_at": user.get("onboarded_at") or utcnow(),
        "age": answers.age, "sex": answers.sex, "height_cm": answers.height_cm, "weight_kg": answers.weight_kg,
        "activity_level": answers.activity_level, "preferred_language": answers.preferred_language,
    }
    if answers.full_name:
        changes["full_name"] = answers.full_name.strip()
    await db.users.update_one({"_id": user["_id"]}, {"$set": changes})
    ONBOARDING_DONE.labels(answers.goal, answers.diet).inc()
    updated = await crud.get_user(db, user["_id"])
    return schemas.OnboardingResult(user=schemas.user_out(updated), plan=plan)


@router.get("/plan", summary="Your current plan")
async def get_plan(user: Doc = Depends(get_current_user)):
    if not user.get("plan"):
        raise HTTPException(status_code=404, detail="No plan yet. Answer the setup questions first.")
    return {"plan": user["plan"], "answers": user.get("onboarding")}
