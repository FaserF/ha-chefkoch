"""Base class for recipe providers (official REST APIs only, no scraping)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from ..filters import RecipeFilter

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Tiny German -> English glossary so the weather/season queries (German) also
# work with English-only providers.
_DE_EN = {
    "suppe": "soup",
    "wärmende": "warm",
    "eintopf": "stew",
    "auflauf": "casserole",
    "gulasch": "goulash",
    "kürbis": "pumpkin",
    "kürbissuppe": "pumpkin soup",
    "salat": "salad",
    "sommersalat": "summer salad",
    "herbstsalat": "autumn salad",
    "grillen": "grill",
    "schmorgericht": "braise",
    "gemüse": "vegetable",
    "gemüsepfanne": "vegetable stir fry",
    "nudeln": "pasta",
    "pilzpfanne": "mushroom",
    "kartoffel": "potato",
    "hähnchen": "chicken",
    "rind": "beef",
    "schwein": "pork",
    "fisch": "fish",
    "lachs": "salmon",
    "reis": "rice",
    "wraps": "wrap",
    "weihnachten": "christmas",
    "ostern": "easter",
    "halloween": "halloween",
    "backen": "baking",
    "apfelkuchen": "apple pie",
    "schnelle": "quick",
    "gerichte": "dish",
    "vegan": "vegan",
    "vegetarisch": "vegetarian",
}


def translate_query(query: str) -> str:
    """Translate known German words of *query* to English (unknown words stay)."""
    words = [w for w in query.lower().replace(",", " ").split() if w]
    return " ".join(_DE_EN.get(w, w) for w in words)


class RecipeProvider:
    """Interface every recipe source implements.

    Providers are synchronous (called from the executor) and return recipes in
    the common attribute schema used by the sensors (title, url, ingredients,
    category_breadcrumb, totalTime, rating, ...).
    """

    key = ""
    name = ""
    #: language the free-text query should be in ("de", "en")
    query_language = "en"
    requires_api_key = False

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    def available(self) -> bool:
        """Whether the provider is usable (e.g. API key present)."""
        return not self.requires_api_key or bool(self.api_key)

    def search(self, flt: RecipeFilter, limit: int = 30) -> list[dict[str, Any]]:
        """Return candidate summaries (``id``, ``title``, ...) matching *flt*.

        A candidate may carry a complete recipe under ``"_recipe"``.
        """
        raise NotImplementedError

    def get_recipe(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Return the normalized recipe for a candidate."""
        raise NotImplementedError

    def enrich(self, recipe: dict[str, Any]) -> dict[str, Any]:
        """Add expensive extras (e.g. comments) to an already accepted recipe."""
        return recipe

    def query_for(self, flt: RecipeFilter) -> str:
        """Query string in the provider's language."""
        if not flt.query:
            return ""
        return translate_query(flt.query) if self.query_language == "en" else flt.query

    def _tag(self, recipe: dict[str, Any]) -> dict[str, Any]:
        recipe["provider"] = self.key
        recipe["provider_name"] = self.name
        return recipe

    @staticmethod
    def get_json(
        url: str, params: dict[str, Any] | None = None, timeout: int = 8
    ) -> Any:
        """GET *url* and return decoded JSON, or ``None`` on any failure."""
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            _LOGGER.debug("GET %s returned HTTP %s", url, resp.status_code)
        except (requests.RequestException, ValueError) as err:
            _LOGGER.debug("GET %s failed: %s", url, err)
        return None
