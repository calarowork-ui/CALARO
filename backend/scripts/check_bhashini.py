"""Checks your Bhashini keys from backend/.env and shows which mode works.

Run from the backend folder:   python scripts/check_bhashini.py
Nothing is logged or printed except masked keys and the results.
"""
import asyncio
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.services import bhashini_service as bs  # noqa: E402


def mask(v):
    return f"{v[:4]}…{v[-3:]} ({len(v)} chars)" if v else "(empty)"


async def try_mode(mode):
    client = bs.BhashiniClient()
    client.only_mode = mode
    if mode == "config" and not bs._config_credentials():
        return print(f"  [{mode}] skipped: needs BHASHINI_UDYAT_KEY + BHASHINI_INFERENCE_API_KEY")
    if mode == "direct" and not settings.BHASHINI_INFERENCE_API_KEY:
        return print(f"  [{mode}] skipped: BHASHINI_INFERENCE_API_KEY empty")
    try:
        out = await client.translate("Two idli and one bowl of sambar", "en", "ta")
        print(f"  [{mode}] translation en->ta OK: {out}")
        _, audio = await client.speak("नमस्ते, आपने दो रोटी खाई", "hi")
        print(f"  [{mode}] text-to-speech hi OK: {len(base64.b64decode(audio or '')) // 1024} KB audio")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  [{mode}] FAILED: {exc}")
        return False


async def main():
    print("Keys found in backend/.env:")
    print("  BHASHINI_INFERENCE_API_KEY", mask(settings.BHASHINI_INFERENCE_API_KEY))
    print("  BHASHINI_UDYAT_KEY        ", mask(settings.BHASHINI_UDYAT_KEY))
    print("  BHASHINI_USER_ID          ", mask(settings.BHASHINI_USER_ID))
    print("  BHASHINI_API_KEY          ", mask(settings.BHASHINI_API_KEY))
    print("\nDirect inference (Inference key only):")
    direct = await try_mode("direct")
    print("\nPipeline config (Udyat key + Inference key):")
    config = await try_mode("config")
    print()
    if direct or config:
        print("Bhashini is working. CALARO will use", "direct" if direct else "config", "mode automatically.")
    else:
        print("Neither mode worked. Copy the FAILED lines above and share them (they don't contain your keys).")


asyncio.run(main())
