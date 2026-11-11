"""TheMealDB provider (free public JSON API, English recipes, no key needed)."""

from __future__ import annotations

import random
from typing import Any

from ..filters import RecipeFilter
from .base import RecipeProvider

BASE_URL = "https://www.themealdb.com/api/json/v1/1"
MAIN_CATEGORIES = [
    "Beef",
    "Chicken",
    "Lamb",
    "Pasta",
    "Pork",
    "Seafood",
    "Goat",
    "Miscellaneous",
]
MEAL_CATEGORIES = {
    "dessert": ["Dessert"],
    "breakfast": ["Breakfast"],
    "side": ["Side"],
    "snack": ["Starter"],
    "salad": ["Vegetarian"],
}


class TheMealDBProvider(RecipeProvider):
    """Free international recipe API."""

    key = "themealdb"
    name = "TheMealDB"
    query_language = "en"

    def search(self, flt: RecipeFilter, limit: int = 30) -> list[dict[str, Any]]:
        query = self.query_for(flt)
        candidates: list[dict[str, Any]] = []

        if query:
            for term in [query, *query.split()]:
                data = self.get_json(f"{BASE_URL}/search.php", {"s": term})
                meals = (data or {}).get("meals") or []
                if meals:
                    candidates.extend(self._full_candidate(m) for m in meals)
                    break
            if not candidates:  # fall back to an ingredient search
                for term in query.split():
                    data = self.get_json(f"{BASE_URL}/filter.php", {"i": term})
                    candidates.extend(
                        self._summary_candidate(m)
                        for m in (data or {}).get("meals") or []
                    )
                    if candidates:
                        break
            return candidates[:limit]

        categories: list[str]
        if "vegan" in flt.diets:
            categories = ["Vegan"]
        elif "vegetarian" in flt.diets:
            categories = ["Vegetarian"]
        elif flt.effective_meal_type in MEAL_CATEGORIES:
            categories = MEAL_CATEGORIES[flt.effective_meal_type]
        else:
            categories = random.sample(MAIN_CATEGORIES, 2)

        for category in categories:
            data = self.get_json(f"{BASE_URL}/filter.php", {"c": category})
            candidates.extend(
                self._summary_candidate(m) for m in (data or {}).get("meals") or []
            )
        random.shuffle(candidates)
        return candidates[:limit]

    @staticmethod
    def _summary_candidate(meal: dict[str, Any]) -> dict[str, Any]:
        mid = str(meal.get("idMeal"))
        return {
            "id": mid,
            "title": meal.get("strMeal", ""),
            "url": f"https://www.themealdb.com/meal/{mid}",
        }

    def _full_candidate(self, meal: dict[str, Any]) -> dict[str, Any]:
        cand = self._summary_candidate(meal)
        cand["_recipe"] = self._normalize(meal)
        return cand

    def get_recipe(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if candidate.get("_recipe"):
            return candidate["_recipe"]
        data = self.get_json(f"{BASE_URL}/lookup.php", {"i": candidate["id"]})
        meals = (data or {}).get("meals") or []
        if not meals:
            raise ValueError(f"TheMealDB recipe {candidate['id']} not found")
        return self._normalize(meals[0])

    def _normalize(self, meal: dict[str, Any]) -> dict[str, Any]:
        ingredients = []
        for i in range(1, 21):
            name = (meal.get(f"strIngredient{i}") or "").strip()
            if not name:
                continue
            measure = (meal.get(f"strMeasure{i}") or "").strip()
            ingredients.append(f"{measure} {name}".strip())
        tags = [t.strip() for t in (meal.get("strTags") or "").split(",") if t.strip()]
        crumbs = [c for c in (meal.get("strCategory"), meal.get("strArea")) if c]
        mid = str(meal.get("idMeal"))
        return self._tag(
            {
                "title": meal.get("strMeal", ""),
                "subtitle": "",
                "url": f"https://www.themealdb.com/meal/{mid}",
                "image_url": meal.get("strMealThumb", ""),
                "video_url": meal.get("strYoutube", "") or "",
                "source_url": meal.get("strSource", "") or "",
                "cuisine": meal.get("strArea", ""),
                "ingredients": ingredients,
                "instructions": (meal.get("strInstructions") or "").strip(),
                "category": meal.get("strCategory", ""),
                "category_breadcrumb": crumbs,
                "author": "TheMealDB",
                "publisher": "TheMealDB",
                "keywords": ", ".join(tags),
                "tags": tags,
                "status": "success",
            }
        )
