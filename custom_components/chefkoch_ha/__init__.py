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

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    _LOGGER.debug("Setting up Chefkoch entry")

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    # Register update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener

    async def async_update_data():
        """Fetch data from Chefkoch."""
        try:
            async with async_timeout.timeout(SCAN_INTERVAL.total_seconds() - 1):
                async with aiohttp.ClientSession() as session:
                    # Create retrievers
                    random_retriever = RandomRetriever()
                    daily_retriever = DailyRecipeRetriever()
                    vegan_retriever = SearchRetriever(health=["Vegan"])

                    _LOGGER.debug("Fetching all recipes concurrently...")

                    # Use asyncio to run the fetches concurrently
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

                    # Logging to understand the content of random_recipe
                    if random_recipe is None:
                        _LOGGER.error("random_recipe is None!")
                    elif isinstance(random_recipe, Recipe):
                        _LOGGER.debug("random_recipe is a single Recipe object")
                    else:
                        _LOGGER.warning("random_recipe is not a Recipe object. It is of type %s", type(random_recipe))

                    # Since random_recipe is a single Recipe object, there's no need to select from a list
                    selected_random_recipe = random_recipe
                    selected_daily_recipe = daily_recipes[0] if isinstance(daily_recipes, list) and daily_recipes else None
                    selected_vegan_recipe = vegan_recipes[0] if isinstance(vegan_recipes, list) and vegan_recipes else None

                    _LOGGER.debug("Selected random_recipe: %s", selected_random_recipe)
                    _LOGGER.debug("Selected daily_recipe: %s", selected_daily_recipe)
                    _LOGGER.debug("Selected vegan_recipe: %s", selected_vegan_recipe)

                    def get_recipe_url(recipe):
                        """Get recipe URL safely."""
                        return recipe.url if hasattr(recipe, 'url') and recipe.url else ""

                    def extract_recipe_attributes(recipe_url):
                        """Extract attributes from the recipe using a separate thread."""
                        if recipe_url:
                            try:
                                recipe = Recipe(recipe_url)
                                return {
                                    "title": recipe.title or "Unknown",
                                    "url": recipe_url or "",
                                    "image_url": recipe.image_url if recipe.image_url is not None else "",
                                    "totalTime": str(recipe.total_time) if recipe.total_time else "",
                                    "ingredients": recipe.ingredients if recipe.ingredients else [],
                                    "calories": recipe.calories if recipe.calories else "",
                                    "category": recipe.category if recipe.category else "",
                                }
                            except Exception as e:
                                _LOGGER.error("Error extracting recipe attributes: %s", e, exc_info=True)
                                return {
                                    "title": "Unknown",
                                    "url": recipe_url or "",
                                    "image_url": "",
                                    "totalTime": "",
                                    "ingredients": [],
                                    "calories": "",
                                    "category": "",
                                }
                        return {
                            "title": "Unknown",
                            "url": recipe_url or "",
                            "image_url": "",
                            "totalTime": "",
                            "ingredients": [],
                            "calories": "",
                            "category": "",
                        }

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
                    data = {
                        "random": random_attributes,
                        "daily": daily_attributes,
                        "vegan": vegan_attributes
                    }

                    return data

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error fetching data: %s", err, exc_info=True)
            raise UpdateFailed(f"Client error fetching data: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error fetching data", exc_info=True)
            raise UpdateFailed("Timeout error fetching data")
        except Exception as err:
            _LOGGER.error("Unexpected error fetching data: %s", err, exc_info=True)
            raise UpdateFailed(f"Unexpected error fetching data: {err}")

    # Create coordinators for each type
    coordinators = {
        "random": DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="Chefkoch random recipe",
            update_method=async_update_data,
            update_interval=SCAN_INTERVAL,
        ),
        "daily": DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="Chefkoch daily recipe",
            update_method=async_update_data,
            update_interval=SCAN_INTERVAL,
        ),
        "vegan": DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="Chefkoch vegan recipe",
            update_method=async_update_data,
            update_interval=SCAN_INTERVAL,
        ),
    }

    # Use asyncio to run the coordinators concurrently
    coordinator_tasks = [coordinator.async_config_entry_first_refresh() for coordinator in coordinators.values()]
    # Gather results from all tasks
    await asyncio.gather(*coordinator_tasks)

    # Add coordinators to hass data
    hass_data["coordinator_random"] = coordinators["random"]
    hass_data["coordinator_daily"] = coordinators["daily"]
    hass_data["coordinator_vegan"] = coordinators["vegan"]
    hass.data[DOMAIN][entry.entry_id] = hass_data

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
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
