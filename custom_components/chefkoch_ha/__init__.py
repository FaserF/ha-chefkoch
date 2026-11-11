"""Chefkoch integration for Home Assistant."""

import asyncio
import logging
import random
import re
from datetime import timedelta
from typing import Any

from get_chefkoch import Search  # noqa: F401
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

try:
    from homeassistant.core import SupportsResponse
except ImportError:

    class SupportsResponse:  # type: ignore[no-redef]
        NONE = "none"
        OPTIONAL = "optional"
        ONLY = "only"


from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .engine import (
    RECOMMENDATION_PATTERN,
    async_get_recipes,
)
from .filters import parse_list
from .formatting import render_recipes
from .parser import (
    _get_id_from_url,
    _scale_ingredient,
    extract_recipe_attributes,
    fetch_recipe_attributes_from_api,
    fetch_recipe_comments_from_api,
)
from .recipe_fetcher import (
    _fetch_recipe_url,
    _get_daily_url,
    _get_search_url,
    _get_weather_recipe_query,
)

_LOGGER = logging.getLogger(__name__)

# Keep for backwards compatibility
__all__ = [
    "DOMAIN",
    "_fetch_recipe_url",
    "_get_daily_url",
    "_get_id_from_url",
    "_get_search_url",
    "_get_weather_recipe_query",
    "_scale_ingredient",
    "async_setup_entry",
    "async_unload_entry",
    "async_update_data",
    "extract_recipe_attributes",
    "fetch_recipe_attributes_from_api",
    "fetch_recipe_comments_from_api",
    "options_update_listener",
]

#: Service fields forwarded 1:1 into the layered recipe filter.
FILTER_KEYS = (
    "query",
    "meal_type",
    "diets",
    "include_keywords",
    "exclude_keywords",
    "exclude_ingredients",
    "categories",
    "exclude_categories",
    "max_total_minutes",
    "min_rating",
    "max_difficulty",
    "max_calories",
    "sort",
)
MAX_RESULTS = 20


def _filter_overrides(data: Any) -> dict[str, Any]:
    """Extract the filter fields a service call actually set."""
    return {
        key: data[key]
        for key in FILTER_KEYS
        if key in data and data[key] not in (None, "", [])
    }


def _render(recipes: list[dict[str, Any]], data: Any) -> dict[str, str]:
    """Build the ``message_*`` fields (title-as-link, one recipe per line)."""
    details = data.get("details")
    rendered = render_recipes(
        [r for r in recipes if r.get("url")],
        header=str(data.get("header") or ""),
        footer=str(data.get("footer") or ""),
        numbering=str(data.get("numbering") or "emoji"),
        details=parse_list(details) if details is not None else None,
    )
    return {f"message_{key}": value for key, value in rendered.items()}


def _no_recipe() -> dict[str, Any]:
    return {
        "title": "No recipe found",
        "url": "",
        "status": "warning",
        "error_message": "No matching recipe found.",
    }


