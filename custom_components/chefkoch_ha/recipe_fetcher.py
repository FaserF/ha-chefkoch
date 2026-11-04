"""Recipe fetching and search logic for Chefkoch using the official v2 REST API."""

import contextlib
import logging
import random
import sys
from datetime import datetime
from typing import Any

import requests

from .const import CHEFKOCH_BASE_URL
from .parser import _get_id_from_url

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://api.chefkoch.de/v2/recipes"
SUGGESTIONS_URL = "https://api.chefkoch.de/v2/search-suggestions/recipes"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SEASONAL_MODES = [
    "auto",
    "halloween",
    "christmas",
    "silvester",
    "winter",
    "easter",
    "summer",
    "autumn",
    "weather_only",
]


def _get_search_class() -> Any:
    """Retrieve Search class, respecting mocks in parent module if present."""
    parent = sys.modules.get("custom_components.chefkoch_ha")
    if parent and hasattr(parent, "Search"):
        return parent.Search
    try:
        from get_chefkoch import Search  # type: ignore[import-untyped]

        return Search
    except ImportError:
        return None


def _fetch_api_suggestions(term: str = "") -> list[str]:
    """Fetch live search suggestions from Chefkoch API."""
    try:
        resp = requests.get(
            SUGGESTIONS_URL,
            params={"t": term},
            headers=HEADERS,
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            suggestions = data.get("suggestions", [])
            if isinstance(suggestions, list):
                return [str(s).strip() for s in suggestions if s and str(s).strip()]
    except Exception as err:
        _LOGGER.debug("Failed to fetch suggestions for '%s': %s", term, err)
    return []


def _get_seasonal_specials(now: datetime | None = None) -> tuple[list[str], str]:
    """Determine seasonal keywords and category label based on date and specials."""
    current = now or datetime.now()
    month = current.month
    day = current.day

    # 1. Holiday / Date-specific special windows
    if (month == 10 and day >= 15) or (month == 11 and day <= 2):
        return [
            "halloween",
            "kürbissuppe",
            "kürbis",
            "herbstgerichte",
            "halloween fingerfood",
            "halloween kuchen",
        ], "Halloween & Herbst-Specials"
    if month == 12:
        if day <= 26:
            return [
                "weihnachten",
                "weihnachtsbraten",
                "plätzchen",
                "wintergerichte",
                "lebkuchen",
                "festmenü",
            ], "Weihnachtliche Festküche"
        return [
            "silvester",
            "raclette",
            "fondue",
            "fingerfood",
            "party snacks",
        ], "Silvester & Party-Specials"
    if month == 1 and day <= 2:
        return ["silvester", "neujahr", "katerfrühstück", "suppe"], "Neujahrs-Specials"
    if (month == 3 and day >= 15) or (month == 4 and day <= 25):
        return [
            "ostern",
            "osterbrot",
            "bärlauch",
            "spargel",
            "frühling",
            "frühlingssalat",
        ], "Frühling & Oster-Küche"

    # 2. Season-based defaults
    if month in (6, 7, 8):
        return [
            "sommersalat",
            "wraps",
            "grillen",
            "sommerrollen",
            "leichte sommerküche",
            "sommer bowl",
        ], "Sommerlich leicht & Grillen"
    if month in (12, 1, 2):
        return [
            "eintopf",
            "auflauf",
            "gulasch",
            "wintergerichte",
            "schmorgericht",
            "wärmende suppe",
        ], "Winterlich deftig"
    if month in (9, 10, 11):
        return [
            "herbstgerichte",
            "kürbissuppe",
            "herbstsalat",
            "eintopf",
            "apfelkuchen",
            "pilzpfanne",
        ], "Herbstliche Wohlfühlküche"

    return [
        "schnelle gerichte",
        "pasta",
        "gemüsepfanne",
        "risotto",
        "quiche",
    ], "Frühlingshaft frisch"


def _get_weather_recipe_query(
    hass: Any = None,
    sensor_config: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Determine an intelligent weather- or season-based recipe search query using Chefkoch API suggestions."""
    sensor_cfg = sensor_config or {}
    opts = options or {}
    mode = opts.get("weather_seasonal_mode") or sensor_cfg.get(
        "weather_seasonal_mode", "auto"
    )
    include_holidays = opts.get(
        "include_holiday_specials",
        sensor_cfg.get("include_holiday_specials", True),
    )

    # 1. Check for manual mode overrides from OptionsFlow
    if mode == "halloween":
        seed_terms = ["halloween", "kürbissuppe", "kürbis", "halloween fingerfood"]
        category_label = "Halloween & Grusel-Specials"
    elif mode == "christmas":
        seed_terms = [
            "weihnachten",
            "weihnachtsbraten",
            "plätzchen",
            "wintergerichte",
            "lebkuchen",
        ]
        category_label = "Weihnachtliche Festküche"
    elif mode == "silvester":
        seed_terms = ["silvester", "raclette", "fondue", "fingerfood", "partysnacks"]
        category_label = "Silvester & Party-Specials"
    elif mode == "winter":
        seed_terms = [
            "eintopf",
            "auflauf",
            "gulasch",
            "wintergerichte",
            "schmorgericht",
        ]
        category_label = "Winterlich deftig"
    elif mode == "easter":
        seed_terms = ["ostern", "osterbrot", "bärlauch", "spargel", "frühling"]
        category_label = "Frühling & Oster-Küche"
    elif mode == "summer":
        seed_terms = [
            "sommersalat",
            "wraps",
            "grillen",
            "sommerrollen",
            "leichte sommerküche",
        ]
        category_label = "Sommerlich leicht & Grillen"
    elif mode == "autumn":
        seed_terms = [
            "herbstgerichte",
            "kürbissuppe",
            "herbstsalat",
            "eintopf",
            "apfelkuchen",
        ]
        category_label = "Herbstliche Wohlfühlküche"
    else:
        # Automatic mode: evaluate weather temperature AND calendar/holiday windows
        temperature: float | None = None
        condition: str = ""

        # Inspect HA weather entities
        if hass and hasattr(hass, "states"):
            configured_entity = opts.get("weather_entity") or sensor_cfg.get(
                "weather_entity"
            )
            entities_to_check = [configured_entity] if configured_entity else []

            try:
                for state_obj in hass.states.async_all():
                    eid = state_obj.entity_id
                    if (
                        eid.startswith("weather.")
                        or "weather_" in eid
                        or "_forecast" in eid
                    ):
                        entities_to_check.append(eid)
            except Exception as err:
                _LOGGER.debug("Could not inspect hass states: %s", err)

            for eid in entities_to_check:
                st = hass.states.get(eid)
                if not st or st.state in ("unavailable", "unknown"):
                    continue
                attrs = st.attributes or {}
                temp_val = attrs.get("temperature")
                if temp_val is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        temperature = float(temp_val)
                        condition = str(st.state).lower()
                        break

        # Check calendar/holiday specials if enabled
        seasonal_terms, seasonal_label = (
            _get_seasonal_specials()
            if include_holidays and mode != "weather_only"
            else ([], "")
        )

        if temperature is not None:
            if temperature >= 22.0 or condition in ("sunny", "clear", "exceptional"):
                temp_terms = ["sommersalat", "wraps", "sommer", "grillen", "bowl"]
                temp_label = "Sommerlich leicht"
            elif temperature <= 12.0 or condition in (
                "rainy",
                "pouring",
                "snowy",
                "snowy-rainy",
                "hail",
                "windy",
            ):
                temp_terms = ["eintopf", "auflauf", "suppe", "gulasch", "schmorgericht"]
                temp_label = "Wärmend & Deftig"
            else:
                temp_terms = [
                    "schnelle gerichte",
                    "pasta",
                    "quiche",
                    "risotto",
                    "gemüse",
                ]
                temp_label = "Frisch & Ausgewogen"

            if seasonal_terms and mode != "weather_only":
                seed_terms = list(seasonal_terms) + temp_terms
                category_label = temp_label
            else:
                seed_terms = temp_terms
                category_label = temp_label
        else:
            seed_terms, category_label = (
                (seasonal_terms, seasonal_label)
                if seasonal_terms
                else (
                    ["schnelle gerichte", "pasta", "gemüsepfanne", "risotto"],
                    "Frisch & Ausgewogen",
                )
            )

    # 2. Dynamically enrich query with real-time Chefkoch search suggestions
    candidate_queries: list[str] = list(seed_terms)

    # Fetch live trending suggestions from Chefkoch API
    trending = _fetch_api_suggestions("")
    if trending:
        candidate_queries.extend(trending)

    # Fetch suggestions for a chosen seed term
    selected_seed = random.choice(seed_terms)
    seed_suggestions = _fetch_api_suggestions(selected_seed)
    if seed_suggestions:
        candidate_queries.extend(seed_suggestions)

    final_query = (
        random.choice(candidate_queries) if candidate_queries else selected_seed
    )
    return final_query, category_label


def _get_daily_url() -> tuple[str | None, str | None]:
    """Fetch featured recipe of the day cleanly via API."""
    search_cls = _get_search_class()

    # 1. Try get_chefkoch Search.recipeOfTheDay() with full exception handling
    if search_cls:
        try:
            searcher = search_cls()
            recipe = searcher.recipeOfTheDay()
            if recipe:
                recipe_id = getattr(recipe, "_id", None) or _get_id_from_url(
                    getattr(recipe, "_url", "")
                )
                if recipe_id:
                    url = f"{CHEFKOCH_BASE_URL}{recipe_id}/"
                    recipe_name = "Daily Recipe"
                    if hasattr(recipe, "_gotMeta") and recipe._gotMeta:
                        recipe_name = getattr(recipe, "name", recipe_name)
                    return url, recipe_name
        except Exception as err:
            _LOGGER.debug(
                "get_chefkoch recipeOfTheDay failed (%s), querying Chefkoch API",
                err,
            )

    # 2. Query Chefkoch REST API for Daily / Trending recipes
    trending = _fetch_api_suggestions("")
    search_seeds = trending[:3] if trending else ["Rezept des Tages", "Rezept"]

    for seed in search_seeds:
        try:
            random_offset = random.randint(0, 5)
            params = {
                "query": seed,
                "limit": "15",
                "minimumRating": "4.0",
                "sort": "rating",
                "offset": str(random_offset),
            }
            resp = requests.get(API_BASE_URL, params=params, headers=HEADERS, timeout=5)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                valid = []
                for item in results:
                    rec = item.get("recipe", {})
                    if rec and not rec.get("isPlus"):
                        rid = rec.get("id")
                        if rid:
                            valid.append(
                                (
                                    f"{CHEFKOCH_BASE_URL}{rid}/",
                                    rec.get("title", "Daily Recipe"),
                                )
                            )
                if valid:
                    choice = random.choice(valid[: min(5, len(valid))])
                    return choice[0], choice[1]
        except Exception as err:
            _LOGGER.debug(
                "API search for daily recipe failed with seed %s: %s", seed, err
            )

    return None, None


def _get_search_url(
    query_or_config: Any, limit: int = 20
) -> tuple[str | None, str | None]:
    """Fetch recipe URL cleanly using Chefkoch v2 REST API."""
    if isinstance(query_or_config, dict):
        sensor_cfg = query_or_config
        query = sensor_cfg.get("search_query", "").strip() or "Rezept"
    else:
        sensor_cfg = {"search_query": str(query_or_config)}
        query = str(query_or_config)

    # 1. Direct Chefkoch REST API search with random offset for variety
    random_offset = random.randint(0, 10)
    params: dict[str, str] = {
        "query": query,
        "limit": str(limit),
        "offset": str(random_offset),
    }

    prep_times = sensor_cfg.get("prep_times")
    if prep_times and prep_times != "Alle":
        with contextlib.suppress(ValueError):
            params["maxTime"] = str(int(prep_times))

    ratings = sensor_cfg.get("ratings")
    ratings_map = {"2": "2.0", "3": "3.0", "4": "4.0", "Top": "4.5"}
    if ratings and ratings in ratings_map:
        params["minimumRating"] = ratings_map[ratings]

    sort = sensor_cfg.get("sort")
    sort_map = {"Bewertung": "rating", "Neuheiten": "createdAt"}
    if sort and sort in sort_map:
        params["sort"] = sort_map[sort]

    try:
        resp = requests.get(API_BASE_URL, params=params, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            valid_recipes = []
            for item in data.get("results", []):
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
        _LOGGER.debug("Chefkoch API search failed (%s)", err)

    # 2. Fallback to get_chefkoch Search() if mocked/available
    search_cls = _get_search_class()
    if search_cls:
        try:
            searcher = search_cls(query)
            recipes = searcher.recipes(limit=limit)
            if recipes:
                attempts = min(5, len(recipes))
                sampled_recipes = random.sample(recipes, attempts)
                for choice in sampled_recipes:
                    recipe_id = getattr(choice, "_id", None) or _get_id_from_url(
                        getattr(choice, "_url", "")
                    )
                    if recipe_id:
                        url = f"{CHEFKOCH_BASE_URL}{recipe_id}/"
                        try:
                            chk = requests.get(url, headers=HEADERS, timeout=5)
                            if (
                                chk.status_code == 200
                                and "application/ld+json" in chk.text
                            ):
                                recipe_name = "Search Recipe"
                                if hasattr(choice, "_gotMeta") and choice._gotMeta:
                                    recipe_name = getattr(choice, "name", recipe_name)
                                return url, recipe_name
                            _LOGGER.debug("Skipping Plus or invalid recipe: %s", url)
                        except (requests.RequestException, ValueError) as e:
                            _LOGGER.debug("Error during Plus check for %s: %s", url, e)

                choice = recipes[0]
                recipe_id = _get_id_from_url(getattr(choice, "_url", ""))
                if recipe_id:
                    return f"{CHEFKOCH_BASE_URL}{recipe_id}/", "Search Recipe"
        except Exception as err:
            _LOGGER.debug("Search() fallback failed: %s", err)

    # 3. Clean fallback query to Chefkoch API if initial specific query had 0 results
    if query != "Rezept":
        try:
            fallback_resp = requests.get(
                API_BASE_URL,
                params={"query": "Rezept", "limit": "10"},
                headers=HEADERS,
                timeout=5,
            )
            if fallback_resp.status_code == 200:
                for item in fallback_resp.json().get("results", []):
                    recipe = item.get("recipe", {})
                    if recipe and not recipe.get("isPlus"):
                        rid = recipe.get("id")
                        if rid:
                            return (
                                f"{CHEFKOCH_BASE_URL}{rid}/",
                                recipe.get("title", "Search Recipe"),
                            )
        except Exception as err:
            _LOGGER.debug("Fallback query to Chefkoch API failed: %s", err)

    return None, None


async def _fetch_recipe_url(
    sensor_config: dict[str, Any], hass: Any = None
) -> str | None:
    """Fetch recipe URL based on sensor config cleanly using API."""
    import asyncio

    sensor_type = sensor_config["type"]

    try:
        _LOGGER.debug("Fetching recipe URL for sensor type: %s", sensor_type)
        url = None

        if sensor_type == "daily":
            try:
                url, _ = await asyncio.to_thread(_get_daily_url)
            except Exception as daily_err:
                _LOGGER.warning(
                    "Daily recipe fetch failed: %s. Falling back to search.",
                    daily_err,
                )

            if not url:
                url, _ = await asyncio.to_thread(_get_search_url, sensor_config)
            return url

        if sensor_type == "weather":
            if "search_query" not in sensor_config or not sensor_config["search_query"]:
                weather_query, _ = await asyncio.to_thread(
                    _get_weather_recipe_query, hass, sensor_config
                )
                cfg = dict(sensor_config)
                cfg["search_query"] = weather_query
            else:
                cfg = sensor_config
            url, _ = await asyncio.to_thread(_get_search_url, cfg)
            return url

        if sensor_type == "random":
            url, _ = await asyncio.to_thread(_get_search_url, sensor_config, 100)
            return url

        if sensor_type == "vegan":
            cfg = dict(sensor_config)
            cfg["search_query"] = "vegan"
            url, _ = await asyncio.to_thread(_get_search_url, cfg)
            return url

        if sensor_type == "vegetarian":
            cfg = dict(sensor_config)
            cfg["search_query"] = "vegetarisch"
            url, _ = await asyncio.to_thread(_get_search_url, cfg)
            return url

        if sensor_type == "baking":
            cfg = dict(sensor_config)
            cfg["search_query"] = "backen"
            url, _ = await asyncio.to_thread(_get_search_url, cfg)
            return url

        if sensor_type == "search":
            url, _ = await asyncio.to_thread(_get_search_url, sensor_config)
            return url

        return None

    except Exception:
        _LOGGER.exception(
            "Exception during recipe URL fetch for sensor type %s",
            sensor_type,
        )
        return None
