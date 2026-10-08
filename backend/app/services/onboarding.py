"""
First-run questions -> a personal plan.

Every question exists because it changes a number or a piece of advice:

  body (age, sex, height, weight)      -> BMR, BMI (Asian cut-offs), healthy weight range
  goal + pace + target weight          -> calorie adjustment, protein per kg, timeline
  activity                             -> activity factor (TDEE)
  meals usually eaten                  -> per-meal calorie split
  tea/coffee cups x sugar spoons       -> hidden sugar per day / year
  diet pattern                         -> protein picks that fit (veg, egg, vegan, Jain)
  region                               -> staple swaps that fit their food
  health conditions                    -> carb share, fibre, salt guidance
  biggest challenge, fasting           -> the coaching focus

All maths is deterministic and explained in the plan, so a person can see why.
References: Mifflin-St Jeor BMR; WHO Asia-Pacific BMI cut-offs (23 / 25);
ICMR-NIN 2024 dietary guidelines for Indians (protein ~0.8-1 g/kg baseline,
added sugar < 5% energy, fibre ~ 14 g per 1000 kcal); 7700 kcal ~ 1 kg body fat.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from . import nutrition_engine as engine

Goal = Literal["lose", "maintain", "gain", "blood_sugar", "eat_better"]
Pace = Literal["gentle", "steady"]
Activity = Literal["sedentary", "light", "moderate", "active", "very_active"]
Diet = Literal["vegetarian", "eggetarian", "non_vegetarian", "vegan", "jain"]
Region = Literal["south", "north", "east", "west", "northeast", "mixed"]
Meal = Literal["early_tea", "breakfast", "mid_morning", "lunch", "evening_snack", "dinner", "late_night"]
Condition = Literal["diabetes", "prediabetes", "high_bp", "thyroid", "pcos", "cholesterol", "none"]
Challenge = Literal["sweets", "fried_snacks", "late_night", "big_portions", "skipping_meals", "eating_out", "low_protein"]
Fasting = Literal["none", "weekly", "festivals", "ramadan", "intermittent"]


class OnboardingAnswers(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=80)
    preferred_language: str = "en"
    age: int = Field(ge=13, le=100)
    sex: Literal["female", "male"]
    height_cm: float = Field(ge=120, le=220)
    weight_kg: float = Field(ge=30, le=250)
    goal: Goal
    target_weight_kg: Optional[float] = Field(default=None, ge=30, le=250)
    pace: Pace = "steady"
    activity_level: Activity
    meals: List[Meal] = Field(min_length=1)
    tea_cups: int = Field(default=0, ge=0, le=12)
    sugar_spoons: float = Field(default=0, ge=0, le=6)
    diet: Diet
    region: Region
    fasting: Fasting = "none"
    conditions: List[Condition] = Field(default_factory=list)
    challenge: Challenge

    @model_validator(mode="after")
    def _clean(self):
        if "none" in self.conditions:
            self.conditions = []
        if self.goal not in ("lose", "gain"):
            self.target_weight_kg = None
        if self.goal == "lose" and self.target_weight_kg and self.target_weight_kg >= self.weight_kg:
            raise ValueError("Your target weight should be below your current weight.")
        if self.goal == "gain" and self.target_weight_kg and self.target_weight_kg <= self.weight_kg:
            raise ValueError("Your target weight should be above your current weight.")
        if self.preferred_language not in engine.LANGUAGE_CODES:
            self.preferred_language = "en"
        return self


ACTIVITY_FACTOR = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
MEAL_WEIGHT = {"early_tea": 3, "breakfast": 25, "mid_morning": 7, "lunch": 33, "evening_snack": 10, "dinner": 28, "late_night": 4}
MEAL_LABEL = {"early_tea": "Early tea", "breakfast": "Breakfast", "mid_morning": "Mid-morning", "lunch": "Lunch",
              "evening_snack": "Evening snack", "dinner": "Dinner", "late_night": "Late night"}

REGION_SWAPS = {
    "south": "Keep rice to one cup and fill the rest of the plate with sambar vegetables, kootu or poriyal. Ragi mudde, millet dosa or pesarattu a few times a week adds fibre and protein.",
    "north": "Two rotis a meal with a full katori of dal or rajma and a sabzi keeps the plate balanced. Jowar or bajra roti in place of maida naan or paratha cuts refined carbs.",
    "east": "Pair a cup of rice with fish or dal and a vegetable rather than a second helping of rice. Keep mishti for occasions; one rasgulla is about 120 kcal.",
    "west": "Thepla with curd, poha with sprouts or a katori of usal are good everyday picks. Farsan adds up fast: a handful of namkeen is about 160 kcal.",
    "northeast": "Boiled, steamed and smoked dishes are already light. Add a protein at each meal, such as eggs, fish, dal or soybean.",
    "mixed": "Build each plate as half vegetables, a quarter protein (dal, paneer, eggs, fish) and a quarter rice or roti.",
}

CHALLENGE_TIPS = {
    "sweets": "Sweets are your main target. Keep one serving a day, after a meal rather than on an empty stomach, and log it so you see the total.",
    "fried_snacks": "Fried snacks are your main target. Swap the evening samosa or bajji for roasted chana, sprouts chaat or a fruit 3–4 days a week.",
    "late_night": "Late-night eating is your main target. Eat dinner at least 2–3 hours before bed, and keep milk or fruit for real hunger after that.",
    "big_portions": "Portions are your main target. Serve once rather than taking second helpings, and start with the vegetables and dal.",
    "skipping_meals": "Skipped meals are your main target. Skipping usually leads to overeating later, so a small breakfast like idli, poha or eggs helps.",
    "eating_out": "Eating out is your main target. Pick tandoori, grilled or dal-based dishes, share the rice or naan, and ask for less oil.",
    "low_protein": "Protein is your main target. Add one protein item to every meal, and use the picks below.",
}

CONDITION_TIPS = {
    "diabetes": "Carbs are set to 40% of calories. Pair rice or roti with dal, curd or a vegetable, and choose whole grains and millets. Follow your doctor's targets over these.",
    "prediabetes": "Carbs are set to 40% of calories. A 15-minute walk after meals and more fibre can help bring blood sugar down. Talk to your doctor about a check-up.",
    "high_bp": "Keep salt low, about 1 teaspoon a day in total. Pickle, papad, namkeen and instant noodles are the big hidden sources.",
    "thyroid": "Eat meals at regular times, and take thyroid medicine as your doctor advised, usually apart from food.",
    "pcos": "Include protein and fibre at every meal, and limit sugary drinks and refined flour.",
    "cholesterol": "Limit deep-fried food and keep ghee or oil to about 3–4 teaspoons a day. Oats, dal, vegetables and nuts help.",
}

FASTING_TIP = {
    "weekly": "CALARO knows fasting foods like sabudana khichdi, fruit and milk, so log fasting days too.",
    "festivals": "CALARO knows festival fasting foods like sabudana khichdi, fruit and milk, so log fasting days too.",
    "ramadan": "During Ramadan, log sehri and iftar as separate meals so your daily total stays accurate.",
    "intermittent": "Fit your meals inside your eating window. Your calorie target stays the same.",
}

VEGAN_EXCLUDE = {"curd", "curd_rice", "raita", "kadhi", "lassi", "buttermilk", "milk", "payasam", "ghee", "mishti_doi",
                 "rasgulla", "sandesh", "filter_coffee", "chai", "cornflakes", "barfi", "palak_paneer", "kadai_paneer",
                 "paneer_butter_masala", "paneer_tikka", "paneer", "dal_makhani", "butter_naan", "gulab_jamun", "halwa"}
JAIN_EXCLUDE = {"aloo_paratha", "aloo_sabzi", "aloo_gobi", "bonda", "samosa", "vada_pav", "pakora", "pav_bhaji", "kachori",
                "misal_pav", "bhel_puri", "banana_chips"}


SERVING_WORD = {"bowl": "katori", "cup": "cup", "plate": "plate", "glass": "glass", "piece": "piece",
                "handful": "handful", "g": "g", "ml": "ml", "tbsp": "spoon", "tsp": "tsp", "slice": "slice", "packet": "packet"}


def _round5(x: float) -> int:
    return int(round(x / 5.0) * 5)


def bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "underweight"
    if bmi < 23:
        return "healthy"
    if bmi < 25:
        return "overweight"
    return "obese"


def protein_picks(diet: str, lang: str, n: int = 5) -> List[Dict[str, Any]]:
    foods, _ = engine.load_foods()
    picks = []
    for f in foods:
        if "fried" in f.tags or "sweet" in f.tags or f.category in ("drink", "basic", "side"):
            continue
        if diet in ("vegetarian", "vegan", "jain", "eggetarian") and "nonveg" in f.tags:
            continue
        if diet in ("vegetarian", "vegan", "jain") and "egg" in f.tags:
            continue
        if diet == "vegan" and f.id in VEGAN_EXCLUDE:
            continue
        if diet == "jain" and f.id in JAIN_EXCLUDE:
            continue
        kcal, p = f.nutrition["kcal"], f.nutrition["protein"]
        if kcal <= 0 or p < 5:
            continue
        picks.append((p / kcal * 100, f))
    picks.sort(key=lambda t: t[0], reverse=True)
    out, seen = [], set()
    for density, f in picks:
        if f.category in seen and len(out) < n - 1 and len(seen) < 4:
            continue  # prefer variety across categories
        seen.add(f.category)
        item = engine.portion_item(f, None, f.unit, lang)
        out.append({"food_id": f.id, "name": f.name, "native_name": item["native_name"],
                    "serving": f"{item['quantity']:g} {SERVING_WORD.get(f.unit, f.unit)}",
                    "protein": f.nutrition["protein"] if f.unit not in ("g", "ml") else round(f.nutrition["protein"]),
                    "kcal": round(f.nutrition["kcal"])})
        if len(out) >= n:
            break
    return out


def build_plan(a: OnboardingAnswers, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    h_m = a.height_cm / 100
    bmi = a.weight_kg / (h_m ** 2)
    category = bmi_category(bmi)
    healthy_lo, healthy_hi = 18.5 * h_m ** 2, 22.9 * h_m ** 2

    bmr = 10 * a.weight_kg + 6.25 * a.height_cm - 5 * a.age + (5 if a.sex == "male" else -161)
    tdee = bmr * ACTIVITY_FACTOR[a.activity_level]

    # ---- calories
    adjust = 0
    if a.goal == "lose":
        adjust = -250 if a.pace == "gentle" else -500
    elif a.goal == "gain":
        adjust = 250 if a.pace == "gentle" else 400
    elif a.goal == "blood_sugar" and category in ("overweight", "obese"):
        adjust = -250
    floor = 1500 if a.sex == "male" else 1200
    calories = max(floor, tdee + adjust)
    calories = _round5(calories)

    # ---- macros
    ref_weight = min(a.weight_kg, 25 * h_m ** 2)  # don't inflate protein for higher body weight
    per_kg = {"lose": 1.2, "gain": 1.6, "maintain": 1.0, "eat_better": 1.0, "blood_sugar": 1.1}[a.goal]
    if a.age >= 50:
        per_kg += 0.1
    if "low_protein" == a.challenge:
        per_kg = max(per_kg, 1.1)
    protein = round(ref_weight * per_kg)
    sugar_care = a.goal == "blood_sugar" or any(c in a.conditions for c in ("diabetes", "prediabetes", "pcos"))
    carb_pct = 0.40 if sugar_care else 0.50
    carbs = calories * carb_pct / 4
    fat = (calories - protein * 4 - carbs * 4) / 9
    if fat * 9 / calories < 0.20:
        fat = calories * 0.20 / 9
        carbs = (calories - protein * 4 - fat * 9) / 4
    if fat * 9 / calories > 0.35:
        fat = calories * 0.35 / 9
        carbs = (calories - protein * 4 - fat * 9) / 4
    fibre = max(25, round(calories / 1000 * 14))
    if sugar_care or "cholesterol" in a.conditions:
        fibre = max(fibre, 35)
    added_sugar_g = round(calories * 0.05 / 4)

    targets = {"calories": calories, "protein": protein, "carbs": round(carbs), "fat": round(fat), "fibre": fibre,
               "added_sugar_g": added_sugar_g, "water_ml": int(round(a.weight_kg * 35 / 250) * 250)}

    # ---- meal split
    weights = {m: MEAL_WEIGHT[m] for m in a.meals}
    total_w = sum(weights.values())
    meals = [{"meal": m, "label": MEAL_LABEL[m], "calories": _round5(calories * w / total_w)}
             for m, w in sorted(weights.items(), key=lambda kv: list(MEAL_WEIGHT).index(kv[0]))]

    # ---- timeline
    timeline = None
    if a.goal in ("lose", "gain") and a.target_weight_kg:
        rate = {"lose": {"gentle": 0.25, "steady": 0.5}, "gain": {"gentle": 0.2, "steady": 0.35}}[a.goal][a.pace]
        delta = abs(a.weight_kg - a.target_weight_kg)
        weeks = max(1, round(delta / rate))
        timeline = {"from_kg": a.weight_kg, "to_kg": a.target_weight_kg, "kg_per_week": rate, "weeks": weeks,
                    "by_date": (today + timedelta(weeks=weeks)).isoformat()}

    # ---- hidden sugar in tea/coffee
    chai = None
    if a.tea_cups and a.sugar_spoons:
        g_day = a.tea_cups * a.sugar_spoons * 5
        kcal_day = g_day * 4
        chai = {"cups": a.tea_cups, "spoons": a.sugar_spoons, "sugar_g_day": round(g_day), "kcal_day": round(kcal_day),
                "kg_year": round(kcal_day * 365 / 7700, 1), "share_of_sugar_limit": round(g_day / max(added_sugar_g, 1) * 100)}

    # ---- insights, most important first
    insights: List[Dict[str, str]] = []
    bmi_text = {
        "underweight": f"Your BMI is {bmi:.1f}, below the healthy range. A healthy weight for your height is {healthy_lo:.0f}–{healthy_hi:.0f} kg.",
        "healthy": f"Your BMI is {bmi:.1f}, inside the healthy range for Indians (18.5–22.9). A healthy weight for your height is {healthy_lo:.0f}–{healthy_hi:.0f} kg.",
        "overweight": f"Your BMI is {bmi:.1f}. Indian guidelines treat 23 and above as overweight because risk of diabetes starts earlier for South Asians. A healthy weight for your height is {healthy_lo:.0f}–{healthy_hi:.0f} kg.",
        "obese": f"Your BMI is {bmi:.1f}, in the obese range for Indians (25 and above). Losing even 5% of your weight ({a.weight_kg * 0.05:.1f} kg) lowers the risk of diabetes and high blood pressure. A healthy weight for your height is {healthy_lo:.0f}–{healthy_hi:.0f} kg.",
    }[category]
    insights.append({"kind": "body", "title": "Where you are now", "body": bmi_text})

    if a.goal == "lose" and category in ("underweight",) :
        insights.append({"kind": "warn", "title": "Check this goal", "body": "Your weight is already below the healthy range, so losing more isn't advised. Consider setting your goal to maintain or gain."})
    if chai:
        insights.append({"kind": "sugar", "title": "The sugar in your chai",
                         "body": f"{chai['cups']} cups with {chai['spoons']:g} spoon{'s' if chai['spoons'] != 1 else ''} of sugar is about {chai['sugar_g_day']} g of sugar a day, which is {chai['share_of_sugar_limit']}% of your daily added-sugar limit ({added_sugar_g} g). Over a year that's {chai['kcal_day'] * 365:,} kcal, about {chai['kg_year']} kg of weight. Halving the sugar keeps the taste and halves this."})
    for c in a.conditions:
        insights.append({"kind": "health", "title": {"diabetes": "Diabetes", "prediabetes": "Prediabetes", "high_bp": "Blood pressure",
                         "thyroid": "Thyroid", "pcos": "PCOS", "cholesterol": "Cholesterol"}[c], "body": CONDITION_TIPS[c]})
    insights.append({"kind": "focus", "title": "Your focus", "body": CHALLENGE_TIPS[a.challenge]})
    insights.append({"kind": "plate", "title": "Your plate", "body": REGION_SWAPS[a.region]})
    if a.diet in ("vegetarian", "vegan", "jain"):
        insights.append({"kind": "protein", "title": "Protein on a vegetarian diet",
                         "body": f"Many Indian vegetarian meals fall short on protein. Your target is {protein} g a day, about {round(protein / max(1, len(a.meals)))} g per meal. The protein picks in your plan all fit your diet."})
    if a.fasting in FASTING_TIP:
        insights.append({"kind": "fasting", "title": "Fasting days", "body": FASTING_TIP[a.fasting]})

    return {
        "version": 1,
        "created_on": today.isoformat(),
        "bmi": round(bmi, 1),
        "bmi_category": category,
        "healthy_weight_kg": [round(healthy_lo, 1), round(healthy_hi, 1)],
        "bmr": round(bmr),
        "tdee": round(tdee),
        "calorie_adjustment": adjust if calories != floor else round(calories - tdee),
        "targets": targets,
        "carb_pct": int(carb_pct * 100),
        "meals": meals,
        "timeline": timeline,
        "chai": chai,
        "protein_picks": protein_picks(a.diet, a.preferred_language),
        "insights": insights,
        "summary": {"goal": a.goal, "diet": a.diet, "region": a.region, "activity_level": a.activity_level,
                    "conditions": a.conditions, "challenge": a.challenge},
    }