async def async_update_data(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Fetch data from the configured providers for all configured sensors."""
    sensors: list[dict[str, Any]] = entry.options.get("sensors", [])
    if not sensors:
        return {}

    # Get current data to prevent flickering during partial updates
    current_data: dict[str, Any] = {}

    # 1. Try active coordinator
    if (
        DOMAIN in hass.data
        and entry.entry_id in hass.data[DOMAIN]
        and "coordinator" in hass.data[DOMAIN][entry.entry_id]
    ):
        current_data = hass.data[DOMAIN][entry.entry_id]["coordinator"].data or {}

    # 2. Try persistent cache (survives reloads)
    if not current_data:
        current_data = hass.data.get(DOMAIN, {}).get(f"cache_{entry.entry_id}", {})

    data: dict[str, Any] = dict(current_data)

    async def fetch_and_process_sensor(sensor_config: dict[str, Any]) -> None:
        sensor_id = sensor_config["id"]
        sensor_name = sensor_config.get(CONF_NAME, f"Chefkoch Sensor {sensor_id}")
        sensor_type = sensor_config.get("type", "")

        try:
            recipes = await async_get_recipes(
                hass,
                entry.options,
                recipe_type=sensor_type or "search",
                sensor_cfg=sensor_config,
            )
            if recipes:
                data[sensor_id] = recipes[0]
            else:
                _LOGGER.warning("No recipe found for sensor %s", sensor_name)
                if sensor_id not in data:
                    data[sensor_id] = {
                        "title": "No recipe found",
                        "status": "warning",
                        "error_message": "No matching recipe found.",
                    }
        except Exception as e:
            _LOGGER.exception(
                "Error during data fetching for sensor %s",
                sensor_name,
            )
            if sensor_id not in data:
                data[sensor_id] = {
                    "title": "Error fetching data",
                    "status": "error",
                    "error_message": str(e),
                }

    tasks = [fetch_and_process_sensor(s) for s in sensors]
    await asyncio.gather(*tasks)
    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    update_interval_hours = entry.options.get(
        "update_interval", DEFAULT_UPDATE_INTERVAL
    )
    scan_interval = timedelta(hours=update_interval_hours)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Chefkoch Recipe Coordinator",
        update_method=lambda: async_update_data(hass, entry),
        update_interval=scan_interval,
    )

    cached_data = hass.data.get(DOMAIN, {}).get(f"cache_{entry.entry_id}")
    if cached_data:
        coordinator.data = cached_data

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}
    hass.data[DOMAIN][f"cache_{entry.entry_id}"] = coordinator.data

    async def handle_refresh_recipe(call):
        """Handle the service call to refresh recipes."""
        _LOGGER.debug("Service chefkoch_ha.refresh_recipe called")
        await coordinator.async_refresh()

    async def handle_add_to_shopping_list(call):
        """Add ingredients of a recipe to the shopping list."""
        entity_id = call.data.get("entity_id")
        target_servings = call.data.get("servings")
        state = hass.states.get(entity_id)
        if not state:
            _LOGGER.error("Entity %s not found", entity_id)
            return

        ingredients = state.attributes.get("ingredients", [])
        if not ingredients:
            _LOGGER.warning("No ingredients found for entity %s", entity_id)
            return

        scale_factor = 1.0
        if target_servings and isinstance(target_servings, (int, float)):
            orig_servings_str = str(state.attributes.get("servings", ""))
            m = re.search(r"\d+", orig_servings_str)
            if m:
                try:
                    orig_servings = int(m.group(0))
                    if orig_servings > 0:
                        scale_factor = float(target_servings) / float(orig_servings)
                except ValueError:
                    pass

        for ingredient in ingredients:
            item_name = (
                _scale_ingredient(ingredient, scale_factor)
                if scale_factor != 1.0
                else ingredient
            )
            await hass.services.async_call(
                "shopping_list", "add_item", {"name": item_name}
            )
        _LOGGER.info(
            "Added %d ingredients to shopping list (scaled factor: %s)",
            len(ingredients),
            scale_factor,
        )

    async def _get_recipes(
        recipe_type: str,
        data: Any,
        count: int = 1,
        exclude_urls: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Resolve recipes for a service call (filters + providers from call data)."""
        return await async_get_recipes(
            hass,
            entry.options,
            recipe_type=recipe_type,
            overrides=_filter_overrides(data),
            providers=data.get("providers") or data.get("provider"),
            count=count,
            exclude_urls=exclude_urls,
        )

    async def handle_generate_meal_plan(call):
        """Generate a multi-day meal plan and fire an event with the results."""
        data = call.data
        days = max(1, min(int(data.get("days", 7)), 7))
        query = str(data.get("query") or "").strip()
        recipe_type = str(data.get("recipe_type") or "search")

        _LOGGER.debug(
            "Service chefkoch_ha.generate_meal_plan called: days=%d, query=%s",
            days,
            query,
        )

        meal_plan: list[dict[str, Any]] = []
        recipes_out: list[dict[str, Any]] = []
        seen: set[str] = set()
        call_data = dict(data)
        for day_index in range(days):
            try:
                recipes = await _get_recipes(recipe_type, call_data, 1, set(seen))
            except Exception as err:
                _LOGGER.warning(
                    "Could not fetch recipe for day %d: %s", day_index + 1, err
                )
                continue
            if not recipes:
                continue
            recipe = recipes[0]
            seen.add(str(recipe.get("url")))
            recipes_out.append(recipe)
            meal_plan.append(
                {
                    "day": str(day_index + 1),
                    "url": recipe.get("url", ""),
                    "title": recipe.get("title") or recipe.get("url", ""),
                    "category": recipe.get("category", ""),
                }
            )

        messages = _render(recipes_out, data)
        hass.bus.async_fire(
            "chefkoch_meal_plan_generated",
            {"meal_plan": meal_plan, "days": days, "query": query, **messages},
        )
        _LOGGER.info(
            "Meal plan generated: %d entries for query '%s'", len(meal_plan), query
        )
        return {"meal_plan": meal_plan, "recipes": recipes_out, **messages}

    async def handle_get_recipe(call):
        """Fetch fresh recipe(s) matching the given filters and return them."""
        data = call.data
        recipe_type = data.get("recipe_type", "random")
        count = max(1, min(int(data.get("count", 1) or 1), MAX_RESULTS))
        recipes = await _get_recipes(recipe_type, data, count)
        recipe = recipes[0] if recipes else _no_recipe()
        return {
            "recipe": recipe,
            "recipes": recipes,
            "count": len(recipes),
            **_render(recipes, data),
        }

    async def handle_search_recipes(call):
        """Universal search: any provider, any filter, 1..N results."""
        data = call.data
        count = max(1, min(int(data.get("count", 5) or 5), MAX_RESULTS))
        recipes = await _get_recipes(data.get("recipe_type", "search"), data, count)
        return {"recipes": recipes, "count": len(recipes), **_render(recipes, data)}

    async def handle_get_recommendations(call):
        """Fetch N distinct curated recipes (default: weather, vegan/veg, weather)."""
        data = call.data
        count = max(1, min(int(data.get("count", 3) or 3), MAX_RESULTS))
        types = parse_list(data.get("recipe_types")) or RECOMMENDATION_PATTERN

        recipes: list[dict[str, Any]] = []
        excluded: set[str] = set()
        for i in range(count):
            recipe_type = types[i % len(types)]
            if recipe_type == "veg":
                recipe_type = random.choice(["vegan", "vegetarian"])
            found = await _get_recipes(recipe_type, data, 1, excluded)
            recipe = found[0] if found else _no_recipe()
            if recipe.get("url"):
                excluded.add(str(recipe["url"]))
            recipes.append(recipe)

        result: dict[str, Any] = {f"recipe_{i + 1}": r for i, r in enumerate(recipes)}
        result["recipes"] = recipes
        result["count"] = len(recipes)
        result.update(_render(recipes, data))
        return result

    async def handle_get_recipe_details(call):
        """Load the full details of a Chefkoch recipe URL or id."""
        ref = str(call.data.get("url") or call.data.get("recipe_id") or "")
        recipe_id = _get_id_from_url(ref) or (ref if ref.isdigit() else None)
        if not recipe_id:
            return {"recipe": _no_recipe()}
        recipe = await hass.async_add_executor_job(
            extract_recipe_attributes, f"https://www.chefkoch.de/rezepte/{recipe_id}/"
        )
        return {"recipe": recipe}

    async def handle_format_recipes(call):
        """Render a list of recipes (e.g. from a previous response) for messaging."""
        recipes = call.data.get("recipes") or []
        return {"count": len(recipes), **_render(list(recipes), call.data)}

    hass.services.async_register(DOMAIN, "refresh_recipe", handle_refresh_recipe)
    hass.services.async_register(
        DOMAIN, "add_to_shopping_list", handle_add_to_shopping_list
    )
    hass.services.async_register(
        DOMAIN,
        "generate_meal_plan",
        handle_generate_meal_plan,
        supports_response=SupportsResponse.OPTIONAL,
    )
    for name, handler in (
        ("get_recipe", handle_get_recipe),
        ("search_recipes", handle_search_recipes),
        ("get_recommendations", handle_get_recommendations),
        ("get_recipe_details", handle_get_recipe_details),
        ("format_recipes", handle_format_recipes),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            supports_response=SupportsResponse.OPTIONAL,
        )

    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
