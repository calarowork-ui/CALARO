"""End-to-end tests with an in-memory MongoDB (mongomock-motor) and Bhashini mocked at the HTTP layer.

Run from backend/:  pip install -r requirements-dev.txt && python -m pytest -q
"""
import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import bhashini_service  # noqa: E402
from app.services.nutrition_engine import parse_meal  # noqa: E402

CALLS = []


def fake_post_factory(real_post):
    async def fake_post(self, url, json=None, headers=None, **kw):
        if "bhashini" not in str(url) and "ulcacontrib" not in str(url):
            return await real_post(self, url, json=json, headers=headers, **kw)
        CALLS.append((str(url), json, headers))
        req = httpx.Request("POST", url)
        if "getModelsPipeline" in str(url):
            assert headers["userID"] == "test-user" and headers["ulcaApiKey"] == "test-key"
            return httpx.Response(200, request=req, json={
                "pipelineResponseConfig": [
                    {"taskType": t["taskType"], "config": [{"serviceId": f"svc-{t['taskType']}"}]}
                    for t in json["pipelineTasks"]
                ],
                "pipelineInferenceAPIEndPoint": {
                    "callbackUrl": "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
                    "inferenceApiKey": {"name": "Authorization", "value": "inference-key"},
                },
            })
        direct = headers["Authorization"] == "direct-inference-key"
        assert direct or headers["Authorization"] == "inference-key"
        out = []
        for t in json["pipelineTasks"]:
            if direct:
                assert t["config"]["serviceId"].startswith("ai4bharat/")
            else:
                assert t["config"]["serviceId"] == f"svc-{t['taskType']}"
            if t["taskType"] == "asr":
                out.append({"taskType": "asr", "output": [{"source": "ரெண்டு இட்லி ஒரு வடை ஒரு கிண்ணம் சாம்பார்"}]})
            elif t["taskType"] == "translation":
                src = json["inputData"].get("input", [{"source": ""}])[0]["source"]
                target = "Two idli, one vada and one bowl of sambar" if t["config"]["language"]["targetLanguage"] == "en" else f"[{t['config']['language']['targetLanguage']}] {src}"
                out.append({"taskType": "translation", "output": [{"source": src, "target": target}]})
            elif t["taskType"] == "tts":
                out.append({"taskType": "tts", "audio": [{"audioContent": "UklGRg=="}]})
        return httpx.Response(200, request=req, json={"pipelineResponse": out})
    return fake_post


@pytest.fixture(scope="module")
def client():
    real_post = httpx.AsyncClient.post
    httpx.AsyncClient.post = fake_post_factory(real_post)
    bhashini_service.settings.BHASHINI_USER_ID = "test-user"
    bhashini_service.settings.BHASHINI_API_KEY = "test-key"
    with TestClient(app) as c:
        c.post("/api/v1/auth/register", json={"email": "amma@example.com", "password": "secret123", "full_name": "Amma"})
        tok = c.post("/api/v1/auth/login", data={"username": "amma@example.com", "password": "secret123"}).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {tok}"})
        c.put("/api/v1/auth/profile", json={"age": 55, "height_cm": 158, "weight_kg": 64, "sex": "female",
                                             "activity_level": "light", "preferred_language": "ta"})
        yield c
    httpx.AsyncClient.post = real_post


def test_status(client):
    r = client.get("/api/v1/vaani/status").json()
    assert r["bhashini_configured"] is True
    assert r["food_count"] >= 100
    assert any(l["code"] == "ta" for l in r["languages"])


def test_voice_tamil_end_to_end(client):
    r = client.post("/api/v1/vaani/voice", json={"audio_b64": "AAAA", "lang": "ta"})
    assert r.status_code == 200, r.text
    body = r.json()
    names = {i["food_id"]: i for i in body["items"]}
    assert names["idli"]["quantity"] == 2
    assert names["medu_vada"]["quantity"] == 1
    assert names["sambar"]["unit"] == "bowl"
    assert body["totals"]["calories"] == 386
    assert body["reply_audio_b64"] == "UklGRg=="
    assert body["reply_text"].startswith("[ta]")
    assert "calories left" in body["reply_english"]


