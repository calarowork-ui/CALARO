"""
Bhashini (MeitY / ULCA / Dhruva) client for CALARO.

Two ways to authenticate, both supported, tried in this order:

  A. Direct inference (new Bhashini dashboard: "Inference" key)
     POST dhruva-api.bhashini.gov.in/services/inference/pipeline with
     Authorization: <inference key>, using the public AI4Bharat serviceIds below.

  B. Pipeline config (ULCA flow: userID + ulcaApiKey -> getModelsPipeline)
     returns serviceIds, the callback URL and a short-lived inference key.
     Candidate credential pairs tried: (BHASHINI_USER_ID, BHASHINI_API_KEY)
     and (BHASHINI_UDYAT_KEY, BHASHINI_INFERENCE_API_KEY).

Whichever works first is remembered for the life of the process.
Run `python scripts/check_bhashini.py` to see which one your keys support.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..core.config import settings
from ..core.observability import BHASHINI_ERRORS, BHASHINI_SECONDS

logger = logging.getLogger(__name__)

CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
DEFAULT_INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
CACHE_TTL_SECONDS = 60 * 30

DRAVIDIAN = {"ta", "te", "kn", "ml"}
INDO_ARYAN = {"hi", "bn", "gu", "mr", "or", "pa", "as", "ur"}

# Public Dhruva serviceIds (AI4Bharat models). Override any of them with the
# BHASHINI_SERVICE_IDS env var, e.g. {"asr:hi": "ai4bharat/conformer-hi-gpu--t4"}
DEFAULT_SERVICE_IDS: Dict[str, str] = {
    "asr:dravidian": "ai4bharat/conformer-multilingual-dravidian-gpu--t4",
    "asr:indo_aryan": "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4",
    "asr:en": "ai4bharat/whisper-medium-en--gpu--t4",
    "asr:hi": "ai4bharat/conformer-hi-gpu--t4",
    "translation": "ai4bharat/indictrans-v2-all-gpu--t4",
    "tts:dravidian": "ai4bharat/indic-tts-coqui-dravidian-gpu--t4",
    "tts:indo_aryan": "ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4",
    "tts:misc": "ai4bharat/indic-tts-coqui-misc-gpu--t4",
}


def _service_overrides() -> Dict[str, str]:
    raw = settings.BHASHINI_SERVICE_IDS
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("BHASHINI_SERVICE_IDS is not valid JSON; ignoring")
        return {}


def direct_service_id(task_type: str, language: Dict[str, str]) -> str:
    table = {**DEFAULT_SERVICE_IDS, **_service_overrides()}
    src = language.get("sourceLanguage", "en")
    specific = table.get(f"{task_type}:{src}")
    if specific:
        return specific
    if task_type == "translation":
        return table["translation"]
    family = "dravidian" if src in DRAVIDIAN else "indo_aryan" if src in INDO_ARYAN else ("en" if task_type == "asr" else "misc")
    return table[f"{task_type}:{family}"]


class BhashiniError(RuntimeError):
    pass


class BhashiniNotConfigured(BhashiniError):
    pass


def _config_credentials() -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    if settings.BHASHINI_USER_ID and settings.BHASHINI_API_KEY:
        pairs.append((settings.BHASHINI_USER_ID, settings.BHASHINI_API_KEY))
    if settings.BHASHINI_UDYAT_KEY and settings.BHASHINI_INFERENCE_API_KEY:
        pairs.append((settings.BHASHINI_UDYAT_KEY, settings.BHASHINI_INFERENCE_API_KEY))
    return pairs


def is_configured() -> bool:
    return bool(settings.BHASHINI_INFERENCE_API_KEY or _config_credentials())


class BhashiniClient:
    def __init__(self) -> None:
        self._cache: Dict[Tuple, Tuple[float, Dict[str, Any]]] = {}
        self.mode: Optional[str] = None  # "direct" | "config" once one has worked
        self.last_errors: List[str] = []
        self.only_mode: Optional[str] = None  # used by scripts/check_bhashini.py

    # ------------------------------------------------------------- config (B)
    async def _pipeline_config(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        key = tuple(
            (t["taskType"], t["config"]["language"].get("sourceLanguage"), t["config"]["language"].get("targetLanguage"))
            for t in tasks
        )
        cached = self._cache.get(key)
        if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

        payload = {
            "pipelineTasks": tasks,
            "pipelineRequestConfig": {"pipelineId": settings.BHASHINI_PIPELINE_ID},
        }
        errors = []
        for user_id, api_key in _config_credentials():
            headers = {"Content-Type": "application/json", "userID": user_id, "ulcaApiKey": api_key}
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(CONFIG_URL, json=payload, headers=headers)
            if resp.status_code >= 400:
                errors.append(f"config {resp.status_code}: {resp.text[:200]}")
                continue
            data = resp.json()
            endpoint = data.get("pipelineInferenceAPIEndPoint") or {}
            key_obj = endpoint.get("inferenceApiKey") or {}
            service_ids: Dict[str, str] = {}
            for task_cfg in data.get("pipelineResponseConfig", []):
                configs = task_cfg.get("config") or []
                if configs:
                    service_ids[task_cfg["taskType"]] = configs[0]["serviceId"]
            missing = [t["taskType"] for t in tasks if t["taskType"] not in service_ids]
            if missing:
                raise BhashiniError(f"Bhashini has no model for {missing} with languages {key}")
            result = {
                "url": endpoint.get("callbackUrl") or DEFAULT_INFERENCE_URL,
                "auth_name": key_obj.get("name") or "Authorization",
                "auth_value": key_obj.get("value") or settings.BHASHINI_INFERENCE_API_KEY,
                "service_ids": service_ids,
            }
            self._cache[key] = (time.time(), result)
            return result
        raise BhashiniError("; ".join(errors) or "no pipeline-config credentials")

    # ------------------------------------------------------------- compute
    async def _post(self, url: str, auth_name: str, auth_value: str, tasks, input_data) -> httpx.Response:
        headers = {"Content-Type": "application/json", auth_name: auth_value}
        payload = {"pipelineTasks": tasks, "inputData": input_data}
        async with httpx.AsyncClient(timeout=45.0) as client:
            return await client.post(url, json=payload, headers=headers)

    async def _compute(self, tasks: List[Dict[str, Any]], input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not is_configured():
            raise BhashiniNotConfigured(
                "Bhashini is not configured. Add BHASHINI_INFERENCE_API_KEY (and BHASHINI_UDYAT_KEY) to backend/.env"
            )
        errors: List[str] = []
        modes = ["direct", "config"] if self.mode != "config" else ["config", "direct"]
        for mode in modes:
            if self.only_mode and mode != self.only_mode:
                continue
            if mode == "direct" and not settings.BHASHINI_INFERENCE_API_KEY:
                continue
            if mode == "config" and not _config_credentials():
                continue
            run_tasks = json.loads(json.dumps(tasks))
            task_name = "+".join(t["taskType"] for t in tasks)
            started = time.perf_counter()
            try:
                if mode == "direct":
                    for t in run_tasks:
                        t["config"]["serviceId"] = direct_service_id(t["taskType"], t["config"]["language"])
                    resp = await self._post(DEFAULT_INFERENCE_URL, "Authorization",
                                            settings.BHASHINI_INFERENCE_API_KEY, run_tasks, input_data)
                else:
                    cfg = await self._pipeline_config([
                        {"taskType": t["taskType"], "config": {"language": t["config"]["language"]}} for t in run_tasks
                    ])
                    for t in run_tasks:
                        t["config"]["serviceId"] = cfg["service_ids"][t["taskType"]]
                    resp = await self._post(cfg["url"], cfg["auth_name"], cfg["auth_value"], run_tasks, input_data)
            except (httpx.HTTPError, BhashiniError) as exc:
                BHASHINI_ERRORS.labels(task_name, mode).inc()
                errors.append(f"{mode}: {exc}")
                continue
            BHASHINI_SECONDS.labels(task_name, mode).observe(time.perf_counter() - started)
            if resp.status_code >= 400:
                BHASHINI_ERRORS.labels(task_name, mode).inc()
                errors.append(f"{mode} {resp.status_code}: {resp.text[:200]}")
                continue
            if self.mode != mode:
                logger.info("Bhashini working in %s mode", mode)
            self.mode = mode
            return resp.json().get("pipelineResponse", [])
        self.last_errors = errors
        raise BhashiniError(" | ".join(errors) or "Bhashini call failed")

    # ------------------------------------------------------------------ tasks
    async def speech_to_text(self, audio_b64: str, lang: str, translate_to_english: bool = True) -> Tuple[str, Optional[str]]:
        """Returns (native_transcript, english_translation_or_None)."""
        tasks: List[Dict[str, Any]] = [{
            "taskType": "asr",
            "config": {"language": {"sourceLanguage": lang}, "audioFormat": "wav", "samplingRate": 16000},
        }]
        chain = translate_to_english and lang != "en"
        if chain:
            tasks.append({"taskType": "translation",
                          "config": {"language": {"sourceLanguage": lang, "targetLanguage": "en"}}})
        out = await self._compute(tasks, {"audio": [{"audioContent": audio_b64}]})
        native = _first_output(out, "asr", "source") or ""
        english = _first_output(out, "translation", "target") if chain else (native if lang == "en" else None)
        return native.strip(), (english or "").strip() or None

    async def translate(self, text: str, source: str, target: str) -> str:
        if source == target or not text.strip():
            return text
        out = await self._compute(
            [{"taskType": "translation", "config": {"language": {"sourceLanguage": source, "targetLanguage": target}}}],
            {"input": [{"source": text}]},
        )
        return (_first_output(out, "translation", "target") or text).strip()

    async def speak(self, text: str, lang: str, translate_from_english: bool = False) -> Tuple[str, Optional[str]]:
        """Returns (spoken_text, base64_wav). Optionally translates EN -> lang first, in the same call."""
        tasks: List[Dict[str, Any]] = []
        if translate_from_english and lang != "en":
            tasks.append({"taskType": "translation",
                          "config": {"language": {"sourceLanguage": "en", "targetLanguage": lang}}})
        tts_cfg: Dict[str, Any] = {"language": {"sourceLanguage": lang}, "gender": settings.BHASHINI_TTS_GENDER}
        if settings.BHASHINI_TTS_SAMPLING_RATE:
            tts_cfg["samplingRate"] = settings.BHASHINI_TTS_SAMPLING_RATE
        tasks.append({"taskType": "tts", "config": tts_cfg})
        out = await self._compute(tasks, {"input": [{"source": text}]})
        spoken = _first_output(out, "translation", "target") or text
        audio = None
        for block in out:
            if block.get("taskType") == "tts":
                audios = block.get("audio") or []
                if audios:
                    audio = audios[0].get("audioContent")
        return spoken.strip(), audio


def _first_output(blocks: List[Dict[str, Any]], task_type: str, field: str) -> Optional[str]:
    for block in blocks:
        if block.get("taskType") == task_type:
            outputs = block.get("output") or []
            if outputs:
                return outputs[0].get(field)
    return None


bhashini = BhashiniClient()
