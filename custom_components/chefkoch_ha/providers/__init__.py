"""Recipe provider registry.

To add a new source implement :class:`RecipeProvider` (``search`` +
``get_recipe``) and register it in :data:`PROVIDERS`.
"""

from __future__ import annotations

from typing import Any

from .base import RecipeProvider
from .chefkoch import ChefkochProvider
from .spoonacular import SpoonacularProvider
from .themealdb import TheMealDBProvider

PROVIDERS: dict[str, type[RecipeProvider]] = {
    ChefkochProvider.key: ChefkochProvider,
    TheMealDBProvider.key: TheMealDBProvider,
    SpoonacularProvider.key: SpoonacularProvider,
}
PROVIDER_LABELS: dict[str, str] = {k: cls.name for k, cls in PROVIDERS.items()}
DEFAULT_PROVIDER_ORDER = [ChefkochProvider.key]


def build_providers(
    keys: list[str] | None, options: dict[str, Any] | None = None
) -> list[RecipeProvider]:
    """Instantiate the available providers for *keys* in the given order."""
    options = options or {}
    api_keys: dict[str, str] = dict(options.get("api_keys") or {})
    if options.get("spoonacular_api_key"):
        api_keys.setdefault("spoonacular", options["spoonacular_api_key"])
    built: list[RecipeProvider] = []
    for key in keys or DEFAULT_PROVIDER_ORDER:
        cls = PROVIDERS.get(key)
        if cls is None:
            continue
        provider = cls(api_key=api_keys.get(key, ""))
        if provider.available():
            built.append(provider)
    return built


__all__ = [
    "DEFAULT_PROVIDER_ORDER",
    "PROVIDERS",
    "PROVIDER_LABELS",
    "RecipeProvider",
    "build_providers",
]
