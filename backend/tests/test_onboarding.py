"""Members answer setup questions once; the plan drives their daily targets."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.onboarding import OnboardingAnswers, build_plan

ANSWERS = {
    "full_name": "Lakshmi", "preferred_language": "ta", "age": 34, "sex": "female", "height_cm": 158, "weight_kg": 68,
    "goal": "lose", "target_weight_kg": 60, "pace": "steady", "activity_level": "light",
    "meals": ["early_tea", "breakfast", "lunch", "evening_snack", "dinner"], "tea_cups": 3, "sugar_spoons": 2,
    "diet": "vegetarian", "region": "south", "fasting": "festivals", "conditions": ["prediabetes"], "challenge": "fried_snacks",
}


def login(c, email, pw):
    r = c.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def test_plan_maths():
    p = build_plan(OnboardingAnswers(**ANSWERS), today=date(2026, 10, 7))
    assert p["bmi"] == 27.2 and p["bmi_category"] == "obese"  # Asian cut-off: 25+
    assert p["tdee"] == 1838 and p["targets"]["calories"] == 1340  # TDEE - 500
    assert p["targets"]["fibre"] == 35 and p["carb_pct"] == 40  # prediabetes
    assert p["timeline"]["weeks"] == 16 and p["timeline"]["by_date"] == "2027-01-27"
    assert p["chai"]["sugar_g_day"] == 30 and p["chai"]["kg_year"] == 5.7
    assert sum(m["calories"] for m in p["meals"]) == pytest.approx(1340, abs=10)
    assert all("nonveg" not in pk["food_id"] and pk["food_id"] not in ("boiled_egg", "omelette") for pk in p["protein_picks"])
    titles = [i["title"] for i in p["insights"]]
    assert "The sugar in your chai" in titles and "Prediabetes" in titles and "Protein on a vegetarian diet" in titles


def test_calorie_floor_and_vegan_picks():
    a = {**ANSWERS, "age": 60, "height_cm": 150, "weight_kg": 50, "target_weight_kg": 45, "activity_level": "sedentary", "diet": "vegan"}
    p = build_plan(OnboardingAnswers(**a))
    assert p["targets"]["calories"] == 1200
    assert not {"paneer", "milk", "curd", "paneer_tikka"} & {pk["food_id"] for pk in p["protein_picks"]}


def test_bad_target_rejected():
    with pytest.raises(ValueError):
        OnboardingAnswers(**{**ANSWERS, "target_weight_kg": 75})


def test_member_onboarding_flow(c):
    c.post("/api/v1/auth/register", json={"email": "lakshmi@example.com", "password": "lakshmi-pass1"})
    h = login(c, "lakshmi@example.com", "lakshmi-pass1")
    assert c.get("/api/v1/auth/me", headers=h).json()["needs_onboarding"] is True
    assert c.post("/api/v1/onboarding", json={**ANSWERS, "target_weight_kg": 80}, headers=h).status_code == 422
    r = c.post("/api/v1/onboarding", json=ANSWERS, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["needs_onboarding"] is False and body["user"]["full_name"] == "Lakshmi"
    assert body["user"]["preferred_language"] == "ta"
    today = c.get("/api/v1/vaani/today", headers=h).json()
    assert today["goal"] == 1340 and today["targets"]["protein"] == 75
    # body change re-builds the plan
    c.put("/api/v1/auth/profile", json={"weight_kg": 64}, headers=h)
    plan = c.get("/api/v1/onboarding/plan", headers=h).json()["plan"]
    assert plan["bmi"] == 25.6 and plan["timeline"]["from_kg"] == 64


def test_admins_skip_onboarding(c):
    h = login(c, "calaro@admin.calaro.com", "super-secret-1")
    assert c.get("/api/v1/auth/me", headers=h).json()["needs_onboarding"] is False
    o = c.get("/api/v1/admin/overview", headers=h).json()
    assert o["onboarded"] >= 1 and any(g["name"] == "lose" for g in o["goals"])
