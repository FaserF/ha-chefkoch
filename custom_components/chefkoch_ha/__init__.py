import asyncio
import json
import logging
import random
from datetime import timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup
from get_chefkoch import Search  # type: ignore[import-untyped]

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
    # We check both the active coordinator and the persistent cache
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


def _get_id_from_url(url: str | None) -> str | None:
    """Extract recipe ID from URL manually."""
    if not url:
        return None
    parts = url.split("/")
    for part in parts:
        if part.isdigit() and len(part) > 5:
            return part
    return None


async def _fetch_recipe_url(sensor_config: dict[str, Any]) -> str | None:
    """Fetch the recipe URL based on sensor config using get_chefkoch."""
    sensor_type = sensor_config["type"]

    def _get_daily_url():
        searcher = Search()
        recipe = searcher.recipeOfTheDay()
        if recipe:
            # Try to get ID without triggering getMeta if possible
            recipe_id = getattr(recipe, "_id", None)
            if not recipe_id:
                recipe_id = _get_id_from_url(getattr(recipe, "_url", ""))

            if recipe_id:
                url = f"{CHEFKOCH_BASE_URL}{recipe_id}/"
                # Check for Plus recipe (no JSON-LD)
                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    resp = requests.get(url, headers=headers, timeout=5)
                    if resp.status_code == 200 and "application/ld+json" in resp.text:
                        # Avoid triggering getMeta via .name property
                        recipe_name = "Daily Recipe"
                        if hasattr(recipe, "_gotMeta") and recipe._gotMeta:
                            recipe_name = getattr(recipe, "name", recipe_name)
                        return url, recipe_name
                    else:
                        _LOGGER.debug("Daily recipe is Plus or invalid: %s", url)
                except Exception as e:
                    _LOGGER.debug("Error during Daily Plus check for %s: %s", url, e)
        return None, None

    def _get_search_url(query_or_config, limit=20):
        if isinstance(query_or_config, dict):
            sensor_cfg = query_or_config
            query = sensor_cfg.get("search_query", "").strip() or "Rezept"
        else:
            sensor_cfg = {"search_query": str(query_or_config)}
            query = str(query_or_config)

        # Try direct API search with parameters first
        params: dict[str, str] = {"query": query, "limit": str(limit)}

        prep_times = sensor_cfg.get("prep_times")
        if prep_times and prep_times != "Alle":
            try:
                params["maxTime"] = str(int(prep_times))
            except ValueError:
                pass

        ratings = sensor_cfg.get("ratings")
        ratings_map = {"2": "2.0", "3": "3.0", "4": "4.0", "Top": "4.5"}
        if ratings and ratings in ratings_map:
            params["minimumRating"] = ratings_map[ratings]

        sort = sensor_cfg.get("sort")
        sort_map = {"Bewertung": "rating", "Neuheiten": "createdAt"}
        if sort and sort in sort_map:
            params["orderBy"] = sort_map[sort]

        api_search_url = "https://api.chefkoch.de/v2/recipes"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(
                api_search_url, params=params, headers=headers, timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                valid_recipes = []
                for item in results:
                    recipe = item.get("recipe", {})
                    if recipe and not recipe.get("isPlus"):
                        rid = recipe.get("id")
                        if rid:
                            valid_recipes.append(
                                (
                                    f"{CHEFKOCH_BASE_URL}{rid}/",
                                    recipe.get("title", "Search Recipe"),
                                )
                            )

                if valid_recipes:
                    attempts = min(5, len(valid_recipes))
                    choice = random.choice(valid_recipes[:attempts])
                    return choice[0], choice[1]
        except Exception as err:
            _LOGGER.debug("API search failed (%s), falling back to Search()", err)

        # Fallback to get_chefkoch Search()
        searcher = Search(query)
        recipes = searcher.recipes(limit=limit)
        if recipes:
            attempts = min(5, len(recipes))
            sampled_recipes = random.sample(recipes, attempts)

            for choice in sampled_recipes:
                recipe_id = getattr(choice, "_id", None)
                if not recipe_id:
                    recipe_id = _get_id_from_url(getattr(choice, "_url", ""))

                if recipe_id:
                    url = f"{CHEFKOCH_BASE_URL}{recipe_id}/"
                    try:
                        resp = requests.get(url, headers=headers, timeout=5)
                        if (
                            resp.status_code == 200
                            and "application/ld+json" in resp.text
                        ):
                            recipe_name = "Search Recipe"
                            if hasattr(choice, "_gotMeta") and choice._gotMeta:
                                recipe_name = getattr(choice, "name", recipe_name)
                            return url, recipe_name
                        else:
                            _LOGGER.debug("Skipping Plus or invalid recipe: %s", url)
                    except Exception as e:
                        _LOGGER.debug("Error during Plus check for %s: %s", url, e)

            choice = recipes[0]
            recipe_id = _get_id_from_url(getattr(choice, "_url", ""))
            return f"{CHEFKOCH_BASE_URL}{recipe_id}/", "Search Recipe"

        return None, None

    try:
        _LOGGER.debug("Fetching recipe URL for sensor type: %s", sensor_type)
        url = None
        name = None

        if sensor_type == "daily":
            try:
                url, name = await asyncio.to_thread(_get_daily_url)
            except Exception as daily_err:
                _LOGGER.warning(
                    "Daily recipe fetch failed: %s. Falling back to random.", daily_err
                )

            if not url:
                url, name = await asyncio.to_thread(_get_search_url, sensor_config)

            if url:
                _LOGGER.debug("Daily/Fallback recipe: %s (URL: %s)", name, url)
            return url

        elif sensor_type == "random":
            url, name = await asyncio.to_thread(_get_search_url, sensor_config, 100)
            if url:
                _LOGGER.debug("Random recipe chosen: %s (URL: %s)", name, url)
            return url

        elif sensor_type == "vegan":
            cfg = dict(sensor_config)
            cfg["search_query"] = "vegan"
            url, name = await asyncio.to_thread(_get_search_url, cfg)
            return url

        elif sensor_type == "vegetarian":
            cfg = dict(sensor_config)
            cfg["search_query"] = "vegetarisch"
            url, name = await asyncio.to_thread(_get_search_url, cfg)
            return url

        elif sensor_type == "baking":
            cfg = dict(sensor_config)
            cfg["search_query"] = "backen"
            url, name = await asyncio.to_thread(_get_search_url, cfg)
            return url

        elif sensor_type == "search":
            url, name = await asyncio.to_thread(_get_search_url, sensor_config)
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

        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
        if not match:
            return ""
        hours, minutes, seconds = match.groups()
        h = int(hours) if hours else 0
        m = int(minutes) if minutes else 0
        s = int(seconds) if seconds else 0
        return str(timedelta(hours=h, minutes=m, seconds=s))
    except Exception:
        return ""


def _find_recipe_in_json(data: Any) -> dict[str, Any] | None:
    """Recursively search JSON-LD structure for a Recipe object."""
    if isinstance(data, dict):
        if data.get("@type") == "Recipe":
            return data
        if isinstance(data.get("@graph"), list):
            for item in data["@graph"]:
                found = _find_recipe_in_json(item)
                if found:
                    return found
    elif isinstance(data, list):
        for item in data:
            found = _find_recipe_in_json(item)
            if found:
                return found
    return None


def fetch_recipe_comments_from_api(recipe_id: str, limit: int = 5) -> list[str]:
    """Fetch top user comments for a recipe from Chefkoch API."""
    url = f"https://api.chefkoch.de/v2/recipes/{recipe_id}/comments"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(
            url, params={"limit": str(limit)}, headers=headers, timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            comments = []
            for item in data.get("results", []):
                if isinstance(item, dict):
                    text = item.get("text", "").strip()
                    owner = item.get("owner", {})
                    author = (
                        owner.get("displayName") or owner.get("username")
                        if isinstance(owner, dict)
                        else ""
                    )
                    if text:
                        comments.append(f"{author}: {text}" if author else text)
            return comments
    except Exception as err:
        _LOGGER.debug("Failed to fetch comments for recipe %s: %s", recipe_id, err)
    return []


def fetch_recipe_attributes_from_api(recipe_id: str) -> dict[str, Any]:
    """Fetch recipe attributes directly from Chefkoch v2 API."""
    api_url = f"https://api.chefkoch.de/v2/recipes/{recipe_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(api_url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    if not data or not isinstance(data, dict) or not data.get("title"):
        raise ValueError("API response is empty or missing required title field")

    title = data.get("title", "")

    # Extract ingredients from ingredientGroups
    ingredients = []
    for group in data.get("ingredientGroups", []):
        header = group.get("header", "").strip()
        if header:
            ingredients.append(f"--- {header} ---")
        for ing in group.get("ingredients", []):
            amount = ing.get("amount")
            unit = ing.get("unit", "").strip()
            name = ing.get("name", "").strip()
            usage_info = ing.get("usageInfo", "").strip().lstrip(",").strip()

            amount_str = ""
            if isinstance(amount, (int, float)) and amount > 0:
                amount_str = f"{amount:g}"

            name_with_usage = f"{name} ({usage_info})" if usage_info else name
            parts = [p for p in [amount_str, unit, name_with_usage] if p]
            if parts:
                ingredients.append(" ".join(parts))

    # Image URL: use previewImageUrlTemplate if available, replacing <format> with crop-900x600
    image_url = ""
    template = data.get("previewImageUrlTemplate")
    if template and isinstance(template, str):
        image_url = template.replace("<format>", "crop-900x600")
    elif data.get("previewImageId"):
        preview_img_id = data.get("previewImageId")
        image_url = f"https://img.chefkochcdn.de/rezepte/{recipe_id}/bilder/{preview_img_id}/crop-900x600/rezept.jpg"

    # Nutrition
    nutrition = data.get("nutrition", {})
    calories = ""
    protein = ""
    fat = ""
    carbohydrates = ""
    if isinstance(nutrition, dict):
        if nutrition.get("kCalories") is not None:
            calories = f"{nutrition.get('kCalories')} kcal"
        if nutrition.get("proteinContent") is not None:
            protein = f"{nutrition.get('proteinContent')} g"
        if nutrition.get("fatContent") is not None:
            fat = f"{nutrition.get('fatContent')} g"
        if nutrition.get("carbohydrateContent") is not None:
            carbohydrates = f"{nutrition.get('carbohydrateContent')} g"
    elif data.get("kCalories") is not None:
        calories = f"{data.get('kCalories')} kcal"

    # Rating
    rating_data = data.get("rating", {})
    rating_val = None
    rating_count = None
    if isinstance(rating_data, dict):
        rating_val = rating_data.get("rating")
        rating_count = rating_data.get("numVotes")
    elif isinstance(rating_data, (int, float)):
        rating_val = rating_data

    # Owner/Author
    owner = data.get("owner", {})
    author = ""
    if isinstance(owner, dict):
        author = owner.get("displayName") or owner.get("username") or ""

    # Times
    def parse_api_time(mins):
        if mins is None or mins == "" or mins == 0:
            return ""
        try:
            m = int(mins)
            return str(timedelta(minutes=m))
        except (ValueError, TypeError):
            return str(mins)

    prep_time = parse_api_time(data.get("preparationTime"))
    cook_time = parse_api_time(data.get("cookingTime"))
    rest_time = parse_api_time(data.get("restingTime"))
    total_time = parse_api_time(data.get("totalTime"))

    # Difficulty mapping
    diff_raw = data.get("difficulty")
    diff_map: dict[Any, str] = {1: "einfach", 2: "normal", 3: "pfiffig"}
    difficulty = diff_map.get(diff_raw, str(diff_raw) if diff_raw is not None else "")

    # Servings
    servings = data.get("servings", "")
    if servings:
        servings = f"{servings} Port."

    tags = data.get("tags", [])
    keywords = ", ".join(tags) if isinstance(tags, list) else str(tags) if tags else ""

    breadcrumb_items = [
        b.get("title")
        for b in data.get("categoryBreadcrumb", [])
        if isinstance(b, dict) and b.get("title")
    ]

    comments = fetch_recipe_comments_from_api(recipe_id, limit=5)

    attributes: dict[str, Any] = {
        "title": title,
        "subtitle": data.get("subtitle", ""),
        "url": data.get("siteUrl") or f"{CHEFKOCH_BASE_URL}{recipe_id}/",
        "image_url": image_url,
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbohydrates": carbohydrates,
        "cuisine": data.get("recipeCuisine", ""),
        "video_url": "",
        "video_id": str(data.get("recipeVideoId")) if data.get("recipeVideoId") else "",
        "difficulty": difficulty,
        "ingredients": ingredients,
        "instructions": data.get("instructions", ""),
        "category": "",
        "category_breadcrumb": breadcrumb_items,
        "servings": str(servings),
        "author": author,
        "author_notes": data.get("miscellaneousText", "").strip(),
        "publisher": "Chefkoch",
        "keywords": keywords,
        "tags": tags if isinstance(tags, list) else [],
        "saved_recipes_count": data.get("savedRecipesCount"),
        "view_count": data.get("viewCount"),
        "top_comments": comments,
        "date_published": str(data.get("createdAt", "")),
        "status": "success",
        "totalTime": total_time,
        "prepTime": prep_time,
        "cookTime": cook_time,
        "restTime": rest_time,
        "rating": rating_val,
        "rating_count": rating_count,
        "number_ratings": rating_count,
        "number_reviews": None,
    }
    return attributes


def extract_recipe_attributes_webscraping(recipe_url: str) -> dict[str, Any]:
    """Extract all attributes from a recipe URL using JSON-LD webscraping."""
    try:
        # Manual fetch to be more robust
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(recipe_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Find JSON-LD
        scripts = soup.find_all("script", type="application/ld+json")
        raw = {}
        all_json_data = []
        for script in scripts:
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                all_json_data.append(data)
                recipe = _find_recipe_in_json(data)
                if recipe:
                    raw = recipe
                    break
            except Exception:
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

        raw_name = safe("name", "Unknown Recipe")
        name = raw_name
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
            author = (
                author_raw[0].get("name", "") if isinstance(author_raw[0], dict) else ""
            )

        if not author and " von " in raw_name:
            author = raw_name.split(" von ")[-1].strip()

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
            first_img = images[0]
            if isinstance(first_img, dict):
                image_url = first_img.get("url") or first_img.get("contentUrl", "")
            elif isinstance(first_img, str):
                image_url = first_img
        elif isinstance(images, str):
            image_url = images
        elif isinstance(images, dict):
            image_url = images.get("url") or images.get("contentUrl", "")

        if not image_url or not image_url.startswith("http"):
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                image_url = str(og_image["content"])

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

        kw = safe("keywords", "")
        tags_list = [k.strip() for k in kw.split(",") if k.strip()] if kw else []

        attributes: dict[str, Any] = {
            "title": name,
            "subtitle": "",
            "url": recipe_url,
            "image_url": image_url,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carbohydrates": carbohydrates,
            "cuisine": safe("recipeCuisine", ""),
            "video_url": safe("video", [{}])[0].get("contentUrl", "")
            if isinstance(safe("video"), list) and safe("video")
            else (
                safe("video", {}).get("contentUrl", "")
                if isinstance(safe("video"), dict)
                else ""
            ),
            "video_id": "",
            "difficulty": safe("difficulty", ""),
            "ingredients": ingredients,
            "instructions": instructions,
            "category": safe("recipeCategory", ""),
            "category_breadcrumb": [],
            "servings": safe("recipeYield", ""),
            "author": author,
            "author_notes": "",
            "publisher": safe("publisher", {}).get("name", "")
            if isinstance(safe("publisher"), dict)
            else "",
            "keywords": kw,
            "tags": tags_list,
            "saved_recipes_count": None,
            "view_count": None,
            "top_comments": [],
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


def extract_recipe_attributes(recipe_url: str) -> dict[str, Any]:
    """Extract all attributes from a recipe URL using API first, with webscraping fallback."""
    recipe_id = _get_id_from_url(recipe_url)
    if recipe_id:
        try:
            return fetch_recipe_attributes_from_api(recipe_id)
        except Exception as err:
            _LOGGER.warning(
                "Chefkoch API request failed or returned empty data for %s (%s). Falling back to less efficient webscraping.",
                recipe_url,
                err,
            )

    else:
        _LOGGER.warning(
            "Could not extract recipe ID from URL %s. Falling back to less efficient webscraping.",
            recipe_url,
        )

    return extract_recipe_attributes_webscraping(recipe_url)


def _scale_ingredient(ingredient: str, factor: float) -> str:
    """Scale numeric quantities in an ingredient string by a factor."""
    if factor == 1.0 or ingredient.startswith("---"):
        return ingredient
    import re

    def replace_num(match):
        num_str = match.group(0).replace(",", ".")
        try:
            val = float(num_str) * factor
            return f"{val:g}".replace(".", ",")
        except ValueError:
            return match.group(0)

    return re.sub(r"\b\d+(?:[\.,]\d+)?\b", replace_num, ingredient)


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

    # Pre-fill coordinator with cached data if available to avoid "unavailable" state on reload
    cached_data = hass.data.get(DOMAIN, {}).get(f"cache_{entry.entry_id}")
    if cached_data:
        coordinator.data = cached_data

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}
    # Update cache after successful refresh
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
                url = await _fetch_recipe_url({"type": "search", **sensor_cfg})
                if url:
                    recipe_id = _get_id_from_url(url)
                    title = ""
                    if recipe_id:
                        try:
                            attrs = await asyncio.to_thread(
                                fetch_recipe_attributes_from_api, recipe_id
                            )
                            title = attrs.get("title", "")
                        except Exception:
                            pass
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
    hass.services.async_register(
        DOMAIN, "generate_meal_plan", handle_generate_meal_plan
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
        # We keep the cache_ entry in hass.data[DOMAIN] to survive the reload flicker
        if entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
