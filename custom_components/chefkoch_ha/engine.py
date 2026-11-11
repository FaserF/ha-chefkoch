"""Provider-agnostic recipe search engine with layered filters and fallbacks."""

from __future__ import annotations

import logging
import random
from collections.abc import Mapping
from functools import partial
from typing import Any

from .filters import RecipeFilter, parse_list
from .providers import DEFAULT_PROVIDER_ORDER, RecipeProvider, build_providers
from .recipe_fetcher import _get_weather_recipe_query

_LOGGER = logging.getLogger(__name__)

#: Filter defaults used until the user configures "Default filters" in the options.
#: Dinner planning is the main use case, so desserts/baking/drinks are excluded.
DEFAULT_GLOBAL_FILTERS: dict[str, Any] = {"meal_type": "main"}

#: Filter implied by the sensor/recipe type (weaker than the sensor's own settings).
TYPE_PRESETS: dict[str, dict[str, Any]] = {
    "daily": {"mode": "daily"},
    "vegan": {"diets": ["vegan"]},
    "vegetarian": {"diets": ["vegetarian"]},
    "baking": {"query": "backen", "meal_type": "any"},
}
RECIPE_TYPES = [
    "random",
    "weather",
    "daily",
    "vegan",
    "vegetarian",
    "baking",
    "search",
]
RECOMMENDATION_PATTERN = ["weather", "veg", "weather"]


def build_filter(
    options: Mapping[str, Any] | None,
    recipe_type: str = "",
    sensor_cfg: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> RecipeFilter:
    """Merge global defaults < type preset < sensor config < explicit overrides."""
    options = options or {}
    global_cfg = options.get("filters") if "filters" in options else None
    flt = RecipeFilter.from_dict(
        global_cfg if global_cfg is not None else DEFAULT_GLOBAL_FILTERS
    )
    flt = flt.merged(RecipeFilter.from_dict(TYPE_PRESETS.get(recipe_type)))
    flt = flt.merged(RecipeFilter.from_dict(dict(sensor_cfg or {})))
    return flt.merged(RecipeFilter.from_dict(dict(overrides or {})))


def resolve_provider_keys(
    options: Mapping[str, Any] | None,
    sensor_cfg: Mapping[str, Any] | None = None,
    requested: Any = None,
) -> list[str]:
    """Order of providers: service argument > sensor setting > integration options."""
    options = options or {}
    for source in (requested, (sensor_cfg or {}).get("provider")):
        keys = parse_list(source)
        keys = [k for k in keys if k != "auto"]
        if keys:
            return keys
    return parse_list(options.get("providers")) or list(DEFAULT_PROVIDER_ORDER)


def finalize_recipe(
    recipe: dict[str, Any],
    recipe_type: str = "",
    weather_category: str | None = None,
) -> dict[str, Any]:
    """Add the human friendly ``category`` label used in notifications."""
    if weather_category:
        recipe["weather_category"] = weather_category
        recipe["category"] = weather_category
    elif recipe_type == "vegan":
        recipe["diet"] = "Vegan"
        recipe["category"] = "Vegan"
    elif recipe_type == "vegetarian":
        recipe["diet"] = "Vegetarisch"
        recipe["category"] = "Vegetarisch"
    elif not recipe.get("category"):
        crumbs = recipe.get("category_breadcrumb") or []
        recipe["category"] = recipe.get("cuisine") or (
            crumbs[-1] if crumbs else "Klassiker"
        )
    return recipe


def find_recipes_sync(
    providers: list[RecipeProvider],
    flt: RecipeFilter,
    count: int = 1,
    exclude_urls: set[str] | None = None,
    max_checks: int = 14,
) -> list[dict[str, Any]]:
    """Search *providers* in order until *count* recipes pass the filter."""
    seen_urls = set(exclude_urls or ())
    seen_titles: set[str] = set()
    results: list[dict[str, Any]] = []

    for provider in providers:
        try:
            candidates = provider.search(flt)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Provider %s search failed: %s", provider.key, err)
            continue

        special = [c for c in candidates if c.get("daily")]
        rest = [c for c in candidates if not c.get("daily")]
        random.shuffle(rest)
        checks = 0
        for cand in special + rest:
            if len(results) >= count or checks >= max_checks:
                break
            if cand.get("url") in seen_urls:
                continue
            if (reason := flt.quick_reject(cand)) is not None:
                _LOGGER.debug("Skip '%s': %s", cand.get("title"), reason)
                continue
            checks += 1
            try:
                recipe = provider.get_recipe(cand)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Provider %s detail fetch failed: %s", provider.key, err)
                continue
            if recipe.get("status") == "error":
                continue
            title_key = str(recipe.get("title", "")).lower()
            if recipe.get("url") in seen_urls or title_key in seen_titles:
                continue
            if (reason := flt.reject_reason(recipe)) is not None:
                _LOGGER.debug("Reject '%s': %s", recipe.get("title"), reason)
                continue
            results.append(provider.enrich(recipe))
            seen_urls.add(str(recipe.get("url")))
            seen_titles.add(title_key)
        if len(results) >= count:
            break
    return results


async def async_get_recipes(
    hass: Any,
    options: Mapping[str, Any] | None,
    *,
    recipe_type: str = "random",
    sensor_cfg: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
    providers: Any = None,
    count: int = 1,
    exclude_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve *count* recipes for a sensor type / service call.

    ``weather`` types derive a search query from weather + season; other types
    use the layered filter directly.
    """
    options = options or {}
    sensor_cfg = dict(sensor_cfg or {})
    flt = build_filter(options, recipe_type, sensor_cfg, overrides)
    provider_objs = build_providers(
        resolve_provider_keys(options, sensor_cfg, providers), options
    )
    if not provider_objs:
        _LOGGER.warning("No usable recipe provider configured")
        return []

    seen = set(exclude_urls or ())
    run = lambda f, n: hass.async_add_executor_job(  # noqa: E731
        partial(find_recipes_sync, provider_objs, f, n, seen)
    )

    weather_category: str | None = None
    if recipe_type == "weather" and not flt.query:
        recipes: list[dict[str, Any]] = []
        for _ in range(3):
            query, weather_category = await hass.async_add_executor_job(
                _get_weather_recipe_query, hass, sensor_cfg, options
            )
            attempt = RecipeFilter.from_dict({"query": query})
            recipes = await run(flt.merged(attempt), count)
            if recipes:
                break
        if recipes:
            for rec in recipes:
                rec["search_term"] = rec.get("search_term") or query
    else:
        recipes = await run(flt, count)

    return [finalize_recipe(r, recipe_type, weather_category) for r in recipes]
