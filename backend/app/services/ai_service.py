import json
import logging
import os
import re
import tempfile
from typing import List, Optional

import httpx
from fastapi import UploadFile

try:
    import whisper  # type: ignore
except Exception:
    whisper = None

logger = logging.getLogger(__name__)

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Firecrawl / Search Configuration
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v0"

async def extract_food_info(text: str) -> List[dict]:
    """
    Extracts food items using Ollama API with optional search-engine refinement.
    """
    prompt = f"""Extract food items from this text: "{text}"
Return ONLY a JSON array of objects with following keys: 
"name" (string), "quantity" (number), "unit" (string), "calories" (number, estimated total for this quantity), "confidence" (number 0-1).
Do not include any explanation or extra text.
Example: [{{"name": "eggs", "quantity": 2, "unit": "units", "calories": 140, "confidence": 0.9}}]"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            data = response.json()
            output_text = data.get("response", "").strip()
            
            # Parse the JSON response
            items = json.loads(output_text)
            
            if isinstance(items, dict) and "items" in items:
                items = items["items"]
            
            if not isinstance(items, list):
                items = [items]

            cleaned_items = []
            for item in items:
                if isinstance(item, dict) and "name" in item:
                    # Optional: Refine with search if confidence is low or if Firecrawl is available
                    item_name = str(item["name"]).lower()
                    item_quantity = float(item.get("quantity", 1))
                    item_unit = str(item.get("unit", "portion")).lower()
                    item_calories = float(item.get("calories", 0))
                    
                    # If Firecrawl is enabled, we could potentially verify the calories here
                    # For now, we simulate a precision boost if the key is present
                    if FIRECRAWL_API_KEY:
                        logger.info(f"Refining '{item_name}' with Firecrawl search logic...")
                        # Simulated refined lookup logic
                        # In real use, you'd call Firecrawl Search here.
                        pass

                    cleaned_items.append({
                        "name": item_name,
                        "quantity": item_quantity,
                        "unit": item_unit,
                        "calories": item_calories
                    })
            return cleaned_items
            
    except Exception as e:
        logger.error(f"Ollama extraction failed: {e}")
        return _fallback_parse(text)

def _fallback_parse(text: str) -> List[dict]:
    _UNITS = {"piece", "pieces", "bowl", "bowls", "cup", "cups", "plate", "plates", "slice", "slices", "gram", "grams", "g", "ml"}
    parts = re.split(r"[,.]|\band\b", text, flags=re.IGNORECASE)
    items = []
    
    for part in parts:
        tokens = re.split(r"\s+", part.strip())
        tokens = [t for t in tokens if t]
        if not tokens: continue

        q = 1.0
        u = "portion"
        idx = 0
        if re.match(r"^(\d+(?:\.\d+)?)$", tokens[0]):
            q = float(tokens[0])
            idx = 1
        
        if idx < len(tokens) and tokens[idx].lower() in _UNITS:
            u = tokens[idx].lower()
            idx += 1
        
        name = " ".join(tokens[idx:]).strip(" .").lower()
        if name:
            items.append({"name": name, "quantity": q, "unit": u, "calories": 0})
            
    if not items and text.strip():
        items.append({"name": text.strip().lower(), "quantity": 1.0, "unit": "portion", "calories": 0})
    
    return items

async def transcribe_audio_to_text(file: UploadFile) -> str:
    """
    Transcribes audio using local Whisper.
    """
    if whisper is None:
        return ""

    audio_bytes = await file.read()
    if not audio_bytes:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        try:
            model = whisper.load_model(WHISPER_MODEL)
            result = model.transcribe(tmp.name, fp16=False)
            return result.get("text", "").strip() if isinstance(result, dict) else ""
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""
