"""Universal, provider-independent recipe filter model.

A :class:`RecipeFilter` describes *what* the user wants (meal type, diet,
excluded words, max. time, ...). Providers translate whatever they can into
native API parameters, and :meth:`RecipeFilter.reject_reason` applies the rest
on the normalized recipe attributes, so every provider honours every filter.

Filters are merged in layers (global defaults < sensor type preset < sensor
config < service call), see :meth:`RecipeFilter.merged`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from typing import Any

MEAL_TYPES = [
    "any",
    "main",
    "dessert",
    "breakfast",
    "soup",
    "salad",
    "snack",
    "side",
    "drink",
]
DIETS = [
    "vegan",
    "vegetarian",
    "low_carb",
    "low_calorie",
    "low_fat",
    "gluten_free",
]
DIFFICULTIES = ["einfach", "normal", "pfiffig"]
_DIFFICULTY_RANK = {"einfach": 1, "normal": 2, "pfiffig": 3}
SORT_MODES = ["relevance", "rating", "newest"]

# --- Legacy (v3.1) option values from the old search-sensor form ---------------
_LEGACY_MEAL_TYPES = {
    "hauptspeise": "main",
    "vorspeise": "snack",
    "beilage": "side",
    "dessert": "dessert",
    "snack": "snack",
    "frühstück": "breakfast",
}
_LEGACY_DIETS = {
    "vegetarisch": "vegetarian",
    "vegan": "vegan",
    "kalorienarm": "low_calorie",
    "low carb": "low_carb",
    "fettarm": "low_fat",
}
_LEGACY_RATINGS = {"2": 2.0, "3": 3.0, "4": 4.0, "5": 4.5, "top": 4.5}
_LEGACY_SORT = {"bewertung": "rating", "neuheiten": "newest", "empfehlung": "relevance"}

# --- Meal-type heuristics -------------------------------------------------------
# Title words that clearly describe sweet dishes / drinks / baked goods.
_DESSERT_SUFFIXES = (
    "kuchen",
    "torte",
    "törtchen",
    "dessert",
    "nachtisch",
    "nachspeise",
    "kekse",
    "keks",
    "plätzchen",
    "muffin",
    "muffins",
    "brownie",
    "brownies",
    "cupcake",
    "cupcakes",
    "pudding",
    "mousse",
    "tiramisu",
    "cheesecake",
    "crumble",
    "marmelade",
    "konfitüre",
    "kompott",
    "eiscreme",
    "smoothie",
    "cocktail",
    "bowle",
    "punsch",
    "glühwein",
    "likör",
    "gebäck",
    "lebkuchen",
    "stollen",
    "parfait",
    "cookies",
    "cookie",
    "pie",
    "crossies",
    "konfekt",
    "praline",
    "pralinen",
    "fudge",
    "riegel",
)
_DESSERT_EXACT = {
    "eis",
    "creme",
    "brûlée",
    "brulee",
    "süßspeise",
    "süß",
    "süss",
    "sorbet",
}
# "...kuchen" dishes that are savoury and fine for dinner.
_SAVORY_EXCEPTIONS = (
    "pfannkuchen",
    "reibekuchen",
    "kartoffelkuchen",
    "zwiebelkuchen",
    "flammkuchen",
    "speckkuchen",
    "fleischkuchen",
    "hackfleischkuchen",
    "gemüsekuchen",
    "spinatkuchen",
    "lauchkuchen",
    "kürbispie",
    "shepherd",
    "cottage",
    "pot pie",
    "pork pie",
    "steak and",
)
# Breadcrumb/category fragments that are *not* a main dish.
_NON_MAIN_CRUMBS = (
    "dessert",
    "nachspeise",
    "nachtisch",
    "kuchen",
    "torten",
    "torte",
    "eis",
    "süßspeise",
    "cremes",
    "backen & süßspeisen",
    "kekse",
    "plätzchen",
    "getränke",
    "cocktail",
    "shake",
    "bowle",
    "punsch",
    "frühstück",
    "breakfast",
    "aufstrich",
    "saucen & dips",
    "grundrezepte",
    "brot und brötchen",
    "confiserie",
    "gewürzmischung",
)
# Tags that mark sweets / baking (matched on word level against tags + categories).
_NON_MAIN_TAGS = (
    "konfiserie",
    "konfekt",
    "naschen",
    "süßigkeit",
    "süßigkeiten",
    "dessert",
    "nachtisch",
    "nachspeise",
    "gebäck",
    "plätzchen",
    "kuchen",
    "torte",
    "kekse",
)
_MAIN_CRUMBS = ("hauptspeise", "hauptgericht", "main course", "eintopf", "suppen")

# meal -> (breadcrumb fragments, title suffixes/words)
_MEAL_POSITIVE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "dessert": (
        (
            "dessert",
            "nachspeise",
            "kuchen",
            "torte",
            "eis",
            "süßspeise",
            "cremes",
            "kekse",
            "plätzchen",
            "backen & süßspeisen",
        ),
        _DESSERT_SUFFIXES,
    ),
    "breakfast": (
        ("frühstück", "breakfast", "brunch"),
        ("müsli", "porridge", "granola", "frühstück", "brunch", "rührei", "pancakes"),
    ),
    "soup": (
        ("suppe", "eintopf", "soup"),
        ("suppe", "eintopf", "brühe", "soup", "stew"),
    ),
    "salad": (("salat", "salad"), ("salat", "salad", "bowl")),
    "snack": (
        ("snack", "fingerfood", "party", "vorspeise", "starter"),
        ("snack", "dip", "fingerfood", "häppchen", "wrap"),
    ),
    "side": (("beilage", "side"), ("beilage", "kroketten", "püree", "reis")),
    "drink": (
        ("getränke", "cocktail", "shake", "bowle", "punsch", "drink"),
        ("shake", "smoothie", "cocktail", "bowle", "punsch", "limonade", "glühwein"),
    ),
}


def parse_list(value: Any) -> list[str]:
    """Turn a comma/newline separated string (or iterable) into a clean list."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = re.split(r"[,;\n]", value)
    elif isinstance(value, (list, tuple, set)):
        parts = [str(v) for v in value]
    else:
        parts = [str(value)]
    return [p.strip() for p in parts if p and p.strip()]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\wäöüßéèûô]+", text.lower()) if t]


