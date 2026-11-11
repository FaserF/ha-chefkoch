"""Spoonacular provider (official API, free API key required)."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from ..filters import RecipeFilter
from .base import RecipeProvider

_LOGGER = logging.getLogger(__name__)

SEARCH_URL = "https://api.spoonacular.com/recipes/complexSearch"
MEAL_TYPES = {
    "main": "main course",
    "dessert": "dessert",
    "breakfast": "breakfast",
    "soup": "soup",
    "salad": "salad",
    "side": "side dish",
    "snack": "snack",
    "drink": "drink",
}
DIETS = {
    "vegan": "vegan",
    "vegetarian": "vegetarian",
    "gluten_free": "gluten free",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


class SpoonacularProvider(RecipeProvider):
    """Spoonacular recipe search (complex search incl. nutrition)."""

    key = "spoonacular"
    name = "Spoonacular"
    query_language = "en"
    requires_api_key = True

    def search(self, flt: RecipeFilter, limit: int = 10) -> list[dict[str, Any]]:
        if not self.available():
            return []
        params: dict[str, Any] = {
            "apiKey": self.api_key,
            "number": min(limit, 15),
            "addRecipeInformation": "true",
            "addRecipeNutrition": "true",
            "fillIngredients": "true",
            "instructionsRequired": "true",
            "sort": "random",
        }
        query = self.query_for(flt)
        if query:
            params["query"] = query
        meal = MEAL_TYPES.get(flt.effective_meal_type)
        if meal:
            params["type"] = meal
        diets = [DIETS[d] for d in flt.diets if d in DIETS]
        if diets:
            params["diet"] = ",".join(diets)
        if flt.max_total_minutes:
            params["maxReadyTime"] = flt.max_total_minutes
        if flt.max_calories:
            params["maxCalories"] = flt.max_calories
        if flt.exclude_ingredients:
            params["excludeIngredients"] = ",".join(
                self._en(w) for w in flt.exclude_ingredients
            )
        data = self.get_json(SEARCH_URL, params, timeout=12)
        candidates = []
        for item in (data or {}).get("results", []):
            recipe = self._normalize(item)
            candidates.append(
                {
                    "id": str(item.get("id")),
                    "title": recipe["title"],
                    "url": recipe["url"],
                    "rating": recipe.get("rating"),
                    "_recipe": recipe,
                }
            )
        return candidates

    @staticmethod
    def _en(word: str) -> str:
        from .base import translate_query

        return translate_query(word)

    def get_recipe(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if candidate.get("_recipe"):
            return candidate["_recipe"]
        data = self.get_json(
            f"https://api.spoonacular.com/recipes/{candidate['id']}/information",
            {"apiKey": self.api_key, "includeNutrition": "true"},
            timeout=12,
        )
        if not data:
            raise ValueError(f"Spoonacular recipe {candidate['id']} not found")
        return self._normalize(data)

    def _normalize(self, item: dict[str, Any]) -> dict[str, Any]:
        nutrients = {
            n.get("name"): n
            for n in (item.get("nutrition") or {}).get("nutrients", [])
            if isinstance(n, dict)
        }

        def nutrient(name: str, unit: str) -> str:
            n = nutrients.get(name)
            return f"{round(n['amount'])} {unit}" if n and "amount" in n else ""

        steps: list[str] = []
        for block in item.get("analyzedInstructions") or []:
            for step in block.get("steps", []):
                steps.append(
                    f"{step.get('number', len(steps) + 1)}. {step.get('step', '')}"
                )
        instructions = "\n".join(steps) or _strip_html(item.get("instructions", ""))

        ready = item.get("readyInMinutes")
        score = item.get("spoonacularScore")
        crumbs = list(item.get("dishTypes") or []) + list(item.get("diets") or [])
        servings = item.get("servings")
        cuisines = item.get("cuisines") or []
        return self._tag(
            {
                "title": item.get("title", ""),
                "subtitle": "",
                "url": item.get("sourceUrl") or item.get("spoonacularSourceUrl", ""),
                "image_url": item.get("image", ""),
                "calories": nutrient("Calories", "kcal"),
                "protein": nutrient("Protein", "g"),
                "fat": nutrient("Fat", "g"),
                "carbohydrates": nutrient("Carbohydrates", "g"),
                "cuisine": cuisines[0] if cuisines else "",
                "ingredients": [
                    i.get("original", "") for i in item.get("extendedIngredients", [])
                ],
                "instructions": instructions,
                "category": crumbs[0] if crumbs else "",
                "category_breadcrumb": crumbs,
                "servings": f"{servings} Port." if servings else "",
                "author": item.get("sourceName", "") or "Spoonacular",
                "publisher": "Spoonacular",
                "keywords": ", ".join(crumbs),
                "tags": crumbs,
                "totalTime": str(timedelta(minutes=int(ready))) if ready else "",
                "rating": round(score / 20, 1)
                if isinstance(score, (int, float))
                else None,
                "status": "success",
            }
        )
