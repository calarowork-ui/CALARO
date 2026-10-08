from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

import logging

from .... import crud, schemas
from ....core.observability import MEAL_CALORIES, MEALS_LOGGED
from ....database import Doc, get_db
from ....services.ai_service import extract_food_info
from .auth import get_current_user

router = APIRouter()


@router.post("/parse", response_model=List[schemas.FoodItem], summary="Legacy: extract food items from English text")
async def parse_food(text: str):
    items = await extract_food_info(text=text)
    return [schemas.FoodItem(**item) for item in items]


@router.post("/logs", response_model=schemas.FoodLogRead, summary="Save a meal")
async def create_food_log(
    food_log_in: schemas.FoodLogCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: Doc = Depends(get_current_user),
):
    if not food_log_in.items:
        raise HTTPException(status_code=400, detail="Add at least one food before saving.")
    log = await crud.create_food_log(db, user_id=current_user["_id"], food_log_in=food_log_in)
    MEALS_LOGGED.labels(food_log_in.language or "en").inc()
    MEAL_CALORIES.observe(log.get("total_calories") or 0)
    logging.getLogger("calaro.meals").info("meal saved", extra={
        "event": "meal_saved", "user_id": str(current_user["_id"]), "language": food_log_in.language or "en",
        "items": len(food_log_in.items), "kcal": log.get("total_calories")})
    return schemas.log_out(log)


@router.get("/logs", response_model=List[schemas.FoodLogRead], summary="Your recent meals")
async def list_food_logs(
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: Doc = Depends(get_current_user),
):
    logs = await crud.get_food_logs_for_user(db, user_id=current_user["_id"], skip=skip, limit=limit)
    return [schemas.log_out(l) for l in logs]


@router.delete("/logs/{log_id}", status_code=204, summary="Delete one of your meals")
async def delete_food_log(log_id: str, db: AsyncIOMotorDatabase = Depends(get_db), current_user: Doc = Depends(get_current_user)):
    if not await crud.delete_food_log(db, user_id=current_user["_id"], log_id=log_id):
        raise HTTPException(status_code=404, detail="Meal not found.")
