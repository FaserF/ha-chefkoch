import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant import config_entries, core
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from chefkoch.retrievers import DailyRecipeRetriever, RandomRetriever, SearchRetriever
from chefkoch import Recipe

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_update_data(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> dict[str, Any]:
    """Fetch data from Chefkoch for all configured sensors."""
    sensors: list[dict[str, Any]] = entry.options.get("sensors", [])
    if not sensors:
        return {}

    data: dict[str, Any] = {}

    async def fetch_and_process_sensor(sensor_config: dict[str, Any]) -> None:
        sensor_id = sensor_config["id"]
        sensor_name = sensor_config.get(CONF_NAME, f"Chefkoch Sensor {sensor_id}")

        try:
            recipe_url = await _fetch_recipe_url(sensor_config)
            if recipe_url:
                attributes = await hass.async_add_executor_job(
                    extract_recipe_attributes, recipe_url
                )
                data[sensor_id] = attributes
            else:
                _LOGGER.warning("No recipe found for sensor %s", sensor_name)
                data[sensor_id] = {
                    "title": "No recipe found",
                    "status": "warning",
                    "error_message": "No matching recipe found.",
                }
        except Exception as e:
            _LOGGER.error(
                "Error during data fetching for sensor %s: %s",
                sensor_name,
                e,
                exc_info=True,
            )
            data[sensor_id] = {
                "title": "Error fetching data",
                "status": "error",
                "error_message": str(e),
            }

    tasks = [fetch_and_process_sensor(s) for s in sensors]
    await asyncio.gather(*tasks)
    return data


async def _fetch_recipe_url(sensor_config: dict[str, Any]) -> str | None:
    """Fetch the recipe URL based on sensor config."""
    sensor_type = sensor_config["type"]
    retriever: Any = None

    try:
        if sensor_type == "random":
            retriever = RandomRetriever()
            recipe = await asyncio.to_thread(retriever.get_recipe)
            return recipe.url if recipe else None

        elif sensor_type == "daily":
            retriever = DailyRecipeRetriever()
            recipes = await asyncio.to_thread(retriever.get_recipes, type="kochen")
            return recipes[0].url if recipes and recipes[0] else None

        elif sensor_type == "vegan":
            retriever = SearchRetriever(health=["Vegan"])
            recipes = await asyncio.to_thread(
                retriever.get_recipes, search_query="vegan"
            )
            # In some cases, the search might return fewer results than expected or different structures
            return recipes[0].url if recipes and recipes[0] else None

        elif sensor_type == "baking":
            retriever = DailyRecipeRetriever()
            recipes = await asyncio.to_thread(retriever.get_recipes, type="backen")
            return recipes[0].url if recipes and recipes[0] else None

        elif sensor_type == "vegetarian":
            retriever = SearchRetriever(health=["Vegetarisch"])
            recipes = await asyncio.to_thread(
                retriever.get_recipes, search_query="vegetarisch"
            )
            return recipes[0].url if recipes and recipes[0] else None

        elif sensor_type == "search":
            search_query = sensor_config.get("search_query", "")

            # Helper to parse comma-separated strings into lists
            def parse_list(key: str) -> list[str] | None:
                value = sensor_config.get(key, "")
                if not value:
                    return None
                return [item.strip() for item in value.split(",") if item.strip()]

            init_params = {
                "properties": parse_list("properties"),
                "health": parse_list("health"),
                "categories": parse_list("categories"),
                "countries": parse_list("countries"),
                "meal_type": parse_list("meal_type"),
                "prep_times": sensor_config.get("prep_times"),
                "ratings": sensor_config.get("ratings"),
                "sort": sensor_config.get("sort"),
            }

            # Remove None values
            filtered_params = {k: v for k, v in init_params.items() if v}

            retriever = SearchRetriever(**filtered_params)
            recipes = await asyncio.to_thread(
                retriever.get_recipes, search_query=search_query
            )
            return recipes[0].url if recipes and recipes[0] else None

        return None
    finally:
        # Some retrievers might implement a close method, ensuring we call it if it exists.
        # Note: python-chefkoch retrievers might not all have 'close', but good practice if updated.
        if retriever and hasattr(retriever, "close"):
            await asyncio.to_thread(retriever.close)


def extract_recipe_attributes(recipe_url: str) -> dict[str, Any]:
    """Extract all attributes from a recipe URL robustly."""
    try:
        # Initialize Recipe object from the dependency
        recipe = Recipe(recipe_url)
        _LOGGER.debug("Successfully initialized Recipe object for URL %s.", recipe_url)
    except Exception as e:
        _LOGGER.error(
            "Failed to initialize Recipe object for URL %s: %s", recipe_url, e
        )
        return {
            "title": "Error loading recipe",
            "url": recipe_url,
            "status": "error",
            "error_message": f"Could not parse recipe page: {e}",
        }

    def safe_get_attr(recipe_obj: Any, attr_name: str, default: Any = None) -> Any:
        """Safely get an attribute from the recipe object."""
        try:
            return getattr(recipe_obj, attr_name)
        except Exception as e:
            _LOGGER.debug(
                "Could not get attribute '%s' for recipe %s. Error: %s",
                attr_name,
                recipe_obj.url,
                e,
            )
            return default

    # Extract all attributes and build the data dictionary
    title = safe_get_attr(recipe, "title", "Title not found")
    # Cleanup titles that might include "von <User>"
    if title and " von " in title:
        title = title.split(" von ")[0]

    attributes = {
        "title": title,
        "url": recipe.url,
        "image_url": safe_get_attr(recipe, "image_url", ""),
        "calories": safe_get_attr(recipe, "calories", ""),
        "difficulty": safe_get_attr(recipe, "difficulty", ""),
        "ingredients": safe_get_attr(recipe, "ingredients", []),
        "instructions": safe_get_attr(recipe, "instructions", ""),
        "category": safe_get_attr(recipe, "category", ""),
        "servings": safe_get_attr(recipe, "servings", ""),
        "author": safe_get_attr(recipe, "author", ""),
        "publisher": safe_get_attr(recipe, "publisher", ""),
        "keywords": safe_get_attr(recipe, "keywords", ""),
        "date_published": str(safe_get_attr(recipe, "date_published", "")),
        "status": "success",
    }

    # Handle time attributes
    for time_attr, key in [
        ("total_time", "totalTime"),
        ("prep_time", "prepTime"),
        ("cook_time", "cookTime"),
        ("rest_time", "restTime"),
    ]:
        val = safe_get_attr(recipe, time_attr)
        attributes[key] = str(val) if val else ""

    # Handle rating
    rating_info = safe_get_attr(recipe, "rating")
    if isinstance(rating_info, dict):
        attributes["rating"] = rating_info.get("rating")
        attributes["rating_count"] = rating_info.get("count")
    else:
        attributes["rating"] = rating_info
        attributes["rating_count"] = None

    # Additional rating statistics
    attributes["number_ratings"] = safe_get_attr(recipe, "number_ratings", None)
    attributes["number_reviews"] = safe_get_attr(recipe, "number_reviews", None)

    _LOGGER.debug("Extracted attributes for recipe %s.", recipe.url)
    return attributes


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
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

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
