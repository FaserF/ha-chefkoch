"""Tests for the universal recipe filter."""

from custom_components.chefkoch_ha.filters import (
    RecipeFilter,
    parse_list,
    parse_minutes,
    title_looks_like_dessert,
)

from . import mock_ha  # noqa: F401


def _recipe(title="Gemüsecremesuppe", **extra):
    return {"title": title, "status": "success", **extra}


def test_parse_helpers():
    assert parse_list("a, b;c\nd") == ["a", "b", "c", "d"]
    assert parse_list(["x", " ", "y"]) == ["x", "y"]
    assert parse_list(None) == []
    assert parse_minutes("0:25:00") == 25
    assert parse_minutes("1 day, 2:00:00") == 1560
    assert parse_minutes(45) == 45
    assert parse_minutes("") is None


def test_dessert_title_heuristic():
    for title in (
        "Veganer Schokokuchen",
        "Apfelkuchen mit Streuseln",
        "Tiramisu",
        "Eis",
    ):
        assert title_looks_like_dessert(title), title
    for title in (
        "Gemüsecremesuppe",
        "Reis mit Gemüse",
        "Herzhafte Pfannkuchen",
        "Flammkuchen Elsässer Art",
        "Spaghetti Carbonara",
    ):
        assert not title_looks_like_dessert(title), title


def test_main_meal_type_rejects_desserts():
    flt = RecipeFilter.from_dict({"meal_type": "main"})
    assert flt.quick_reject({"title": "Apfelkuchen mit Streuseln"})
    assert flt.quick_reject({"title": "Gemüsecremesuppe"}) is None
    assert flt.reject_reason(_recipe("Irgendwas", category_breadcrumb=["Dessert"]))
    # a main-dish category wins over a sweet-sounding title
    assert (
        flt.reject_reason(
            _recipe("Kaiserschmarrenkuchen", category_breadcrumb=["Hauptspeise"])
        )
        is None
    )
    # "Reis" must not be mistaken for the "Eis" category
    assert (
        flt.reject_reason(_recipe(category_breadcrumb=["Reis- oder Nudelsalat"]))
        is None
    )


def test_main_rejects_sweets_by_tags():
    flt = RecipeFilter.from_dict({"meal_type": "main"})
    sweet = _recipe(
        "Schokocrossies",
        category_breadcrumb=["Spezielles", "Ernährungskonzepte", "Vegan"],
        tags=["Konfiserie", "Schnell", "vegan"],
    )
    assert flt.reject_reason(sweet) is not None
    assert flt.quick_reject({"title": "Schokocrossies"}) is not None


def test_dessert_meal_type_requires_dessert():
    flt = RecipeFilter.from_dict({"meal_type": "dessert"})
    assert flt.reject_reason(_recipe("Käsekuchen")) is None
    assert flt.reject_reason(_recipe("Gulasch")) is not None


def test_keyword_and_ingredient_filters():
    flt = RecipeFilter.from_dict(
        {"exclude_keywords": "Torte, Kuchen", "exclude_ingredients": ["Fisch"]}
    )
    assert flt.reject_reason(_recipe("Käsekuchen")) is not None
    assert flt.reject_reason(_recipe(ingredients=["200 g Fischfilet"])) is not None
    assert flt.reject_reason(_recipe(ingredients=["200 g Kartoffeln"])) is None
    inc = RecipeFilter.from_dict({"include_keywords": ["Kürbis"]})
    assert inc.reject_reason(_recipe("Kürbissuppe")) is None
    assert inc.reject_reason(_recipe("Tomatensuppe")) is not None


def test_time_rating_difficulty_calories():
    flt = RecipeFilter.from_dict(
        {
            "max_total_minutes": 60,
            "min_rating": 4,
            "max_difficulty": "normal",
            "max_calories": 600,
        }
    )
    assert flt.reject_reason(_recipe(totalTime="1:30:00"))
    assert flt.reject_reason(_recipe(totalTime="0:45:00", rating=3.5))
    assert flt.reject_reason(_recipe(rating=4.5, difficulty="pfiffig"))
    assert flt.reject_reason(_recipe(rating=4.5, calories="900 kcal"))
    assert (
        flt.reject_reason(
            _recipe(
                totalTime="0:45:00",
                rating=4.5,
                difficulty="einfach",
                calories="450 kcal",
            )
        )
        is None
    )
    # unknown values never reject
    assert flt.reject_reason(_recipe()) is None


def test_legacy_search_sensor_config_is_understood():
    flt = RecipeFilter.from_dict(
        {
            "search_query": "Pasta",
            "meal_type": ["Hauptspeise"],
            "health": ["Vegan", "Low Carb"],
            "prep_times": "30",
            "ratings": "Top",
            "countries": ["Italien"],
            "sort": "Bewertung",
            "properties": ["Einfach"],
        }
    )
    assert flt.query == "Pasta"
    assert flt.meal_type == "main"
    assert flt.diets == ["vegan", "low_carb"]
    assert flt.max_total_minutes == 30
    assert flt.min_rating == 4.5
    assert flt.categories == ["Italien"]
    assert flt.sort == "rating"
    assert flt.max_difficulty == "einfach"
    # legacy "no filter" values stay empty
    empty = RecipeFilter.from_dict(
        {"prep_times": "Alle", "ratings": "Alle", "sort": "Empfehlung", "meal_type": []}
    )
    assert empty.to_dict() == {"sort": "relevance"}


def test_layered_merge():
    base = RecipeFilter.from_dict({"meal_type": "main", "exclude_keywords": ["Torte"]})
    override = RecipeFilter.from_dict({"meal_type": "any", "max_total_minutes": 20})
    merged = base.merged(override)
    assert merged.meal_type == "any"
    assert merged.max_total_minutes == 20
    assert merged.exclude_keywords == ["Torte"]
    assert base.meal_type == "main"  # inputs untouched
