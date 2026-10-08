"""
Vaani: speak your meal in any Indian language.

  native speech --(Bhashini ASR+NMT)--> native text + English
               --(Indian food DB)------> items with katori/roti/ladle portions
               --(coach)---------------> reply in English
               --(Bhashini NMT+TTS)----> reply spoken back in the user's language
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from .... import crud, schemas
from ....core.config import settings
from ....core.observability import VAANI_ITEMS, VAANI_REQUESTS
from ....core.ratelimit import enforce
from ....database import Doc, get_db, utcnow
from ....services import nutrition_engine as engine
from ....services.ai_service import extract_food_info
from ....services.bhashini_service import BhashiniError, BhashiniNotConfigured, bhashini, is_configured
from ....services.coach import build_reply
from .auth import daily_goal, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

IST_OFFSET = timedelta(hours=5, minutes=30)


def _check_lang(lang: str) -> str:
    lang = (lang or "en").lower()
    if lang not in engine.LANGUAGE_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'")
    return lang


def _today_start_utc() -> datetime:
    local_now = utcnow() + IST_OFFSET
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight - IST_OFFSET


async def _today_totals(db: AsyncIOMotorDatabase, user: Doc) -> schemas.MealTotals:
    logs = await crud.get_food_logs_since(db, user_id=user["_id"], since=_today_start_utc())
    return schemas.MealTotals(
        calories=round(sum(l.total_calories or 0 for l in logs), 1),
        protein=round(sum(l.total_protein or 0 for l in logs), 1),
        carbs=round(sum(l.total_carbs or 0 for l in logs), 1),
        fat=round(sum(l.total_fat or 0 for l in logs), 1),
        fibre=round(sum(l.total_fibre or 0 for l in logs), 1),
    )


async def _understand(
    *, native_text: str, english_text: Optional[str], lang: str, speak: bool, mode: str = "text",
    db: AsyncIOMotorDatabase, user: Doc, warnings: List[str],
) -> schemas.VaaniUnderstandResponse:
    native_items = engine.parse_meal(native_text, lang) if native_text else []
    english_items = engine.parse_meal(english_text, lang) if english_text and english_text != native_text else []
    items = engine.combine_native_and_english(native_items, english_items)

    # Nothing in our curated DB? Fall back to the local LLM estimate (Ollama) if it is running.
    if not items and (english_text or native_text):
        try:
            guesses = await extract_food_info(english_text or native_text)
            for g in guesses:
                if g.get("calories"):
                    items.append({**g, "matched": False, "source": "ai-estimate"})
            if items:
                warnings.append("Some foods were estimated by AI, not from the Indian food database. Please check the numbers.")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("LLM fallback failed: %s", exc)

    outcome = "matched" if any(i.get("matched", True) for i in items) else ("ai_estimate" if items else "no_match")
    VAANI_REQUESTS.labels(mode, lang, outcome).inc()
    VAANI_ITEMS.observe(len(items))
    meal_totals = engine.totals(items)
    goal = daily_goal(user)
    remaining = None
    if goal:
        remaining = goal - (await _today_totals(db, user)).calories - meal_totals["calories"]

    reply_en = build_reply(items, meal_totals, remaining)
    reply_text, reply_audio = (reply_en if lang == "en" else None), None
    if speak and is_configured():
        try:
            reply_text, reply_audio = await bhashini.speak(reply_en, lang, translate_from_english=True)
        except BhashiniError as exc:
            logger.warning("Bhashini TTS failed: %s", exc)
            warnings.append("Voice reply is unavailable right now.")

    return schemas.VaaniUnderstandResponse(
        lang=lang,
        native_text=native_text,
        english_text=english_text,
        items=[schemas.FoodItem(**i) for i in items],
        totals=schemas.MealTotals(**meal_totals),
        reply_english=reply_en,
        reply_text=reply_text,
        reply_audio_b64=reply_audio,
        warnings=warnings,
    )


@router.get("/status", response_model=schemas.VaaniStatus, summary="Languages and Bhashini availability")
def status():
    foods, _ = engine.load_foods()
    return schemas.VaaniStatus(
        bhashini_configured=is_configured(),
        languages=[schemas.LanguageOut(**l) for l in engine.LANGUAGES],
        food_count=len(foods),
    )


@router.post("/voice", response_model=schemas.VaaniUnderstandResponse, summary="Log a meal by speaking in any Indian language")
async def understand_voice(
    body: schemas.VaaniVoiceRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: Doc = Depends(get_current_user),
):
    enforce(f"vaani:{current_user['_id']}", settings.VAANI_PER_MINUTE, 60, "meal requests")
    lang = _check_lang(body.lang)
    if len(body.audio_b64) > 8_000_000:
        raise HTTPException(status_code=413, detail="Recording is too long. Keep it under about 60 seconds.")
    try:
        native_text, english_text = await bhashini.speech_to_text(body.audio_b64, lang)
    except BhashiniNotConfigured as exc:
        VAANI_REQUESTS.labels("voice", lang, "not_configured").inc()
        raise HTTPException(status_code=503, detail=str(exc))
    except BhashiniError as exc:
        VAANI_REQUESTS.labels("voice", lang, "speech_error").inc()
        logger.error("Bhashini ASR failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not understand the audio right now. Please try again or type it.")
    if not native_text:
        VAANI_REQUESTS.labels("voice", lang, "silence").inc()
        raise HTTPException(status_code=422, detail="I could not hear anything. Please speak a little closer to the mic.")
    return await _understand(native_text=native_text, english_text=english_text, lang=lang, mode="voice",
                             speak=body.speak, db=db, user=current_user, warnings=[])


@router.post("/text", response_model=schemas.VaaniUnderstandResponse, summary="Log a meal from text in any Indian language or script")
async def understand_text(
    body: schemas.VaaniTextRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: Doc = Depends(get_current_user),
):
    enforce(f"vaani:{current_user['_id']}", settings.VAANI_PER_MINUTE, 60, "meal requests")
    lang = _check_lang(body.lang)
    warnings: List[str] = []
    english_text: Optional[str] = body.text if lang == "en" else None
    if lang != "en" and is_configured():
        try:
            english_text = await bhashini.translate(body.text, lang, "en")
        except BhashiniError as exc:
            logger.warning("Bhashini NMT failed: %s", exc)
            warnings.append("Translation is unavailable, matched foods from your own words only.")
    return await _understand(native_text=body.text, english_text=english_text, lang=lang,
                             speak=body.speak, db=db, user=current_user, warnings=warnings)


@router.post("/speak", response_model=schemas.VaaniSpeakResponse, summary="Speak any short text in the chosen language")
async def speak(body: schemas.VaaniSpeakRequest, current_user: Doc = Depends(get_current_user)):
    lang = _check_lang(body.lang)
    try:
        text, audio = await bhashini.speak(body.text, lang, translate_from_english=body.from_english)
    except BhashiniNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except BhashiniError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return schemas.VaaniSpeakResponse(text=text, audio_b64=audio)


@router.get("/foods", response_model=List[schemas.FoodItem], summary="Search the Indian food database in any script")
def search_foods(q: str = Query("", max_length=60), lang: str = "en", limit: int = Query(12, ge=1, le=40)):
    lang = _check_lang(lang)
    return [schemas.FoodItem(**i) for i in engine.search_foods(q, lang, limit)]


@router.get("/today", response_model=schemas.TodaySummary, summary="Today's totals, goal and streak (IST)")
async def today(db: AsyncIOMotorDatabase = Depends(get_db), current_user: Doc = Depends(get_current_user)):
    t = await _today_totals(db, current_user)
    goal = daily_goal(current_user)
    meals = len(await crud.get_food_logs_since(db, user_id=current_user["_id"], since=_today_start_utc()))
    plan_t = (current_user.get("plan") or {}).get("targets")
    return schemas.TodaySummary(
        totals=t,
        targets=schemas.Targets(**{k: plan_t.get(k) for k in ("calories", "protein", "carbs", "fat", "fibre")}) if plan_t else None,
        goal=round(goal) if goal else None,
        remaining=round(goal - t.calories) if goal else None,
        meals=meals,
        streak=await crud.get_logging_streak(db, user_id=current_user["_id"]),
    )
