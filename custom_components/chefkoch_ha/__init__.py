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
    """
    Fetch recipes for all sensors configured in the given ConfigEntry.
    
    Reads the list of sensor configurations from entry.options["sensors"] (returns {} if absent or empty). For each sensor it concurrently:
    - resolves a recipe URL via _fetch_recipe_url(sensor_config),
    - if a URL is found, extracts recipe attributes using extract_recipe_attributes (run in a thread),
    - stores the resulting attributes under the sensor's id in the returned mapping.
    
    On failures: a sensor entry will contain {"title": "No recipe found", "status": "error"} when no URL is found, or {"title": "Error", "status": "error", "error_message": ...} if an exception occurs during fetch/processing.
    
    Parameters:
    - entry: ConfigEntry whose options must include a "sensors" list of sensor config dicts (each must provide at least "id" and "name"; other keys are used by _fetch_recipe_url).
    
    Returns:
    A dict mapping sensor_id -> attributes_dict (or error-status dict) for each configured sensor.
    """
    sensors = entry.options.get("sensors", [])
    if not sensors:
        return {}

    data = {}

    async def fetch_and_process_sensor(sensor_config):
        """
        Fetch and process a single sensor configuration: obtain a recipe URL, extract recipe attributes, and store the result in the outer `data` mapping.
        
        sensor_config (dict) should include at least:
        - "id": unique sensor identifier used as the key in `data`
        - "name": human-readable sensor name (used in logs)
        Other keys determine how the recipe URL is retrieved.
        
        Side effects:
        - Writes the recipe attributes or an error/status dict into the enclosing `data` dict under the sensor's id.
        - Logs warnings and errors for missing recipes or failures.
        
        This function handles its own errors and does not raise exceptions.
        """
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
    """
    Select and return a Chefkoch recipe URL according to the given sensor configuration.
    
    Given sensor_config (a dict) this chooses an appropriate retriever based on its "type"
    and returns the first matching recipe's URL, or None if no recipe is found or the type is
    unrecognized.
    
    Supported sensor types:
    - "random": returns a single random recipe.
    - "daily": returns the first recipe from the daily recipes of type "kochen".
    - "vegan": searches with a vegan health filter and returns the first match.
    - "search": performs a parameterized search; recognized optional keys are
      "search_query" (string), "category", and "difficulty" (the latter two are used to
      construct the SearchRetriever and are ignored if None/empty).
    
    Parameters:
        sensor_config (dict): Sensor configuration containing at minimum a "type" key.
            For "search" type it may also include "search_query", "category", and "difficulty".
    
    Returns:
        str | None: The recipe URL if found, otherwise None.
    """
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
    """
    Extracts recipe data from a Chefkoch recipe URL and returns a normalized attribute dictionary.
    
    Parameters:
        recipe_url (str): URL of the recipe page to parse.
    
    Returns:
        dict: A dictionary containing normalized recipe attributes. On success, includes:
            - title (str)
            - url (str)
            - image_url (str)
            - totalTime (int|float)
            - prepTime (int|float)
            - cookTime (int|float)
            - restTime (int|float)
            - calories (int|None)
            - difficulty (str)
            - ingredients (list)
            - instructions (str)
            - category (str)
            - servings (int|None)
            - rating (number|None)
            - rating_count (int|None)
            - status (str) — "success"
    
        If extraction fails, returns a dictionary with:
            - status: "error"
            - error_message: (str) exception message describing the failure
    """
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
    """
    Set up the Chefkoch integration for a specific config entry.
    
    Creates and registers a DataUpdateCoordinator for the entry, performs an initial data refresh,
    stores the coordinator under hass.data[DOMAIN][entry.entry_id], registers an options update
    listener, and forwards platform setup to the "sensor" platform.
    
    Parameters:
        entry (config_entries.ConfigEntry): The config entry for this integration instance.
    
    Returns:
        bool: True if setup completed successfully.
    """
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
    """
    Unload a config entry's platforms and clean up stored integration data.
    
    Unloads the "sensor" platform for the provided ConfigEntry. If platform unload succeeds,
    removes the entry's coordinator/data from hass.data[DOMAIN].
    
    Returns:
        bool: True if the platform unload completed successfully, False otherwise.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok