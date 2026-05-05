import asyncio
import json
import logging
import random
import re
from datetime import timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup
from get_chefkoch import Search

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

    # Get current data to prevent flickering during partial updates
    # We use a copy to avoid mutating the current state prematurely
    current_data = {}
    if (
        DOMAIN in hass.data
        and entry.entry_id in hass.data[DOMAIN]
        and "coordinator" in hass.data[DOMAIN][entry.entry_id]
    ):
        current_data = hass.data[DOMAIN][entry.entry_id]["coordinator"].data or {}

    data: dict[str, Any] = dict(current_data)

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
                # Only set error state if we don't have old data
                if sensor_id not in data:
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
            # Only set error state if we don't have old data
            if sensor_id not in data:
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

    def _get_id_from_url(url):
        """Extract recipe ID from URL manually."""
        if not url:
            return None
        parts = url.split("/")
        for part in parts:
            if part.isdigit() and len(part) > 5:
                return part
        return None

    def _get_daily_url():
        searcher = Search()
        recipe = searcher.recipeOfTheDay()
        if recipe:
            # Try to get ID without triggering getMeta if possible
            recipe_id = getattr(recipe, "_id", None)
            if not recipe_id:
                recipe_id = _get_id_from_url(getattr(recipe, "_url", ""))
            
            if recipe_id:
                # Avoid triggering getMeta via .name property
                recipe_name = "Daily Recipe"
                if hasattr(recipe, "_gotMeta") and recipe._gotMeta:
                    recipe_name = getattr(recipe, "name", recipe_name)
                return f"{CHEFKOCH_BASE_URL}{recipe_id}/", recipe_name
        return None, None

    def _get_search_url(query, limit=20):
        searcher = Search(query)
        recipes = searcher.recipes(limit=limit)
        if recipes:
            choice = random.choice(recipes)
            recipe_id = getattr(choice, "_id", None)
            if not recipe_id:
                recipe_id = _get_id_from_url(getattr(choice, "_url", ""))
            
            if recipe_id:
                # Avoid triggering getMeta via .name property
                recipe_name = "Search Recipe"
                if hasattr(choice, "_gotMeta") and choice._gotMeta:
                    recipe_name = getattr(choice, "name", recipe_name)
                return f"{CHEFKOCH_BASE_URL}{recipe_id}/", recipe_name
        return None, None

    try:
        _LOGGER.debug("Fetching recipe URL for sensor type: %s", sensor_type)
        url = None
        name = None

        if sensor_type == "daily":
            try:
                url, name = await asyncio.to_thread(_get_daily_url)
            except Exception as daily_err:
                _LOGGER.warning("Daily recipe fetch failed: %s. Falling back to random.", daily_err)
            
            if not url:
                url, name = await asyncio.to_thread(_get_search_url, "Rezept")
            
            if url:
                _LOGGER.debug("Daily/Fallback recipe: %s (URL: %s)", name, url)
            return url

        elif sensor_type == "random":
            url, name = await asyncio.to_thread(_get_search_url, "Rezept", 100)
            if url:
                _LOGGER.debug("Random recipe chosen: %s (URL: %s)", name, url)
            return url

        elif sensor_type == "vegan":
            url, name = await asyncio.to_thread(_get_search_url, "vegan")
            return url

        elif sensor_type == "vegetarian":
            url, name = await asyncio.to_thread(_get_search_url, "vegetarisch")
            return url

        elif sensor_type == "baking":
            url, name = await asyncio.to_thread(_get_search_url, "backen")
            return url

        elif sensor_type == "search":
            search_query = sensor_config.get("search_query", "").strip()
            if not search_query:
                search_query = "Rezept"
            url, name = await asyncio.to_thread(_get_search_url, search_query)
            return url

        return None

    except Exception as e:
        _LOGGER.error(
            "Exception during recipe URL fetch for sensor type %s: %s",
            sensor_type,
            e,
            exc_info=True,
        )
        return None


def _parse_duration(duration_str):
    """Parse ISO8601 duration string (e.g., PT30M) to timedelta string."""
    if not duration_str or not isinstance(duration_str, str):
        return ""
    try:
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return ""
        hours, minutes, seconds = match.groups()
        h = int(hours) if hours else 0
        m = int(minutes) if minutes else 0
        s = int(seconds) if seconds else 0
        return str(timedelta(hours=h, minutes=m, seconds=s))
    except:
        return ""

