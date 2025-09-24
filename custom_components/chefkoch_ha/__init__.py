import asyncio
import logging
from datetime import timedelta
from homeassistant import config_entries, core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from chefkoch.retrievers import DailyRecipeRetriever, RandomRetriever, SearchRetriever
from chefkoch import Recipe

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(days=1)


async def async_update_data(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    """Fetch data from Chefkoch for all configured sensors."""
    sensors = entry.options.get("sensors", [])
    if not sensors:
        return {}

    data = {}

    async def fetch_and_process_sensor(sensor_config):
        sensor_id = sensor_config["id"]
        try:
            recipe_url = await _fetch_recipe_url(sensor_config)
            if recipe_url:
                attributes = await hass.async_add_executor_job(extract_recipe_attributes, recipe_url)
                data[sensor_id] = attributes
            else:
                _LOGGER.warning("No recipe found for sensor %s", sensor_config['name'])
                data[sensor_id] = {"title": "No recipe found", "status": "error"}
        except Exception as e:
            _LOGGER.error("Error during data fetching for sensor %s: %s", sensor_config['name'], e, exc_info=True)
            data[sensor_id] = {"title": "Error fetching URL", "status": "error", "error_message": str(e)}

    tasks = [fetch_and_process_sensor(s) for s in sensors]
    await asyncio.gather(*tasks)
    return data

async def _fetch_recipe_url(sensor_config: dict) -> str | None:
    """Fetch the recipe URL based on sensor config."""
    sensor_type = sensor_config["type"]
    retriever = None
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
            recipes = await asyncio.to_thread(retriever.get_recipes, search_query="vegan")
            return recipes[0].url if recipes and recipes[0] else None

        elif sensor_type == "search":
            search_query = sensor_config.get("search_query", "")

            # Helper to parse comma-separated strings into lists
            def parse_list(key):
                value = sensor_config.get(key, "")
                return [item.strip() for item in value.split(',') if item.strip()] if value else None

            init_params = {
                "properties": parse_list("properties"),
                "health": parse_list("health"),
                "categories": parse_list("categories"),
                "countries": parse_list("countries"),
                "meal_type": parse_list("meal_type"),
                "prep_times": sensor_config.get("prep_times"),
                "ratings": sensor_config.get("ratings"),
                "sort": sensor_config.get("sort")
            }

            init_params = {k: v for k, v in init_params.items() if v}

            retriever = SearchRetriever(**init_params)
            recipes = await asyncio.to_thread(retriever.get_recipes, search_query=search_query)
            return recipes[0].url if recipes and recipes[0] else None

        return None
    finally:
        if retriever:
            await asyncio.to_thread(retriever.close)


def extract_recipe_attributes(recipe_url):
    """Extract all attributes from a recipe URL robustly."""
    try:
        recipe = Recipe(recipe_url)
    except Exception as e:
        _LOGGER.error("Failed to initialize Recipe object for URL %s: %s", recipe_url, e)
        return {"title": "Error loading recipe details", "url": recipe_url, "status": "error", "error_message": f"Could not parse recipe page: {e}"}

    def safe_get_attr(recipe_obj, attr_name, default=None):
        try:
            return getattr(recipe_obj, attr_name)
        except Exception:
            _LOGGER.debug("Could not get attribute '%s' for recipe %s", attr_name, recipe_obj.url)
            return default

    return {
        "title": safe_get_attr(recipe, 'title', 'Title not found'),
        "url": recipe.url,
        "image_url": safe_get_attr(recipe, 'image_url', ''),
        "totalTime": safe_get_attr(recipe, 'total_time', '0'),
        "prepTime": safe_get_attr(recipe, 'prep_time', ''),
        "cookTime": safe_get_attr(recipe, 'cook_time', ''),
        "restTime": safe_get_attr(recipe, 'rest_time', ''),
        "calories": safe_get_attr(recipe, 'calories', ''),
        "difficulty": safe_get_attr(recipe, 'difficulty', ''),
        "ingredients": safe_get_attr(recipe, 'ingredients', []),
        "instructions": safe_get_attr(recipe, 'instructions', ''),
        "category": safe_get_attr(recipe, 'category', ''),
        "servings": safe_get_attr(recipe, 'servings', ''),
        "rating": (safe_get_attr(recipe, 'rating') or {}).get('rating'),
        "rating_count": (safe_get_attr(recipe, 'rating') or {}).get('count'),
        "status": "success",
    }

async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="Chefkoch Recipe Coordinator",
        update_method=lambda: async_update_data(hass, entry),
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}
    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def options_update_listener(hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
