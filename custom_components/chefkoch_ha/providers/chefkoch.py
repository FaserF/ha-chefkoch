"""Chefkoch.de provider (official v2 REST API)."""

from __future__ import annotations

import logging
import random
from typing import Any

from ..const import CHEFKOCH_BASE_URL
from ..filters import RecipeFilter
from ..parser import (
    _get_id_from_url,
    fetch_recipe_attributes_from_api,
    fetch_recipe_comments_from_api,
)
from .base import RecipeProvider

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://api.chefkoch.de/v2/recipes"

# Chefkoch category ids (GET /v2/recipes/categories) usable as server-side filter.
DIET_CATEGORY_IDS = {
    "vegan": "111",
    "vegetarian": "39",
    "low_calorie": "37",
    "low_fat": "36",
}
MEAL_CATEGORY_IDS = {
    "main": "9",
    "dessert": "19",
    "breakfast": "31",
    "soup": "5",
    "salad": "20",
    "side": "26",
    "snack": "83",
    "drink": "102",
}
ORDER_BY = {"rating": "3", "newest": "1"}


class ChefkochProvider(RecipeProvider):
    """Search and fetch recipes from Chefkoch."""

    key = "chefkoch"
    name = "Chefkoch"
    query_language = "de"

    def search(self, flt: RecipeFilter, limit: int = 40) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if flt.mode == "daily":
            candidates.extend(self._daily_candidates())

        params: dict[str, str] = {"limit": str(limit)}
        if flt.query:
            params["query"] = flt.query

        category = next(
            (DIET_CATEGORY_IDS[d] for d in flt.diets if d in DIET_CATEGORY_IDS), ""
        )
        meal = flt.effective_meal_type
        if not category and meal in MEAL_CATEGORY_IDS:
            # "main" with a free-text query is filtered client-side to keep the pool big
            if meal != "main" or not flt.query:
                category = MEAL_CATEGORY_IDS[meal]
        if category:
            params["categories"] = category
        if not flt.query and not category:
            params["query"] = "Rezept"
        if flt.min_rating:
            params["minimumRating"] = f"{flt.min_rating:g}"
        if flt.sort in ORDER_BY:
            params["orderBy"] = ORDER_BY[flt.sort]

        data: Any = None
        for offset in (random.randint(0, 30), 0):
            data = self.get_json(API_BASE_URL, {**params, "offset": str(offset)})
            if data and data.get("results"):
                break

        for item in (data or {}).get("results", []):
            rec = item.get("recipe") or {}
            rid = rec.get("id")
            if not rid or rec.get("isPlus") or rec.get("isPremium"):
                continue
            raw_rating = rec.get("rating")
            rating: dict[str, Any] = raw_rating if isinstance(raw_rating, dict) else {}
            candidates.append(
                {
                    "id": str(rid),
                    "title": rec.get("title", ""),
                    "subtitle": rec.get("subtitle", ""),
                    "url": rec.get("siteUrl") or f"{CHEFKOCH_BASE_URL}{rid}/",
                    "rating": rating.get("rating"),
                    "difficulty": rec.get("difficulty"),
                }
            )
        return candidates

    def _daily_candidates(self) -> list[dict[str, Any]]:
        from ..recipe_fetcher import _get_daily_url

        try:
            url, title = _get_daily_url()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Daily recipe lookup failed: %s", err)
            return []
        rid = _get_id_from_url(url)
        if not rid:
            return []
        return [{"id": rid, "title": title or "", "url": url, "daily": True}]

    def get_recipe(self, candidate: dict[str, Any]) -> dict[str, Any]:
        recipe = fetch_recipe_attributes_from_api(
            str(candidate["id"]), include_comments=False
        )
        return self._tag(recipe)

    def enrich(self, recipe: dict[str, Any]) -> dict[str, Any]:
        rid = _get_id_from_url(recipe.get("url"))
        if rid and not recipe.get("top_comments"):
            recipe["top_comments"] = fetch_recipe_comments_from_api(rid, limit=5)
        return recipe
