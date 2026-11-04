"""Chefkoch integration for Home Assistant."""

import asyncio
import logging
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


async def async_update_data(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Fetch data from Chefkoch for all configured sensors."""
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
            weather_cat = None
            cfg = dict(sensor_config)
            if sensor_type == "weather":
                weather_query, weather_cat = await hass.async_add_executor_job(
                    _get_weather_recipe_query, hass, sensor_config, entry.options
                )
                cfg["search_query"] = weather_query

            recipe_url = await _fetch_recipe_url(cfg, hass=hass)
            if recipe_url:
                attributes = await hass.async_add_executor_job(
                    extract_recipe_attributes, recipe_url
                )
                if weather_cat:
                    attributes["weather_category"] = weather_cat
                    attributes["search_term"] = cfg.get("search_query")

                data[sensor_id] = attributes
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
            import re

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

    async def handle_generate_meal_plan(call):
        """Generate a multi-day meal plan and fire an event with the results."""
        days = int(call.data.get("days", 7))
        query = call.data.get("query", "").strip() or "Rezept"
        days = max(1, min(days, 7))

        _LOGGER.debug(
            "Service chefkoch_ha.generate_meal_plan called: days=%d, query=%s",
            days,
            query,
        )

        meal_plan: list[dict[str, str]] = []
        sensor_cfg = {"search_query": query}

        for day_index in range(days):
            try:
                url = await _fetch_recipe_url(
                    {"type": "search", **sensor_cfg}, hass=hass
                )
                if url:
                    recipe_id = _get_id_from_url(url)
                    title = ""
                    if recipe_id:
                        try:
                            attrs = await asyncio.to_thread(
                                fetch_recipe_attributes_from_api, recipe_id
                            )
                            title = attrs.get("title", "")
                        except Exception as fetch_err:
                            _LOGGER.debug(
                                "Failed to fetch recipe title for day %d: %s",
                                day_index + 1,
                                fetch_err,
                            )
                    meal_plan.append(
                        {
                            "day": str(day_index + 1),
                            "url": url,
                            "title": title or url,
                        }
                    )
            except Exception as err:
                _LOGGER.warning(
                    "Could not fetch recipe for day %d: %s", day_index + 1, err
                )

        hass.bus.async_fire(
            "chefkoch_meal_plan_generated",
            {"meal_plan": meal_plan, "days": days, "query": query},
        )
        _LOGGER.info(
            "Meal plan generated: %d entries for query '%s'", len(meal_plan), query
        )

    hass.services.async_register(DOMAIN, "refresh_recipe", handle_refresh_recipe)
    hass.services.async_register(
        DOMAIN, "add_to_shopping_list", handle_add_to_shopping_list
    )

    async def _fetch_single_recipe(
        recipe_type: str = "random",
        query: str = "",
        excluded_urls: set[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single fresh recipe and its full attributes directly via API."""
        cfg = {"type": recipe_type}
        if query:
            cfg["search_query"] = query
        weather_cat = None
        if recipe_type == "weather":
            w_query, weather_cat = await hass.async_add_executor_job(
                _get_weather_recipe_query, hass, cfg, entry.options
            )
            cfg["search_query"] = w_query

        url = None
        for _ in range(3):
            url = await _fetch_recipe_url(cfg, hass=hass)
            if url and (not excluded_urls or url not in excluded_urls):
                break

        if not url:
            return {
                "title": "No recipe found",
                "url": "",
                "status": "warning",
                "error_message": "No matching recipe found.",
            }

        attributes = await hass.async_add_executor_job(extract_recipe_attributes, url)
        if weather_cat:
            attributes["weather_category"] = weather_cat
            attributes["category"] = weather_cat
        elif recipe_type == "vegan":
            attributes["diet"] = "Vegan"
            attributes["category"] = "Vegan"
        elif recipe_type == "vegetarian":
            attributes["diet"] = "Vegetarisch"
            attributes["category"] = "Vegetarisch"
        elif attributes.get("cuisine"):
            attributes["category"] = attributes["cuisine"]
        elif attributes.get("category_breadcrumb"):
            attributes["category"] = attributes["category_breadcrumb"][-1]
        else:
            attributes["category"] = "Klassiker"
        return attributes

    async def handle_get_recipe(call):
        """Fetch a single fresh recipe and return it in service response."""
        recipe_type = call.data.get("recipe_type", "random")
        query = call.data.get("query", "").strip()
        recipe = await _fetch_single_recipe(recipe_type=recipe_type, query=query)
        return {"recipe": recipe}

    async def handle_get_recommendations(call):
        """Fetch 3 curated recipes (Weather #1, Vegan/Veg #2, Weather #3) and return them."""
        import random

        r1 = await _fetch_single_recipe(recipe_type="weather")
        excluded: set[str] = set()
        if r1.get("url"):
            excluded.add(str(r1["url"]))

        veg_type = random.choice(["vegan", "vegetarian"])
        r2 = await _fetch_single_recipe(recipe_type=veg_type, excluded_urls=excluded)
        if r2.get("url"):
            excluded.add(str(r2["url"]))

        r3 = await _fetch_single_recipe(recipe_type="weather", excluded_urls=excluded)

        return {
            "recipe_1": r1,
            "recipe_2": r2,
            "recipe_3": r3,
            "recipes": [r1, r2, r3],
        }

    hass.services.async_register(
        DOMAIN, "generate_meal_plan", handle_generate_meal_plan
    )
    hass.services.async_register(
        DOMAIN,
        "get_recipe",
        handle_get_recipe,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "get_recommendations",
        handle_get_recommendations,
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
