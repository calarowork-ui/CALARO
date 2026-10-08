from fastapi import APIRouter, File, UploadFile

from .... import schemas
from ....services.ai_service import extract_food_info, transcribe_audio_to_text


router = APIRouter()


@router.post(
    "/transcribe",
    response_model=schemas.VoiceParseResponse,
    summary="Transcribe an audio clip and extract structured food items",
)
async def transcribe_and_parse(
    audio: UploadFile = File(...),
):
    """
    Accepts a short audio clip describing a meal, transcribes it using Whisper,
    then runs the same food-extraction pipeline used for text.
    """
    text = await transcribe_audio_to_text(audio)
    if not text:
        # Graceful degradation: return empty items so the UI can handle it.
        return schemas.VoiceParseResponse(text="", items=[])

    items = await extract_food_info(text=text)
    return schemas.VoiceParseResponse(
        text=text,
        items=[schemas.FoodItem(**item) for item in items],
    )

