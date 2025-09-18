import asyncio
import logging
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

from homeassistant import config_entries, core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import async_timeout
import aiohttp
from chefkoch.retrievers import DailyRecipeRetriever, RandomRetriever, SearchRetriever
from chefkoch import Recipe

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(days=1)

# Executor for running synchronous code in a separate thread
executor = ThreadPoolExecutor()


async def async_update_data(hass: core.HomeAssistant):
    """Fetch data from Chefkoch."""
    try:
        async with async_timeout.timeout(SCAN_INTERVAL.total_seconds() - 1):
            # Create retrievers
            random_retriever = RandomRetriever()
            daily_retriever = DailyRecipeRetriever()
            vegan_retriever = SearchRetriever(health=["Vegan"])

            _LOGGER.debug("Fetching all recipes concurrently...")

            # Use asyncio to run the fetches concurrently
            # Note: aiohttp session management should ideally be handled for these calls
            random_recipe_task = asyncio.to_thread(random_retriever.get_recipe)
            daily_recipes_task = asyncio.to_thread(daily_retriever.get_recipes, type="kochen")
            vegan_recipes_task = asyncio.to_thread(vegan_retriever.get_recipes, search_query="vegan")

            # Gather results from all tasks
            random_recipe, daily_recipes, vegan_recipes = await asyncio.gather(
                random_recipe_task,
                daily_recipes_task,
                vegan_recipes_task
            )

            # Log the results after all tasks are completed
            _LOGGER.debug(
                "random_recipe retrieved: %s\ndaily_recipes retrieved: %s\nvegan_recipes retrieved: %s",
                random_recipe,
                daily_recipes,
                vegan_recipes
            )

            selected_random_recipe = random_recipe
            selected_daily_recipe = daily_recipes[0] if isinstance(daily_recipes, list) and daily_recipes else None
            selected_vegan_recipe = vegan_recipes[0] if isinstance(vegan_recipes, list) and vegan_recipes else None

            _LOGGER.debug("Selected random_recipe: %s", selected_random_recipe)
            _LOGGER.debug("Selected daily_recipe: %s", selected_daily_recipe)
            _LOGGER.debug("Selected vegan_recipe: %s", selected_vegan_recipe)

            def get_recipe_url(recipe):
                """Get recipe URL safely."""
                return recipe.url if hasattr(recipe, 'url') and recipe.url else ""

            def safe_get_attr(obj, attr, default=None):
                """Try to get an attribute from obj, catch all exceptions."""
                try:
                    value = getattr(obj, attr)
                    if callable(value):
                        return value()
                    return value
                except Exception as e:
                    _LOGGER.debug(f"Failed to get attribute {attr}: {e}", exc_info=True)
                    return default

            def extract_recipe_attributes(recipe_url):
                result = {
                    "title": "Unknown",
                    "url": recipe_url or "",
                    "image_url": "",
                    "totalTime": 0,
                    "ingredients": [],
                    "calories": None,
                    "category": "",
                    "difficulty": "",
                    "status": "success",
                }

                if not recipe_url:
                    result["status"] = "error"
                    result["error_message"] = "No recipe URL provided"
                    return result

                try:
                    recipe = Recipe(recipe_url)
                    result["title"] = safe_get_attr(recipe, "title", default="Unknown")
                    result["image_url"] = safe_get_attr(recipe, "image_url", default="")
                    result["totalTime"] = safe_get_attr(recipe, "total_time", default=0)
                    result["ingredients"] = safe_get_attr(recipe, "ingredients", default=[])
                    result["calories"] = safe_get_attr(recipe, "calories")
                    result["category"] = safe_get_attr(recipe, "category", default="")
                    result["difficulty"] = safe_get_attr(recipe, "difficulty", default="")

                except Exception as e:
                    _LOGGER.error(f"Recipe object could not be created for URL {recipe_url}: {e}", exc_info=True)
                    result["status"] = "error"
                    result["error_message"] = f"Failed to create recipe object: {e}"

                return result

            # Use asyncio to run recipe extraction concurrently
            random_attributes_task = asyncio.to_thread(
                extract_recipe_attributes, get_recipe_url(selected_random_recipe)
            )
            daily_attributes_task = asyncio.to_thread(
                extract_recipe_attributes, get_recipe_url(selected_daily_recipe)
            )
            vegan_attributes_task = asyncio.to_thread(
                extract_recipe_attributes, get_recipe_url(selected_vegan_recipe)
            )

            # Gather results from all tasks
            random_attributes, daily_attributes, vegan_attributes = await asyncio.gather(
                random_attributes_task,
                daily_attributes_task,
                vegan_attributes_task
            )

            # Log the results after all tasks are completed
            _LOGGER.debug("Extracted random_attributes: %s\nExtracted daily_attributes: %s\nExtracted vegan_attributes: %s", random_attributes, daily_attributes, vegan_attributes)

            # Prepare the data dictionary
            return {
                "random": random_attributes,
                "daily": daily_attributes,
                "vegan": vegan_attributes
            }

    except aiohttp.ClientError as err:
        _LOGGER.error("Client error fetching data: %s", err, exc_info=True)
        raise UpdateFailed(f"Client error fetching data: {err}")
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout error fetching data", exc_info=True)
        raise UpdateFailed("Timeout error fetching data")
    except Exception as err:
        _LOGGER.error("Unexpected error fetching data: %s", err, exc_info=True)
        raise UpdateFailed(f"Unexpected error fetching data: {err}")


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    _LOGGER.debug("Setting up Chefkoch entry")

    hass.data.setdefault(DOMAIN, {})

    # Create a single coordinator to fetch all data
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Chefkoch Recipe Coordinator",
        update_method=lambda: async_update_data(hass),
        update_interval=SCAN_INTERVAL,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator
    }

    # Register update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
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
