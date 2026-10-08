"""Short, spoken-friendly meal feedback. Written in simple English so Bhashini
NMT translates it cleanly, then voiced in the user's language."""
from __future__ import annotations

from typing import Dict, List, Optional


def _fmt_qty(q: float) -> str:
    if abs(q - round(q)) < 1e-6:
        return str(int(round(q)))
    if abs(q - 0.5) < 1e-6:
        return "half"
    return f"{q:g}"


UNIT_WORDS = {"bowl": "bowl", "cup": "cup", "plate": "plate", "glass": "glass", "ladle": "ladle",
              "tbsp": "spoon", "tsp": "teaspoon", "handful": "handful", "slice": "slice", "packet": "packet",
              "g": "grams", "ml": "ml", "kg": "kg"}


def describe_item(item: Dict) -> str:
    name = item["name"].split(" / ")[0].split(" (")[0]
    unit = item.get("unit") or "piece"
    q = _fmt_qty(float(item.get("quantity") or 1))
    if unit == "piece":
        return f"{q} {name}"
    word = UNIT_WORDS.get(unit, unit)
    if unit in ("g", "ml", "kg"):
        return f"{q} {word} of {name}"
    return f"{q} {word} of {name}"


def meal_tip(items: List[Dict], meal_totals: Dict[str, float]) -> Optional[str]:
    kcal = meal_totals.get("calories", 0)
    protein = meal_totals.get("protein", 0)
    fibre = meal_totals.get("fibre", 0)
    fried = sum(1 for it in items if "fried" in (it.get("tags") or []))
    sweets = sum(1 for it in items if "sweet" in (it.get("tags") or []))
    if fried >= 2:
        return "Two or more fried items. Next time try a steamed or roasted option."
    if kcal >= 250 and protein < 10:
        return "This meal is low in protein. Add dal, sprouts, curd, paneer or an egg."
    if sweets >= 2:
        return "That is quite a lot of sugar. Try to keep sweets to one serving."
    if kcal >= 350 and fibre < 3:
        return "Add a salad or a vegetable side for more fibre."
    if protein >= 20:
        return "Good protein in this meal. Well done."
    return None


def build_reply(items: List[Dict], meal_totals: Dict[str, float], remaining: Optional[float]) -> str:
    if not items:
        return "Sorry, I could not find any food in that. Please say it again, for example: two idli and one bowl of sambar."
    names = [describe_item(i) for i in items]
    listing = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    parts = [
        f"You had {listing}.",
        f"That is about {int(round(meal_totals['calories']))} calories and {int(round(meal_totals['protein']))} grams of protein.",
    ]
    if remaining is not None:
        if remaining >= 0:
            parts.append(f"After this you have {int(round(remaining))} calories left for today.")
        else:
            parts.append(f"With this you are {int(round(-remaining))} calories over today's goal.")
    tip = meal_tip(items, meal_totals)
    if tip:
        parts.append(tip)
    return " ".join(parts)