def _crumb_hit(crumbs: str, terms: tuple[str, ...]) -> bool:
    """Match category fragments on word level ("eis" must not match "Reis")."""
    tokens = _tokens(crumbs)
    for term in terms:
        if " " in term or "&" in term:
            if term in crumbs:
                return True
            continue
        for token in tokens:
            if token == term or (len(term) >= 5 and token.startswith(term)):
                return True
    return False


def title_looks_like_dessert(title: str) -> bool:
    """Heuristic: does the recipe title describe a sweet dish / drink / pastry?"""
    low = _norm(title)
    if any(exc in low for exc in _SAVORY_EXCEPTIONS):
        return False
    for token in _tokens(low):
        if token in _DESSERT_EXACT:
            return True
        if any(token.endswith(suffix) for suffix in _DESSERT_SUFFIXES):
            return True
    return False


def parse_minutes(value: Any) -> int | None:
    """Parse '0:25:00', '1 day, 2:00:00', 25 or '25' into minutes."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value) or None
    text = str(value).strip()
    days = 0
    m = re.match(r"(\d+)\s+days?,\s*(.*)", text)
    if m:
        days = int(m.group(1))
        text = m.group(2)
    m = re.match(r"^(\d+):(\d{1,2})(?::(\d{1,2}))?$", text)
    if m:
        total = days * 1440 + int(m.group(1)) * 60 + int(m.group(2))
        return total or None
    if text.isdigit():
        return int(text) or None
    return None


def recipe_minutes(recipe: dict[str, Any]) -> int | None:
    """Best-effort total preparation time of a normalized recipe in minutes."""
    total = parse_minutes(recipe.get("totalTime"))
    if total:
        return total
    parts = [
        parse_minutes(recipe.get(k)) or 0 for k in ("prepTime", "cookTime", "restTime")
    ]
    return sum(parts) or None


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ".")) if value not in (None, "") else None
    except ValueError:
        return None


def _first_int(value: Any) -> int | None:
    m = re.search(r"\d+", str(value or ""))
    return int(m.group(0)) if m else None


@dataclass
class RecipeFilter:
    """Provider-independent description of the recipes the user wants."""

    query: str = ""
    meal_type: str = ""  # "" = not set (inherit); "any" = explicitly unrestricted
    diets: list[str] = field(default_factory=list)
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    exclude_ingredients: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    exclude_categories: list[str] = field(default_factory=list)
    max_total_minutes: int | None = None
    min_rating: float | None = None
    max_difficulty: str = ""
    max_calories: int | None = None
    sort: str = ""
    mode: str = ""  # "daily" = recipe of the day

    # ------------------------------------------------------------------ build
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RecipeFilter:
        """Build a filter from stored options / service data (incl. legacy keys)."""
        data = data or {}
        flt = cls()
        flt.query = str(data.get("query") or data.get("search_query") or "").strip()
        flt.mode = str(data.get("mode") or "")

        # meal type: single string (new) or list of German labels (legacy)
        raw_meal = data.get("meal_type")
        if isinstance(raw_meal, (list, tuple)):
            raw_meal = raw_meal[0] if raw_meal else ""
        raw_meal = _norm(raw_meal)
        flt.meal_type = (
            raw_meal if raw_meal in MEAL_TYPES else _LEGACY_MEAL_TYPES.get(raw_meal, "")
        )

        diets = [_norm(d).replace(" ", "_") for d in parse_list(data.get("diets"))]
        for legacy in parse_list(data.get("health")):
            mapped = _LEGACY_DIETS.get(_norm(legacy))
            if mapped:
                diets.append(mapped)
        flt.diets = [d for d in dict.fromkeys(diets) if d in DIETS]

        flt.include_keywords = parse_list(data.get("include_keywords"))
        flt.exclude_keywords = parse_list(data.get("exclude_keywords"))
        flt.exclude_ingredients = parse_list(data.get("exclude_ingredients"))
        flt.categories = parse_list(data.get("categories")) + parse_list(
            data.get("countries")
        )
        flt.exclude_categories = parse_list(data.get("exclude_categories"))

        max_minutes = data.get("max_total_minutes", data.get("prep_times"))
        flt.max_total_minutes = _first_int(max_minutes) if max_minutes else None

        rating = data.get("min_rating", data.get("ratings"))
        if _norm(rating) in _LEGACY_RATINGS:
            flt.min_rating = _LEGACY_RATINGS[_norm(rating)]
        else:
            flt.min_rating = _to_float(rating)
        if flt.min_rating is not None and flt.min_rating <= 0:
            flt.min_rating = None

        difficulty = _norm(data.get("max_difficulty"))
        flt.max_difficulty = difficulty if difficulty in _DIFFICULTY_RANK else ""
        for prop in parse_list(data.get("properties")):  # legacy
            if _norm(prop) == "einfach" and not flt.max_difficulty:
                flt.max_difficulty = "einfach"
            if _norm(prop) == "schnell" and not flt.max_total_minutes:
                flt.max_total_minutes = 30

        flt.max_calories = _first_int(data.get("max_calories")) or None
        sort = _norm(data.get("sort"))
        flt.sort = sort if sort in SORT_MODES else _LEGACY_SORT.get(sort, "")
        return flt

    def to_dict(self) -> dict[str, Any]:
        """Serialize only the fields that are set."""
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if value not in ("", [], None):
                out[f.name] = list(value) if isinstance(value, list) else value
        return out

    def merged(self, override: RecipeFilter | None) -> RecipeFilter:
        """Return a copy where every field set in *override* wins.

        List fields are replaced when set (not concatenated) so a more specific
        layer can narrow or widen the broader one.
        """
        result = RecipeFilter.from_dict(self.to_dict())
        if override is None:
            return result
        for f in fields(self):
            value = getattr(override, f.name)
            if value not in ("", [], None):
                setattr(
                    result, f.name, list(value) if isinstance(value, list) else value
                )
        return result

    # ------------------------------------------------------------- evaluation
    @property
    def effective_meal_type(self) -> str:
        return self.meal_type or "any"

    def quick_reject(self, candidate: dict[str, Any]) -> str | None:
        """Cheap check on a search *summary* (no detail request needed)."""
        title = str(candidate.get("title") or "")
        if self.effective_meal_type == "main" and title_looks_like_dessert(title):
            return "title looks like dessert/drink"
        low = f"{title} {candidate.get('subtitle') or ''}".lower()
        for word in self.exclude_keywords:
            if _norm(word) in low:
                return f"excluded keyword {word}"
        rating = _to_float(candidate.get("rating"))
        if self.min_rating and rating is not None and rating < self.min_rating:
            return "rating too low"
        return None

    def reject_reason(self, recipe: dict[str, Any]) -> str | None:
        """Return why *recipe* violates the filter, or ``None`` if it passes."""
        title = _norm(recipe.get("title"))
        crumbs_list = [
            _norm(c)
            for c in (recipe.get("category_breadcrumb") or [])
            + [recipe.get("category"), recipe.get("cuisine")]
            if c
        ]
        crumbs = " | ".join(crumbs_list)
        tags = " ".join(_norm(t) for t in (recipe.get("tags") or []))
        ingredients = " ".join(_norm(i) for i in (recipe.get("ingredients") or []))
        haystack = f"{title} {_norm(recipe.get('subtitle'))} {tags} {crumbs}"

        for word in self.exclude_keywords:
            if _norm(word) in haystack:
                return f"excluded keyword '{word}'"
        for word in self.exclude_ingredients:
            if _norm(word) in ingredients or _norm(word) in title:
                return f"excluded ingredient '{word}'"
        if self.include_keywords and not any(
            _norm(w) in f"{haystack} {ingredients}" for w in self.include_keywords
        ):
            return "none of the required keywords found"
        if self.categories and not any(
            _norm(c) in f"{crumbs} {tags}" for c in self.categories
        ):
            return "category not matched"
        for cat in self.exclude_categories:
            if _norm(cat) in crumbs:
                return f"excluded category '{cat}'"

        meal_reason = self._meal_reject(title, crumbs, tags)
        if meal_reason:
            return meal_reason

        minutes = recipe_minutes(recipe)
        if self.max_total_minutes and minutes and minutes > self.max_total_minutes:
            return f"takes {minutes} min (max {self.max_total_minutes})"

        rating = _to_float(recipe.get("rating"))
        if self.min_rating and rating is not None and rating < self.min_rating:
            return f"rating {rating} below {self.min_rating}"

        if self.max_difficulty:
            rank = _DIFFICULTY_RANK.get(_norm(recipe.get("difficulty")))
            if rank and rank > _DIFFICULTY_RANK[self.max_difficulty]:
                return "too difficult"

        if self.max_calories:
            kcal = _first_int(recipe.get("calories"))
            if kcal and kcal > self.max_calories:
                return f"{kcal} kcal above {self.max_calories}"
        return None

    def matches(self, recipe: dict[str, Any]) -> bool:
        return self.reject_reason(recipe) is None

    def _meal_reject(self, title: str, crumbs: str, tags: str = "") -> str | None:
        meal = self.effective_meal_type
        if meal == "any":
            return None
        if meal == "main":
            is_main = _crumb_hit(crumbs, _MAIN_CRUMBS)
            if not is_main and _crumb_hit(crumbs, _NON_MAIN_CRUMBS):
                return "not a main dish (category)"
            if not is_main and _crumb_hit(tags, _NON_MAIN_TAGS):
                return "not a main dish (tags)"
            if not is_main and title_looks_like_dessert(title):
                return "not a main dish (title)"
            return None
        crumb_terms, title_terms = _MEAL_POSITIVE.get(meal, ((), ()))
        if _crumb_hit(crumbs, crumb_terms):
            return None
        title_tokens = _tokens(title)
        if any(tok.endswith(t) for t in title_terms for tok in title_tokens):
            return None
        return f"not a {meal}"