def extract_recipe_attributes(recipe_url: str) -> dict[str, Any]:
    """Extract all attributes from a recipe URL using manual parsing as fallback for get_chefkoch."""
    try:
        # Manual fetch to be more robust
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        response = requests.get(recipe_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find JSON-LD
        scripts = soup.find_all("script", type="application/ld+json")
        raw = {}
        for script in scripts:
            try:
                data = json.loads(script.string)
                # Some scripts are lists, some are objects
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Recipe":
                            raw = item
                            break
                elif data.get("@type") == "Recipe":
                    raw = data
                    break
            except:
                continue
        
        if not raw:
            _LOGGER.error("No Recipe JSON-LD found in %s", recipe_url)
            return {
                "title": "Error: Missing recipe data",
                "url": recipe_url,
                "status": "error",
                "error_message": "Could not find recipe data in page source.",
            }

        def safe(key: str, default: Any = "") -> Any:
            val = raw.get(key)
            return val if val is not None else default

        name = safe("name", "Unknown Recipe")
        if " von " in name:
            name = name.split(" von ")[0].strip()

        # Rating
        agg = safe("aggregateRating", {})
        rating_value = agg.get("ratingValue") if isinstance(agg, dict) else None
        rating_count = agg.get("ratingCount") if isinstance(agg, dict) else None
        review_count = agg.get("reviewCount") if isinstance(agg, dict) else None

        # Author
        author = ""
        author_raw = safe("author", {})
        if isinstance(author_raw, dict):
            author = author_raw.get("name", "")
        elif isinstance(author_raw, list) and author_raw:
            author = author_raw[0].get("name", "") if isinstance(author_raw[0], dict) else ""

        # Nutrition
        nutrition = safe("nutrition", {})
        calories = ""
        protein = ""
        fat = ""
        carbohydrates = ""
        if isinstance(nutrition, dict):
            calories = nutrition.get("calories", "")
            protein = nutrition.get("proteinContent", "")
            fat = nutrition.get("fatContent", "")
            carbohydrates = nutrition.get("carbohydrateContent", "")

        # Ingredients
        ingredients = safe("recipeIngredient", [])
        if isinstance(ingredients, str):
            ingredients = [ingredients]

        # Images
        images = safe("image", [])
        image_url = ""
        if isinstance(images, list) and images:
            image_url = images[0]
        elif isinstance(images, str):
            image_url = images

        # Instructions: can be a string, a list of strings, a list of HowToStep objects, or HowToSection objects
        instructions_raw = safe("recipeInstructions", "")
        instructions_list = []

        def process_instructions(items):
            if isinstance(items, list):
                for item in items:
                    process_instructions(item)
            elif isinstance(items, dict):
                if items.get("@type") == "HowToStep":
                    text = items.get("text", "")
                    if text:
                        instructions_list.append(str(text))
                elif items.get("@type") == "HowToSection":
                    # Handle section name if present
                    name = items.get("name")
                    if name:
                        instructions_list.append(str(name))
                    process_instructions(items.get("itemListElement", []))
                else:
                    # Fallback for other dict structures
                    text = items.get("text") or items.get("name")
                    if text:
                        instructions_list.append(str(text))
            elif items:
                instructions_list.append(str(items))

        process_instructions(instructions_raw)
        instructions = "\n".join(instructions_list)

        attributes: dict[str, Any] = {
            "title": name,
            "url": recipe_url,
            "image_url": image_url,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carbohydrates": carbohydrates,
            "cuisine": safe("recipeCuisine", ""),
            "video_url": safe("video", [{}])[0].get("contentUrl", "") if isinstance(safe("video"), list) and safe("video") else (safe("video", {}).get("contentUrl", "") if isinstance(safe("video"), dict) else ""),
            "difficulty": safe("difficulty", ""),
            "ingredients": ingredients,
            "instructions": instructions,
            "category": safe("recipeCategory", ""),
            "servings": safe("recipeYield", ""),
            "author": author,
            "publisher": safe("publisher", {}).get("name", "") if isinstance(safe("publisher"), dict) else "",
            "keywords": safe("keywords", ""),
            "date_published": str(safe("datePublished", "")),
            "status": "success",
            "totalTime": _parse_duration(safe("totalTime")),
            "prepTime": _parse_duration(safe("prepTime")),
            "cookTime": _parse_duration(safe("cookTime")),
            "restTime": "",
            "rating": rating_value,
            "rating_count": rating_count,
            "number_ratings": rating_count,
            "number_reviews": review_count,
        }
        return attributes

    except Exception as e:
        _LOGGER.error("Failed to parse recipe %s: %s", recipe_url, e, exc_info=True)
        return {
            "title": "Error loading recipe",
            "url": recipe_url,
            "status": "error",
            "error_message": str(e),
        }


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
