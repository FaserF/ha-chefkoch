"""Attribute extraction for Chefkoch recipes via official v2 REST API (100% pure API, no webscraping)."""

import logging
import re
from datetime import timedelta
from typing import Any

import requests

from .const import CHEFKOCH_BASE_URL

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _get_id_from_url(url: str | None) -> str | None:
    """Extract recipe ID from URL manually."""
    if not url:
        return None
    parts = url.split("/")
    for part in parts:
        if part.isdigit() and len(part) > 5:
            return part
    return None


def _parse_api_time(mins: Any) -> str:
    """Parse minutes integer/string to timedelta string."""
    if mins is None or mins == "" or mins == 0:
        return ""
    try:
        m = int(mins)
        return str(timedelta(minutes=m))
    except ValueError, TypeError:
        return str(mins)


def fetch_recipe_comments_from_api(recipe_id: str, limit: int = 5) -> list[str]:
    """Fetch top user comments for a recipe directly from Chefkoch v2 API."""
    url = f"https://api.chefkoch.de/v2/recipes/{recipe_id}/comments"
    try:
        resp = requests.get(
            url, params={"limit": str(limit)}, headers=HEADERS, timeout=5
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
    except (requests.RequestException, ValueError, KeyError) as err:
        _LOGGER.debug("Failed to fetch comments for recipe %s: %s", recipe_id, err)
    return []


def fetch_recipe_attributes_from_api(
    recipe_id: str, include_comments: bool = True
) -> dict[str, Any]:
    """Fetch recipe attributes directly from Chefkoch v2 REST API."""
    api_url = f"https://api.chefkoch.de/v2/recipes/{recipe_id}"
    response = requests.get(api_url, headers=HEADERS, timeout=10)
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

    # Image URL: use previewImageUrlTemplate replacing <format> with crop-900x600
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

    # Owner / Author
    owner = data.get("owner", {})
    author = ""
    if isinstance(owner, dict):
        author = owner.get("displayName") or owner.get("username") or ""

    # Times
    prep_time = _parse_api_time(data.get("preparationTime"))
    cook_time = _parse_api_time(data.get("cookingTime"))
    rest_time = _parse_api_time(data.get("restingTime"))
    total_time = _parse_api_time(data.get("totalTime"))

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

    comments = (
        fetch_recipe_comments_from_api(recipe_id, limit=5) if include_comments else []
    )

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


def extract_recipe_attributes(recipe_url: str) -> dict[str, Any]:
    """Extract all attributes from a recipe URL using Chefkoch REST API exclusively (no webscraping)."""
    recipe_id = _get_id_from_url(recipe_url)
    if not recipe_id:
        _LOGGER.error("Could not extract recipe ID from URL: %s", recipe_url)
        return {
            "title": "Error loading recipe",
            "url": recipe_url,
            "status": "error",
            "error_message": f"Could not extract recipe ID from {recipe_url}",
        }

    try:
        return fetch_recipe_attributes_from_api(recipe_id)
    except Exception as err:
        _LOGGER.exception(
            "Chefkoch API request failed for recipe ID %s: %s", recipe_id, err
        )
        return {
            "title": "Error loading recipe",
            "url": recipe_url,
            "status": "error",
            "error_message": str(err),
        }


def _scale_ingredient(ingredient: str, factor: float) -> str:
    """Scale numeric quantities in an ingredient string by a factor."""
    if factor == 1.0 or ingredient.startswith("---"):
        return ingredient

    def replace_num(match):
        num_str = match.group(0).replace(",", ".")
        try:
            val = float(num_str) * factor
            return f"{val:g}".replace(".", ",")
        except ValueError:
            return match.group(0)

    return re.sub(r"\b\d+(?:[\.,]\d+)?\b", replace_num, ingredient)
