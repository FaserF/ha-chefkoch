import asyncio
import logging
import random
from datetime import timedelta
from typing import Any

from get_chefkoch import Recipe, Search

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CHEFKOCH_BASE_URL = "https://www.chefkoch.de/rezepte/"


async def async_update_data(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
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
    """Fetch the recipe URL based on sensor config using get_chefkoch."""
    sensor_type = sensor_config["type"]

    try:
        if sensor_type == "daily":
            searcher = Search()
            recipe = await asyncio.to_thread(searcher.recipeOfTheDay)
            return f"{CHEFKOCH_BASE_URL}{recipe.id}/" if recipe else None

        elif sensor_type == "random":
            # Random: search with empty query, pick a random result
            searcher = Search()
            recipes = await asyncio.to_thread(searcher.recipes, limit=100)
            if recipes:
                return f"{CHEFKOCH_BASE_URL}{random.choice(recipes).id}/"
            return None

        elif sensor_type == "vegan":
            searcher = Search("vegan")
            recipes = await asyncio.to_thread(searcher.recipes, limit=10)
            if recipes:
                return f"{CHEFKOCH_BASE_URL}{random.choice(recipes).id}/"
            return None

        elif sensor_type == "vegetarian":
            searcher = Search("vegetarisch")
            recipes = await asyncio.to_thread(searcher.recipes, limit=10)
            if recipes:
                return f"{CHEFKOCH_BASE_URL}{random.choice(recipes).id}/"
            return None

        elif sensor_type == "baking":
            searcher = Search("backen")
            recipes = await asyncio.to_thread(searcher.recipes, limit=10)
            if recipes:
                return f"{CHEFKOCH_BASE_URL}{random.choice(recipes).id}/"
            return None

        elif sensor_type == "search":
            search_query = sensor_config.get("search_query", "")
            searcher = Search(search_query if search_query else None)
            recipes = await asyncio.to_thread(searcher.recipes, limit=10)
            if recipes:
                return f"{CHEFKOCH_BASE_URL}{random.choice(recipes).id}/"
            return None

        return None

    except Exception as e:
        _LOGGER.error(
            "Error fetching recipe URL for sensor type %s: %s", sensor_type, e
        )
        return None


def extract_recipe_attributes(recipe_url: str) -> dict[str, Any]:
    """Extract all attributes from a recipe URL using get_chefkoch."""
    try:
        recipe = Recipe(recipe_url)
        _LOGGER.debug("Successfully loaded recipe for URL %s.", recipe_url)
    except Exception as e:
        _LOGGER.error("Failed to load recipe for URL %s: %s", recipe_url, e)
        return {
            "title": "Error loading recipe",
            "url": recipe_url,
            "status": "error",
            "error_message": f"Could not parse recipe page: {e}",
        }

    # get_chefkoch uses data_dump() for full structured data
    raw: dict[str, Any] = recipe.data_dump() or {}

    def safe(key: str, default: Any = "") -> Any:
        val = raw.get(key)
        return val if val is not None else default

    # Name cleanup: strip "von <User>" suffix
    name: str = recipe.name or safe("name", "")
    if " von " in name:
        name = name.split(" von ")[0].strip()

    # Rating
    agg = safe("aggregateRating", {})
    rating_value = agg.get("ratingValue") if isinstance(agg, dict) else None
    rating_count = agg.get("ratingCount") if isinstance(agg, dict) else None
    review_count = agg.get("reviewCount") if isinstance(agg, dict) else None

    # Author
    author_raw = safe("author", {})
    if isinstance(author_raw, dict):
        author = author_raw.get("name", "")
    elif isinstance(author_raw, list) and author_raw:
        author = author_raw[0].get("name", "")
    else:
        author = ""

    # Nutrition
    nutrition = safe("nutrition", {})
    calories = nutrition.get("calories", "") if isinstance(nutrition, dict) else ""
    protein = nutrition.get("proteinContent", "") if isinstance(nutrition, dict) else ""
    fat = nutrition.get("fatContent", "") if isinstance(nutrition, dict) else ""
    carbohydrates = nutrition.get("carbohydrateContent", "") if isinstance(nutrition, dict) else ""

    # Times — get_chefkoch provides timedelta objects directly as attributes
    def fmt_time(val: Any) -> str:
        if val is None:
            return ""
        return str(val)

    attributes: dict[str, Any] = {
        "title": name,
        "url": recipe_url,
        "image_url": recipe.image or "",
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbohydrates": carbohydrates,
        "cuisine": safe("recipeCuisine", ""),
        "video_url": safe("video", {}).get("contentUrl", "") if isinstance(safe("video"), dict) else "",
        "difficulty": safe("difficulty", ""),
        "ingredients": recipe.ingredients or [],
        "instructions": safe("recipeInstructions", ""),
        "category": recipe.category or "",
        "servings": safe("recipeYield", ""),
        "author": author,
        "publisher": safe("publisher", {}).get("name", "")
        if isinstance(safe("publisher"), dict)
        else "",
        "keywords": safe("keywords", ""),
        "date_published": str(safe("datePublished", "")),
        "status": "success",
        "totalTime": fmt_time(recipe.totalTime),
        "prepTime": fmt_time(recipe.prepTime),
        "cookTime": fmt_time(recipe.cookTime),
        "restTime": "",
        "rating": rating_value,
        "rating_count": rating_count,
        "number_ratings": rating_count,
        "number_reviews": review_count,
    }

    _LOGGER.debug("Extracted attributes for recipe %s.", recipe_url)
    return attributes


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

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    async def handle_refresh_recipe(call):
        """Handle the service call to refresh recipes."""
        _LOGGER.debug("Service chefkoch_ha.refresh_recipe called")
        await coordinator.async_refresh()

    async def handle_add_to_shopping_list(call):
        """Add ingredients of a recipe to the shopping list."""
        entity_id = call.data.get("entity_id")
        state = hass.states.get(entity_id)
        if not state:
            _LOGGER.error("Entity %s not found", entity_id)
            return

        ingredients = state.attributes.get("ingredients", [])
        if not ingredients:
            _LOGGER.warning("No ingredients found for entity %s", entity_id)
            return

        for ingredient in ingredients:
            await hass.services.async_call(
                "shopping_list", "add_item", {"name": ingredient}
            )
        _LOGGER.info("Added %d ingredients to shopping list", len(ingredients))

    hass.services.async_register(DOMAIN, "refresh_recipe", handle_refresh_recipe)
    hass.services.async_register(
        DOMAIN, "add_to_shopping_list", handle_add_to_shopping_list
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
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
