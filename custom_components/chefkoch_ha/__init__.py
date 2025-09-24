import asyncio
import logging
from datetime import timedelta
from homeassistant import config_entries, core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
                # Use hass.async_add_executor_job to run the blocking I/O in a thread
                attributes = await hass.async_add_executor_job(extract_recipe_attributes, recipe_url)
                data[sensor_id] = attributes
            else:
                _LOGGER.warning("No recipe found for sensor %s", sensor_config['name'])
                data[sensor_id] = {"title": "No recipe found", "status": "error"}
        except Exception as e:
            _LOGGER.error("Error fetching data for sensor %s: %s", sensor_config['name'], e, exc_info=True)
            data[sensor_id] = {"title": "Error", "status": "error", "error_message": str(e)}

    # Create a list of tasks to run concurrently
    tasks = [fetch_and_process_sensor(s) for s in sensors]
    await asyncio.gather(*tasks)

    return data

async def _fetch_recipe_url(sensor_config: dict) -> str | None:
    """Fetch the recipe URL based on sensor config."""
    sensor_type = sensor_config["type"]

    if sensor_type == "random":
        retriever = RandomRetriever()
        recipe = await asyncio.to_thread(retriever.get_recipe)
        return recipe.url if recipe else None

    elif sensor_type == "daily":
        retriever = DailyRecipeRetriever()
        recipes = await asyncio.to_thread(retriever.get_recipes, type="kochen")
        return recipes[0].url if recipes else None

    elif sensor_type == "vegan":
        retriever = SearchRetriever(health=["Vegan"])
        recipes = await asyncio.to_thread(retriever.get_recipes, search_query="vegan")
        return recipes[0].url if recipes else None

    elif sensor_type == "search":
        search_query = sensor_config.get("search_query", "")
        init_params = {
            "category": sensor_config.get("category"),
            "difficulty": sensor_config.get("difficulty")
        }
        # Filter out None or empty values for the constructor
        init_params = {k: v for k, v in init_params.items() if v}

        retriever = SearchRetriever(**init_params)
        recipes = await asyncio.to_thread(retriever.get_recipes, search_query=search_query)
        return recipes[0].url if recipes else None

    return None

def extract_recipe_attributes(recipe_url):
    """Extract all attributes from a recipe URL."""
    try:
        recipe = Recipe(recipe_url)
        # Corrected attribute names from camelCase to snake_case
        return {
            "title": getattr(recipe, 'title', 'Unknown'),
            "url": recipe.url,
            "image_url": getattr(recipe, 'image_url', ''),
            "totalTime": getattr(recipe, 'total_time', 0),
            "prepTime": getattr(recipe, 'prep_time', 0),
            "cookTime": getattr(recipe, 'cook_time', 0),
            "restTime": getattr(recipe, 'rest_time', 0),
            "calories": getattr(recipe, 'calories', None),
            "difficulty": getattr(recipe, 'difficulty', ''),
            "ingredients": getattr(recipe, 'ingredients', []),
            "instructions": getattr(recipe, 'instructions', ''),
            "category": getattr(recipe, 'category', ''),
            "servings": getattr(recipe, 'servings', None),
            "rating": getattr(recipe, 'rating', {}).get('rating'),
            "rating_count": getattr(recipe, 'rating', {}).get('count'),
            "status": "success",
        }
    except Exception as e:
        _LOGGER.error(f"Failed to extract attributes for URL {recipe_url}: {e}")
        return {"status": "error", "error_message": str(e)}

async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Chefkoch Recipe Coordinator",
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