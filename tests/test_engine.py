"""Tests for the provider-agnostic engine and the providers."""

from unittest.mock import patch

from custom_components.chefkoch_ha.engine import (
    build_filter,
    find_recipes_sync,
    resolve_provider_keys,
)
from custom_components.chefkoch_ha.filters import RecipeFilter
from custom_components.chefkoch_ha.providers import build_providers
from custom_components.chefkoch_ha.providers.base import RecipeProvider, translate_query
from custom_components.chefkoch_ha.providers.chefkoch import ChefkochProvider
from custom_components.chefkoch_ha.providers.themealdb import TheMealDBProvider

from . import mock_ha  # noqa: F401


class FakeProvider(RecipeProvider):
    key = "fake"
    name = "Fake"

    def __init__(self, recipes, key="fake"):
        super().__init__()
        self.key = key
        self._recipes = recipes

    def search(self, flt, limit=30):
        return [
            {"id": r["title"], "title": r["title"], "url": r["url"]}
            for r in self._recipes
        ]

    def get_recipe(self, candidate):
        return next(dict(r) for r in self._recipes if r["title"] == candidate["id"])


def _r(title, **extra):
    return {"title": title, "url": f"https://x/{title}", "status": "success", **extra}


def test_engine_applies_filters_and_count():
    provider = FakeProvider(
        [
            _r("Apfelkuchen"),
            _r("Linsensuppe"),
            _r("Gulasch", category_breadcrumb=["Hauptspeise"]),
            _r("Chili", totalTime="2:00:00"),
        ]
    )
    flt = RecipeFilter.from_dict({"meal_type": "main", "max_total_minutes": 60})
    results = find_recipes_sync([provider], flt, count=5)
    assert sorted(r["title"] for r in results) == ["Gulasch", "Linsensuppe"]


def test_engine_excludes_seen_urls_and_falls_back_to_next_provider():
    primary = FakeProvider([_r("Kuchen")], key="a")
    secondary = FakeProvider([_r("Suppe"), _r("Gulasch")], key="b")
    flt = RecipeFilter.from_dict({"meal_type": "main"})
    results = find_recipes_sync(
        [primary, secondary], flt, count=1, exclude_urls={"https://x/Suppe"}
    )
    assert [r["title"] for r in results] == ["Gulasch"]


def test_build_filter_layers():
    options = {"filters": {"meal_type": "main", "exclude_keywords": ["Torte"]}}
    # type preset beats global defaults: baking must still deliver baked goods
    assert build_filter(options, "baking").meal_type == "any"
    assert build_filter(options, "vegan").diets == ["vegan"]
    # sensor config beats the preset, service overrides beat everything
    flt = build_filter(
        options, "vegan", {"meal_type": "soup"}, {"max_total_minutes": 20}
    )
    assert (flt.meal_type, flt.max_total_minutes, flt.exclude_keywords) == (
        "soup",
        20,
        ["Torte"],
    )
    # without configured filters dinner is the default
    assert build_filter({}, "random").meal_type == "main"
    assert build_filter({}, "random", overrides={"meal_type": "any"}).meal_type == "any"


def test_resolve_provider_keys_priority():
    options = {"providers": ["chefkoch", "themealdb"]}
    assert resolve_provider_keys(options) == ["chefkoch", "themealdb"]
    assert resolve_provider_keys(options, {"provider": "themealdb"}) == ["themealdb"]
    assert resolve_provider_keys(options, {"provider": "themealdb"}, ["chefkoch"]) == [
        "chefkoch"
    ]
    assert resolve_provider_keys({}) == ["chefkoch"]
    assert resolve_provider_keys(options, {"provider": "auto"}) == [
        "chefkoch",
        "themealdb",
    ]


def test_build_providers_skips_keyless_spoonacular():
    assert [p.key for p in build_providers(["spoonacular", "themealdb"], {})] == [
        "themealdb"
    ]
    keyed = build_providers(["spoonacular"], {"spoonacular_api_key": "k"})
    assert [p.key for p in keyed] == ["spoonacular"]


def test_translate_query():
    assert translate_query("Kürbissuppe") == "pumpkin soup"
    assert translate_query("Pasta Salat") == "pasta salad"


def test_chefkoch_search_uses_server_side_category_and_skips_plus():
    api = {
        "results": [
            {"recipe": {"id": "111111", "title": "A", "isPlus": False}},
            {"recipe": {"id": "222222", "title": "B", "isPlus": True}},
        ]
    }
    flt = RecipeFilter.from_dict(
        {"diets": ["vegan"], "min_rating": 4, "sort": "rating"}
    )
    with patch.object(RecipeProvider, "get_json", return_value=api) as get_json:
        cands = ChefkochProvider().search(flt)
    params = get_json.call_args.args[1]
    assert params["categories"] == "111"
    assert params["minimumRating"] == "4"
    assert params["orderBy"] == "3"
    assert [c["id"] for c in cands] == ["111111"]


def test_themealdb_normalizes_meal():
    meal = {
        "idMeal": "52772",
        "strMeal": "Teriyaki Chicken",
        "strCategory": "Chicken",
        "strArea": "Japanese",
        "strInstructions": "Cook.",
        "strMealThumb": "https://img/x.jpg",
        "strTags": "Meat,Casserole",
        "strIngredient1": "soy sauce",
        "strMeasure1": "3/4 cup",
        "strIngredient2": "",
        "strMeasure2": "",
    }
    provider = TheMealDBProvider()
    with patch.object(RecipeProvider, "get_json", return_value={"meals": [meal]}):
        cands = provider.search(RecipeFilter.from_dict({"query": "Hähnchen"}))
        recipe = provider.get_recipe(cands[0])
    assert recipe["title"] == "Teriyaki Chicken"
    assert recipe["ingredients"] == ["3/4 cup soy sauce"]
    assert recipe["category_breadcrumb"] == ["Chicken", "Japanese"]
    assert recipe["provider"] == "themealdb"
    assert RecipeFilter.from_dict({"meal_type": "main"}).reject_reason(recipe) is None
    dessert = {**meal, "strCategory": "Dessert", "strMeal": "Pie"}
    assert (
        RecipeFilter.from_dict({"meal_type": "main"}).reject_reason(
            provider._normalize(dessert)
        )
        is not None
    )
