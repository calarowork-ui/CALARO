"""
CALARO Vaani nutrition engine.

Turns a meal description (native script, romanised "Tanglish/Hinglish", or the
English translation from Bhashini) into structured items backed by the curated
Indian food database in ``app/data/indian_foods.json``.

Design goals
  * Deterministic first: dictionary + portion maths, no LLM guessing.
  * Works on native script directly (Tamil agglutination like "இட்லியும்" is
    handled with prefix matching), so it still works if translation is off.
  * Indian household portions: katori, ladle, tumbler, plate, handful ...
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "indian_foods.json"

# --------------------------------------------------------------------------
# Languages (Bhashini codes) shown in the UI
# --------------------------------------------------------------------------
LANGUAGES: List[Dict[str, str]] = [
    {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    {"code": "ta", "name": "Tamil", "native": "தமிழ்"},
    {"code": "te", "name": "Telugu", "native": "తెలుగు"},
    {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ"},
    {"code": "ml", "name": "Malayalam", "native": "മലയാളം"},
    {"code": "bn", "name": "Bengali", "native": "বাংলা"},
    {"code": "mr", "name": "Marathi", "native": "मराठी"},
    {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી"},
    {"code": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    {"code": "or", "name": "Odia", "native": "ଓଡ଼ିଆ"},
    {"code": "as", "name": "Assamese", "native": "অসমীয়া"},
    {"code": "ur", "name": "Urdu", "native": "اردو"},
    {"code": "en", "name": "English", "native": "English"},
]
LANGUAGE_CODES = {lang["code"] for lang in LANGUAGES}

# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------
NUMBER_WORDS: Dict[str, float] = {
    # English
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "half": 0.5, "quarter": 0.25, "couple": 2, "dozen": 12, "single": 1, "double": 2,
    "few": 3, "some": 1,
    # Romanised Hindi / Tamil / Telugu / Kannada / Malayalam / Bengali
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "aadha": 0.5, "adha": 0.5, "dedh": 1.5, "dhai": 2.5,
    "oru": 1, "onnu": 1, "ondru": 1, "rendu": 2, "irandu": 2, "moonu": 3, "munu": 3, "naalu": 4, "nalu": 4, "anju": 5, "ainthu": 5, "arai": 0.5,
    "okati": 1, "moodu": 3, "nalugu": 4, "aidu": 5,
    "ondu": 1, "eradu": 2, "mooru": 3, "naalku": 4, "ardha": 0.5,
    "onn": 1, "randu": 2, "moonnu": 3, "anchu": 5,
    "dui": 2, "tin": 3,
    # Hindi
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "आधा": 0.5, "आधी": 0.5, "डेढ़": 1.5, "ढाई": 2.5, "दर्जन": 12,
    # Marathi
    "दोन": 2, "पाच": 5, "सहा": 6, "नऊ": 9, "दहा": 10, "अर्धा": 0.5, "अर्धी": 0.5, "दीड": 1.5, "अडीच": 2.5,
    # Tamil
    "ஒரு": 1, "ஒன்று": 1, "ஒண்ணு": 1, "இரண்டு": 2, "ரெண்டு": 2, "இரு": 2, "மூன்று": 3, "மூணு": 3, "நான்கு": 4, "நாலு": 4,
    "ஐந்து": 5, "அஞ்சு": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10, "அரை": 0.5,
    # Telugu
    "ఒక": 1, "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "ఆరు": 6, "ఏడు": 7, "ఎనిమిది": 8,
    "తొమ్మిది": 9, "పది": 10, "అర": 0.5, "ఒక్క": 1,
    # Kannada
    "ಒಂದು": 1, "ಒಂದ": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5, "ಆರು": 6, "ಏಳು": 7, "ಎಂಟು": 8,
    "ಒಂಬತ್ತು": 9, "ಹತ್ತು": 10, "ಅರ್ಧ": 0.5,
    # Malayalam
    "ഒരു": 1, "ഒന്ന്": 1, "രണ്ട്": 2, "രണ്ടു": 2, "മൂന്ന്": 3, "നാല്": 4, "അഞ്ച്": 5, "ആറ്": 6, "ഏഴ്": 7,
    "എട്ട്": 8, "ഒമ്പത്": 9, "പത്ത്": 10, "അര": 0.5,
    # Bengali / Assamese
    "এক": 1, "একটা": 1, "একটি": 1, "দুই": 2, "দুটো": 2, "দুটি": 2, "তিন": 3, "তিনটে": 3, "তিনটি": 3, "চার": 4, "চারটে": 4,
    "পাঁচ": 5, "পাঁচটা": 5, "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10, "আধা": 0.5, "হাফ": 0.5, "দেড়": 1.5, "আড়াই": 2.5,
    # Gujarati
    "એક": 1, "બે": 2, "ત્રણ": 3, "ચાર": 4, "પાંચ": 5, "છ": 6, "સાત": 7, "આઠ": 8, "નવ": 9, "દસ": 10,
    "અડધી": 0.5, "અડધો": 0.5, "અડધું": 0.5, "દોઢ": 1.5, "અઢી": 2.5,
    # Punjabi
    "ਇੱਕ": 1, "ਇਕ": 1, "ਦੋ": 2, "ਤਿੰਨ": 3, "ਚਾਰ": 4, "ਪੰਜ": 5, "ਅੱਧਾ": 0.5, "ਅੱਧੀ": 0.5,
    # Odia
    "ଗୋଟେ": 1, "ଏକ": 1, "ଦୁଇ": 2, "ତିନି": 3, "ଚାରି": 4, "ପାଞ୍ଚ": 5, "ଅଧା": 0.5,
}

# Size modifiers multiply the serving
SIZE_WORDS: Dict[str, float] = {
    "small": 0.7, "chhota": 0.7, "chota": 0.7, "chinna": 0.7, "medium": 1.0, "regular": 1.0,
    "large": 1.4, "big": 1.4, "bada": 1.4, "periya": 1.4, "full": 1.0,
    "छोटा": 0.7, "छोटी": 0.7, "बड़ा": 1.4, "बड़ी": 1.4, "சின்ன": 0.7, "பெரிய": 1.4,
    "చిన్న": 0.7, "పెద్ద": 1.4, "ಸಣ್ಣ": 0.7, "ದೊಡ್ಡ": 1.4, "ചെറിയ": 0.7, "വലിയ": 1.4,
    "ছোট": 0.7, "বড়": 1.4, "નાની": 0.7, "નાનો": 0.7, "મોટી": 1.4, "મોટો": 1.4,
}

# --------------------------------------------------------------------------
# Units (canonical unit -> spoken synonyms) and default grams per unit
# --------------------------------------------------------------------------
UNIT_SYNONYMS: Dict[str, List[str]] = {
    "piece": ["piece", "pieces", "pc", "pcs", "nos", "no", "number", "item", "items",
              "पीस", "नग", "துண்டு", "ముక్క", "ತುಂಡು", "കഷണം", "টুকরো", "পিস", "ટુકડો", "નંગ"],
    "bowl": ["bowl", "bowls", "katori", "katoris", "katora", "vati", "vaati", "kinnam", "cup of", "serving", "servings", "portion", "portions",
             "कटोरी", "कटोरा", "वाटी", "கிண்ணம்", "கப்", "గిన్నె", "ಬಟ್ಟಲು", "ಬೌಲ್", "പാത്രം", "ബൗൾ", "বাটি", "વાટકી", "ਕਟੋਰੀ"],
    "cup": ["cup", "cups", "कप", "కప్పు", "ಕಪ್", "കപ്പ്", "কাপ", "કપ"],
    "plate": ["plate", "plates", "thali", "thaali", "prato", "प्लेट", "थाली", "தட்டு", "ప్లేట్", "ಪ್ಲೇಟ್", "പ്ലേറ്റ്", "প্লেট", "থালা", "પ્લેટ", "થાળી"],
    "glass": ["glass", "glasses", "tumbler", "tumblers", "lota", "गिलास", "ग्लास", "டம்ளர்", "கிளாஸ்", "గ్లాసు", "గ్లాస్", "ಲೋಟ",
              "ಗ್ಲಾಸ್", "ഗ്ലാസ്", "গ্লাস", "ગ્લાસ", "ਗਲਾਸ"],
    "ladle": ["ladle", "ladles", "karandi", "kalchul", "karchi", "gariti", "करछी", "கரண்டி", "గరిటె", "ಸೌಟು", "തവി", "হাতা"],
    "tbsp": ["tbsp", "tablespoon", "tablespoons", "spoon", "spoons", "chamach", "chammach", "चम्मच", "ஸ்பூன்", "చెంచా", "ಚಮಚ", "സ്പൂൺ",
             "চামচ", "ચમચી", "ਚਮਚ"],
    "tsp": ["tsp", "teaspoon", "teaspoons"],
    "handful": ["handful", "handfuls", "mutthi", "muthi", "मुट्ठी", "கைப்பிடி", "గుప్పెడు", "ಹಿಡಿ", "പിടി", "মুঠো", "મુઠ્ઠી"],
    "slice": ["slice", "slices", "स्लाइस"],
    "packet": ["packet", "packets", "pack", "पैकेट"],
    "g": ["g", "gm", "gms", "gram", "grams", "gr", "ग्राम", "கிராம்", "గ్రాములు", "ಗ್ರಾಂ", "ഗ്രാം", "গ্রাম", "ગ્રામ"],
    "kg": ["kg", "kilo", "kilogram", "किलो"],
    "ml": ["ml", "millilitre", "milliliter", "मिली"],
}
UNIT_LOOKUP: Dict[str, str] = {syn.lower(): unit for unit, syns in UNIT_SYNONYMS.items() for syn in syns}

GENERIC_UNIT_GRAMS: Dict[str, float] = {
    "bowl": 150, "cup": 150, "plate": 250, "glass": 200, "ladle": 60, "tbsp": 15, "tsp": 5,
    "handful": 30, "slice": 25, "packet": 70, "g": 1, "kg": 1000, "ml": 1,
}

UNIT_LABELS: Dict[str, str] = {
    "piece": "piece", "bowl": "katori / bowl", "cup": "cup", "plate": "plate", "glass": "glass / tumbler",
    "ladle": "ladle", "tbsp": "tbsp", "tsp": "tsp", "handful": "handful", "slice": "slice",
    "packet": "packet", "g": "grams", "kg": "kg", "ml": "ml",
}

INDIC_RANGES = re.compile(r"[ऀ-෿਀-૿؀-ۿ]")
TOKEN_RE = re.compile(r"[^\s]+", re.UNICODE)


@dataclass
class FoodEntry:
    id: str
    name: str
    category: str
    unit: str
    grams: float
    plate_servings: Optional[float]
    nutrition: Dict[str, float]
    tags: List[str]
    aliases: Dict[str, List[str]]

    def per_gram(self) -> Dict[str, float]:
        return {k: (v / self.grams if self.grams else 0.0) for k, v in self.nutrition.items()}

    def unit_grams(self) -> Dict[str, float]:
        """Grams represented by one of each unit, for this specific dish."""
        table = dict(GENERIC_UNIT_GRAMS)
        if self.unit not in ("g", "ml"):
            table[self.unit] = self.grams
        if self.unit in ("piece", "slice"):
            table["piece"] = self.grams
            table["plate"] = self.grams * (self.plate_servings or 2)
        elif self.plate_servings:
            table["plate"] = self.grams * self.plate_servings
        if self.unit == "glass":
            table["cup"] = 150
        return table

    def native_name(self, lang: str) -> Optional[str]:
        names = self.aliases.get(lang) or []
        return names[0] if names else None


@lru_cache(maxsize=1)
def load_foods() -> Tuple[List[FoodEntry], List[Tuple[str, str, FoodEntry]]]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    foods: List[FoodEntry] = []
    index: List[Tuple[str, str, FoodEntry]] = []  # (alias_normalised, lang, entry)
    for f in raw["foods"]:
        entry = FoodEntry(
            id=f["id"], name=f["name"], category=f["category"],
            unit=f["serving"]["unit"], grams=float(f["serving"]["grams"]),
            plate_servings=f["serving"].get("plate_servings"),
            nutrition={k: float(v) for k, v in f["nutrition"].items()},
            tags=f.get("tags", []), aliases=f["aliases"],
        )
        foods.append(entry)
        seen = set()
        for lang, names in entry.aliases.items():
            for name in names + ([entry.name] if lang == "en" else []):
                norm = normalise(name)
                if norm and (norm, entry.id) not in seen:
                    seen.add((norm, entry.id))
                    index.append((norm, lang, entry))
    # Longest alias first so "curd rice" beats "rice", "masala dosa" beats "dosa"
    index.sort(key=lambda t: len(t[0]), reverse=True)
    return foods, index


def get_food(food_id: str) -> Optional[FoodEntry]:
    foods, _ = load_foods()
    for f in foods:
        if f.id == food_id:
            return f
    return None


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    text = text.replace("‌", "").replace("‍", "")  # ZWNJ / ZWJ
    text = re.sub(r"[“”\"'`’,;:!?()\[\]{}|।॥]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _to_number(token: str) -> Optional[float]:
    t = token.lower()
    if t in NUMBER_WORDS:
        return float(NUMBER_WORDS[t])
    try:
        return float(t)
    except ValueError:
        pass
    # Indic digits (०१२, ௧௨, ౧౨ ...)
    if all(unicodedata.digit(ch, None) is not None for ch in t):
        return float("".join(str(unicodedata.digit(ch)) for ch in t))
    # Tamil/Kannada etc. inflected number words: "ரெண்டு" + suffix
    for word, val in NUMBER_WORDS.items():
        if len(word) >= 3 and INDIC_RANGES.search(word) and t.startswith(word) and len(t) - len(word) <= 3:
            return float(val)
    return None


def _to_unit(token: str) -> Optional[str]:
    t = token.lower()
    if t in UNIT_LOOKUP:
        return UNIT_LOOKUP[t]
    if INDIC_RANGES.search(t):
        for syn, unit in UNIT_LOOKUP.items():
            if len(syn) >= 2 and INDIC_RANGES.search(syn) and t.startswith(syn) and len(t) - len(syn) <= 4:
                return unit
    return None


@dataclass
class Match:
    start: int
    end: int
    entry: FoodEntry
    alias: str


def _find_matches(text: str) -> List[Match]:
    _, index = load_foods()
    matches: List[Match] = []
    taken = [False] * len(text)
    for alias, _lang, entry in index:
        if len(alias) < 2:
            continue
        indic = bool(INDIC_RANGES.search(alias))
        if indic:
            # Prefix match at a token start (handles இட்லியும், रोटियाँ ...)
            pattern = r"(?:(?<=\s)|^)" + re.escape(alias)
        else:
            pattern = r"\b" + re.escape(alias) + r"(?:s|es)?\b"
        for m in re.finditer(pattern, text):
            s, e = m.start(), m.end()
            if any(taken[s:e]):
                continue
            # extend to end of the token for Indic suffixes so they don't leak into the next match
            if indic:
                while e < len(text) and not text[e].isspace():
                    e += 1
            for i in range(s, e):
                taken[i] = True
            matches.append(Match(s, e, entry, alias))
    matches.sort(key=lambda m: m.start)
    return matches


def _tokens_between(text: str, start: int, end: int) -> List[str]:
    return TOKEN_RE.findall(text[start:end])


def _quantity_context(text: str, match: Match, prev_end: int, next_start: int) -> Tuple[Optional[float], Optional[str], float]:
    """Look left (then right) of a food mention for a number, unit and size word."""
    qty: Optional[float] = None
    unit: Optional[str] = None
    size = 1.0

    left = _tokens_between(text, prev_end, match.start)[-4:]
    for tok in reversed(left):
        low = tok.lower()
        if unit is None and _to_unit(low):
            unit = _to_unit(low)
            continue
        if low in SIZE_WORDS:
            size = SIZE_WORDS[low]
            continue
        n = _to_number(low)
        if n is not None and qty is None:
            qty = n
            continue
        if low in {"of", "ka", "ki", "ke", "with", "and", "aur", "plus"}:
            continue
    # "one and a half", "saade teen" (3.5), "सवा दो" (2.25)
    window = text[prev_end:match.start].lower()
    m_half = re.search(r"(\S+)\s+and\s+(?:a\s+)?half", window)
    if m_half and _to_number(m_half.group(1)) is not None:
        qty = _to_number(m_half.group(1)) + 0.5
    elif qty is not None and re.search(r"(\bsaade\b|साढ़े|সাড়ে)", window):
        qty += 0.5
    elif qty is not None and re.search(r"(\bsava\b|सवा)", window):
        qty += 0.25

    if qty is None:
        right = _tokens_between(text, match.end, next_start)[:3]
        for tok in right:
            low = tok.lower()
            n = _to_number(low)
            if n is not None:
                qty = n
                continue
            if unit is None and _to_unit(low):
                unit = _to_unit(low)
    return qty, unit, size


def default_quantity(entry: FoodEntry) -> float:
    return entry.grams if entry.unit in ("g", "ml") else 1.0


def portion_item(entry: FoodEntry, quantity: Optional[float], unit: Optional[str], lang: str = "en") -> Dict:
    if quantity is None:
        quantity = default_quantity(entry) if (unit in (None, entry.unit)) else 1.0
    unit = unit or entry.unit
    unit_grams = entry.unit_grams()
    if unit not in unit_grams:
        unit = entry.unit
    grams = max(quantity, 0) * unit_grams[unit]
    per_g = entry.per_gram()
    nut = {k: round(v * grams, 1) for k, v in per_g.items()}
    return {
        "food_id": entry.id,
        "name": entry.name,
        "native_name": entry.native_name(lang) if lang != "en" else None,
        "quantity": round(quantity, 2),
        "unit": unit,
        "grams": round(grams, 1),
        "calories": round(nut.get("kcal", 0.0)),
        "protein": nut.get("protein", 0.0),
        "carbs": nut.get("carbs", 0.0),
        "fat": nut.get("fat", 0.0),
        "fibre": nut.get("fibre", 0.0),
        "matched": True,
        "source": "calaro-db",
        "tags": entry.tags,
        "unit_grams": {u: round(g, 1) for u, g in unit_grams.items() if u in UNIT_LABELS},
        "per_gram": {k: round(v, 5) for k, v in per_g.items()},
    }


def parse_meal(text: str, lang: str = "en") -> List[Dict]:
    """Extract food items from free text in any supported language."""
    norm = normalise(text)
    if not norm:
        return []
    matches = _find_matches(norm)
    items: List[Dict] = []
    for i, m in enumerate(matches):
        prev_end = matches[i - 1].end if i > 0 else 0
        next_start = matches[i + 1].start if i + 1 < len(matches) else len(norm)
        qty, unit, size = _quantity_context(norm, m, prev_end, next_start)
        items.append(portion_item(m.entry, None if qty is None and size == 1.0 else (qty or 1.0) * size, unit, lang))
    return _merge_duplicates(items)


def _merge_duplicates(items: List[Dict]) -> List[Dict]:
    merged: Dict[Tuple[str, str], Dict] = {}
    order: List[Tuple[str, str]] = []
    for it in items:
        key = (it["food_id"], it["unit"])
        if key in merged:
            m = merged[key]
            m["quantity"] = round(m["quantity"] + it["quantity"], 2)
            for k in ("grams", "calories", "protein", "carbs", "fat", "fibre"):
                m[k] = round(m[k] + it[k], 1)
        else:
            merged[key] = dict(it)
            order.append(key)
    return [merged[k] for k in order]


def combine_native_and_english(native_items: List[Dict], english_items: List[Dict]) -> List[Dict]:
    """Native-script parse is authoritative for *what* was eaten when it finds
    things; the English translation fills in foods the native parse missed."""
    if not native_items:
        return english_items
    have = {it["food_id"] for it in native_items}
    extra = [it for it in english_items if it["food_id"] not in have]
    return native_items + extra


def search_foods(query: str, lang: str = "en", limit: int = 12) -> List[Dict]:
    q = normalise(query)
    foods, index = load_foods()
    if not q:
        results = foods[:limit]
    else:
        scored: Dict[str, Tuple[int, FoodEntry]] = {}
        for alias, _l, entry in index:
            if alias.startswith(q):
                score = 0
            elif q in alias:
                score = 1
            else:
                continue
            if entry.id not in scored or scored[entry.id][0] > score:
                scored[entry.id] = (score, entry)
        results = [e for _, e in sorted(scored.values(), key=lambda t: (t[0], t[1].name))][:limit]
    return [portion_item(e, None, e.unit, lang) for e in results]


def totals(items: List[Dict]) -> Dict[str, float]:
    out = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fibre": 0.0}
    for it in items:
        for k in out:
            out[k] += float(it.get(k) or 0)
    return {k: round(v, 1) for k, v in out.items()}