def test_text_then_save_and_today(client):
    r = client.post("/api/v1/vaani/text", json={"text": "दो रोटी, एक कटोरी दाल", "lang": "hi", "speak": False}).json()
    assert {i["food_id"] for i in r["items"]} >= {"roti", "dal"}
    saved = client.post("/api/v1/food/logs", json={
        "raw_text": r["english_text"] or r["native_text"], "native_text": r["native_text"],
        "language": "hi", "items": r["items"]}).json()
    assert saved["total_protein"] > 10 and saved["language"] == "hi"
    today = client.get("/api/v1/vaani/today").json()
    assert today["meals"] == 1 and today["streak"] == 1 and today["goal"]


def test_profile_language(client):
    assert client.get("/api/v1/auth/profile").json()["preferred_language"] == "ta"


def test_food_search_native_script(client):
    r = client.get("/api/v1/vaani/foods", params={"q": "இட்", "lang": "ta"}).json()
    assert r[0]["food_id"] == "idli" and r[0]["native_name"] == "இட்லி"


@pytest.mark.parametrize("lang,text,expected", [
    ("te", "రెండు ఇడ్లీలు మరియు ఒక కప్పు కాఫీ", {"idli": 2, "filter_coffee": 1}),
    ("bn", "দুটো রুটি আর মাছের ঝোল", {"roti": 2, "fish_curry": 1}),
    ("ml", "രണ്ട് പുട്ട്, ഒരു കടല കറി", {"puttu": 2, "chole": 1}),
    ("gu", "બે રોટલી, એક વાટકી દાળ", {"roti": 2, "dal": 1}),
    ("mr", "दोन पोळ्या आणि एक वडापाव", {"roti": 2, "vada_pav": 1}),
    ("kn", "ಎರಡು ಇಡ್ಲಿ ಒಂದು ವಡೆ", {"idli": 2, "medu_vada": 1}),
    ("en", "rendu dosa oru coffee", {"dosa": 2, "filter_coffee": 1}),
    ("en", "one and a half glass of buttermilk", {"buttermilk": 1.5}),
])
def test_parse_languages(lang, text, expected):
    got = {i["food_id"]: i["quantity"] for i in parse_meal(text, lang)}
    for k, v in expected.items():
        assert got.get(k) == v, (text, got)


def test_direct_inference_mode(client):
    """New dashboard keys: Inference key alone goes straight to Dhruva."""
    from app.core.config import settings
    saved = settings.BHASHINI_USER_ID, settings.BHASHINI_API_KEY
    settings.BHASHINI_USER_ID = settings.BHASHINI_API_KEY = None
    settings.BHASHINI_INFERENCE_API_KEY = "direct-inference-key"
    bhashini_service.bhashini.mode = None
    try:
        CALLS.clear()
        r = client.post("/api/v1/vaani/voice", json={"audio_b64": "AAAA", "lang": "ta"})
        assert r.status_code == 200, r.text
        assert not any("getModelsPipeline" in c[0] for c in CALLS)
        asr = CALLS[0][1]["pipelineTasks"][0]
        assert asr["config"]["serviceId"] == "ai4bharat/conformer-multilingual-dravidian-gpu--t4"
        assert bhashini_service.bhashini.mode == "direct"
    finally:
        settings.BHASHINI_USER_ID, settings.BHASHINI_API_KEY = saved
        settings.BHASHINI_INFERENCE_API_KEY = ""
        bhashini_service.bhashini.mode = None


def test_service_id_routing():
    from app.services.bhashini_service import direct_service_id
    assert "dravidian" in direct_service_id("tts", {"sourceLanguage": "ml"})
    assert "indo_aryan" in direct_service_id("tts", {"sourceLanguage": "bn"})
    assert "misc" in direct_service_id("tts", {"sourceLanguage": "en"})
    assert direct_service_id("asr", {"sourceLanguage": "hi"}) == "ai4bharat/conformer-hi-gpu--t4"
    assert "indictrans" in direct_service_id("translation", {"sourceLanguage": "ta", "targetLanguage": "en"})
