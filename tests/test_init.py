from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.chefkoch_ha import (
    _fetch_recipe_url,
    async_setup_entry,
    async_unload_entry,
    async_update_data,
    extract_recipe_attributes,
    options_update_listener,
)
from custom_components.chefkoch_ha.const import DOMAIN

from . import mock_ha  # noqa: F401


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.options = {
        "sensors": [{"id": "test_sensor", "type": "search", "name": "Test"}],
        "update_interval": 12,
    }
    entry.add_update_listener = MagicMock()
    return entry


@pytest.mark.asyncio
async def test_setup_and_unload_entry(mock_hass, mock_config_entry):
    """Test setting up and unloading the integration."""
    with patch(
        "custom_components.chefkoch_ha.DataUpdateCoordinator"
    ) as mock_coordinator_cls:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.data = {"test_sensor": {"title": "Cached"}}
        mock_coordinator_cls.return_value = mock_coordinator

        # Setup
        assert await async_setup_entry(mock_hass, mock_config_entry) is True
        assert DOMAIN in mock_hass.data
        assert "test_entry_id" in mock_hass.data[DOMAIN]

        # Verify cache interaction
        assert mock_hass.data[DOMAIN]["cache_test_entry_id"] == mock_coordinator.data

        # Unload
        assert await async_unload_entry(mock_hass, mock_config_entry) is True
        # Entry ID should be popped, but cache should stay
        assert "test_entry_id" not in mock_hass.data[DOMAIN]
        assert "cache_test_entry_id" in mock_hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_options_update_listener(mock_hass, mock_config_entry):
    """Test that options update triggers a reload."""
    await options_update_listener(mock_hass, mock_config_entry)
    mock_hass.config_entries.async_reload.assert_called_once_with("test_entry_id")


def test_extract_recipe_attributes():
    """Test extracting attributes from a mock recipe HTML."""
    html_content = """
    <html>
    <script type="application/ld+json">
    {
        "@type": "Recipe",
        "name": "Test Recipe von Chef",
        "author": {"name": "Chef"},
        "recipeInstructions": [
            {"@type": "HowToSection", "name": "Section", "itemListElement": [{"@type": "HowToStep", "text": "Step 1"}]}
        ],
        "aggregateRating": {"ratingValue": 4.5, "ratingCount": 10, "reviewCount": 5},
        "nutrition": {"calories": "500 kcal", "proteinContent": "20 g"}
    }
    </script>
    </html>
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html_content
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        attributes = extract_recipe_attributes("http://test")

    assert attributes["title"] == "Test Recipe"
    assert attributes["status"] == "success"
    assert "Step 1" in attributes["instructions"]
    assert "Section" in attributes["instructions"]
    assert attributes["calories"] == "500 kcal"
    assert attributes["protein"] == "20 g"


def test_extract_recipe_attributes_graph():
    """Test extracting attributes when JSON-LD is wrapped in @graph."""
    html_content = """
    <html>
    <head>
    <meta property="og:image" content="https://img.chefkoch-cdn.de/test.jpg">
    </head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Recipe",
                "name": "Graph Recipe von AuthorName",
                "recipeInstructions": [
                    {"@type": "HowToStep", "text": "Mix ingredients"}
                ],
                "aggregateRating": {"ratingValue": 4.8, "ratingCount": 20}
            }
        ]
    }
    </script>
    </html>
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html_content
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        attributes = extract_recipe_attributes("http://test")

    assert attributes["title"] == "Graph Recipe"
    assert attributes["author"] == "AuthorName"
    assert attributes["status"] == "success"
    assert "Mix ingredients" in attributes["instructions"]
    assert attributes["image_url"] == "https://img.chefkoch-cdn.de/test.jpg"


def test_extract_recipe_attributes_api():
    """Test extracting attributes via API using realistic live API JSON format."""
    api_json = {
        "title": "API Spaghetti Carbonara",
        "instructions": "Cook pasta and mix with sauce.",
        "servings": 4,
        "preparationTime": 15,
        "cookingTime": 10,
        "totalTime": 25,
        "difficulty": 1,
        "recipeCuisine": "Italien",
        "previewImageUrlTemplate": "https://img.chefkoch-cdn.de/rezepte/123456/bilder/99999/<format>/carbonara.jpg",
        "nutrition": {
            "kCalories": 582,
            "proteinContent": 27.67,
            "fatContent": 20.45,
            "carbohydrateContent": 71.14,
        },
        "rating": {"rating": 4.9, "numVotes": 150},
        "ingredientGroups": [
            {
                "header": "Hauptzutaten",
                "ingredients": [
                    {
                        "amount": 400,
                        "unit": "g",
                        "name": "Spaghetti",
                        "usageInfo": "oder Tortellini",
                    },
                    {
                        "amount": 150,
                        "unit": "g",
                        "name": "Pancetta",
                        "usageInfo": ", roher",
                    },
                ],
            }
        ],
        "subtitle": "Klassiker aus Italien",
        "savedRecipesCount": 116412,
        "viewCount": 3965603,
        "miscellaneousText": "Super lecker mit etwas Knoblauch!",
        "recipeVideoId": "597",
        "tags": ["Pasta", "Italien", "Schnell"],
        "categoryBreadcrumb": [
            {"id": "61", "title": "Zubereitungsarten"},
            {"id": "164", "title": "Kochen"},
        ],
        "owner": {"displayName": "ChefMaster", "username": "chef_master_99"},
        "siteUrl": "https://www.chefkoch.de/rezepte/123456/carbonara.html",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = api_json
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        attributes = extract_recipe_attributes(
            "https://www.chefkoch.de/rezepte/123456/carbonara.html"
        )

    assert attributes["title"] == "API Spaghetti Carbonara"
    assert attributes["subtitle"] == "Klassiker aus Italien"
    assert attributes["saved_recipes_count"] == 116412
    assert attributes["view_count"] == 3965603
    assert attributes["author_notes"] == "Super lecker mit etwas Knoblauch!"
    assert attributes["video_id"] == "597"
    assert "Pasta" in attributes["tags"]
    assert "Kochen" in attributes["category_breadcrumb"]
    assert attributes["status"] == "success"
    assert attributes["author"] == "ChefMaster"
    assert attributes["cuisine"] == "Italien"
    assert attributes["difficulty"] == "einfach"
    assert attributes["calories"] == "582 kcal"
    assert attributes["protein"] == "27.67 g"
    assert (
        attributes["image_url"]
        == "https://img.chefkoch-cdn.de/rezepte/123456/bilder/99999/crop-900x600/carbonara.jpg"
    )
    assert "400 g Spaghetti (oder Tortellini)" in attributes["ingredients"]
    assert "150 g Pancetta (roher)" in attributes["ingredients"]
    assert "--- Hauptzutaten ---" in attributes["ingredients"]


def test_fetch_recipe_comments_from_api():
    """Test fetching recipe comments from API."""
    from custom_components.chefkoch_ha import fetch_recipe_comments_from_api

    comments_json = {
        "results": [
            {
                "id": "1",
                "text": "Tolle Soße!",
                "owner": {"displayName": "Anna"},
            },
            {
                "id": "2",
                "text": "Sehr lecker.",
                "owner": {"displayName": "Ben"},
            },
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = comments_json

    with patch("requests.get", return_value=mock_resp):
        comments = fetch_recipe_comments_from_api("123456", limit=2)

    assert len(comments) == 2
    assert comments[0] == "Anna: Tolle Soße!"
    assert comments[1] == "Ben: Sehr lecker."


def test_fetch_recipe_url_api_filters():
    """Test fetching recipe URL with API search filters (prep_times, ratings, sort)."""
    sensor_config = {
        "type": "search",
        "search_query": "Pasta",
        "prep_times": "30",
        "ratings": "4",
        "sort": "Bewertung",
    }
    api_response = {
        "results": [
            {
                "recipe": {
                    "id": "555555",
                    "title": "Filtered Pasta",
                    "isPlus": False,
                }
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = api_response

    with patch("requests.get", return_value=mock_resp) as mock_get:
        import asyncio

        from custom_components.chefkoch_ha import _fetch_recipe_url

        url = asyncio.run(_fetch_recipe_url(sensor_config))

    assert url == "https://www.chefkoch.de/rezepte/555555/"
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    params = kwargs.get("params", {})
    assert params.get("query") == "Pasta"
    assert params.get("maxTime") == "30"
    assert params.get("minimumRating") == "4.0"
    assert params.get("orderBy") == "rating"


def test_extract_recipe_attributes_api_fallback_to_webscraping(caplog):
    """Test fallback to webscraping with warning log when API fails."""
    html_content = """
    <html>
    <script type="application/ld+json">
    {
        "@type": "Recipe",
        "name": "Fallback Recipe von Web",
        "recipeInstructions": ["Mix well"]
    }
    </script>
    </html>
    """

    def mock_get(url, **kwargs):
        resp = MagicMock()
        if "api.chefkoch.de" in url:
            resp.status_code = 500
            resp.raise_for_status.side_effect = Exception("API Server Error 500")
        else:
            resp.status_code = 200
            resp.text = html_content
            resp.raise_for_status = MagicMock()
        return resp

    with patch("requests.get", side_effect=mock_get):
        attributes = extract_recipe_attributes(
            "https://www.chefkoch.de/rezepte/123456/fallback.html"
        )

    assert attributes["title"] == "Fallback Recipe"
    assert attributes["status"] == "success"
    assert "Falling back to less efficient webscraping" in caplog.text


def test_extract_recipe_attributes_error():
    """Test extracting attributes when fetch fails."""
    with patch("requests.get", side_effect=Exception("Failed")):
        attributes = extract_recipe_attributes("http://test")
    assert attributes["status"] == "error"


@pytest.mark.asyncio
async def test_fetch_recipe_url_daily():
    """Test fetching daily URL."""
    mock_recipe = MagicMock()
    mock_recipe._url = "https://www.chefkoch.de/rezepte/123456/test.html"
    mock_recipe._id = "123456"
    mock_recipe._gotMeta = False
    mock_searcher = MagicMock()
    mock_searcher.recipeOfTheDay.return_value = mock_recipe

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "application/ld+json"

    with (
        patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher),
        patch("requests.get", return_value=mock_response),
    ):
        url = await _fetch_recipe_url({"type": "daily"})

    assert url == "https://www.chefkoch.de/rezepte/123456/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_random():
    """Test fetching random recipe URL."""
    mock_recipe = MagicMock()
    mock_recipe._url = "https://www.chefkoch.de/rezepte/789/test.html"
    mock_recipe._id = "789"
    mock_recipe._gotMeta = False
    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [mock_recipe]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "application/ld+json"

    with (
        patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher),
        patch("requests.get", return_value=mock_response),
        patch("random.sample", return_value=[mock_recipe]),
    ):
        url = await _fetch_recipe_url({"type": "random"})

    assert url == "https://www.chefkoch.de/rezepte/789/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_plus_skip():
    """Test skipping Plus recipes."""
    recipe_plus = MagicMock()
    recipe_plus._url = "https://www.chefkoch.de/rezepte/1/plus.html"
    # Also set name/id to avoid other mock side effects
    recipe_plus._id = "1"
    recipe_plus._gotMeta = False

    recipe_ok = MagicMock()
    recipe_ok._url = "https://www.chefkoch.de/rezepte/2/ok.html"
    recipe_ok._id = "2"
    recipe_ok._gotMeta = False

    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [recipe_plus, recipe_ok]

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "/1/" in url:
            resp.text = "No JSON-LD here"
        else:
            resp.text = "application/ld+json"
        return resp

    with (
        patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher),
        patch("requests.get", side_effect=mock_get),
        patch("random.sample", return_value=[recipe_plus, recipe_ok]),
    ):
        url = await _fetch_recipe_url({"type": "search", "search_query": "test"})

    assert url == "https://www.chefkoch.de/rezepte/2/"


@pytest.mark.asyncio
async def test_async_update_data(mock_hass, mock_config_entry):
    """Test updating data for all sensors."""
    mock_hass.async_add_executor_job = AsyncMock(
        return_value={"title": "Data", "status": "success"}
    )
    with patch(
        "custom_components.chefkoch_ha._fetch_recipe_url",
        return_value=("http://recipe", "Name"),
    ):
        data = await async_update_data(mock_hass, mock_config_entry)
    assert "test_sensor" in data
    assert data["test_sensor"] == {"title": "Data", "status": "success"}


def test_scale_ingredient():
    """Test scaling numeric quantities in ingredient string."""
    from custom_components.chefkoch_ha import _scale_ingredient

    assert _scale_ingredient("400 g Spaghetti", 0.5) == "200 g Spaghetti"
    assert _scale_ingredient("150 g Pancetta", 2.0) == "300 g Pancetta"
    assert _scale_ingredient("--- Hauptzutaten ---", 2.0) == "--- Hauptzutaten ---"
    assert _scale_ingredient("Salz und Pfeffer", 2.0) == "Salz und Pfeffer"


@pytest.mark.asyncio
async def test_add_to_shopping_list_scaled(mock_hass, mock_config_entry):
    """Test add_to_shopping_list service with servings scaling."""
    from custom_components.chefkoch_ha import async_setup_entry

    mock_state = MagicMock()
    mock_state.attributes = {
        "ingredients": ["400 g Spaghetti", "150 g Pancetta"],
        "servings": "4 Port.",
    }
    mock_hass.states.get.return_value = mock_state
    mock_hass.services.async_call = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry)

    # Find the registered add_to_shopping_list handler
    handler = None
    for call in mock_hass.services.async_register.call_args_list:
        if call[0][1] == "add_to_shopping_list":
            handler = call[0][2]
            break

    assert handler is not None

    service_call = MagicMock()
    service_call.data = {"entity_id": "sensor.chefkoch_test", "servings": 2}
    await handler(service_call)

    assert mock_hass.services.async_call.call_count == 2
    mock_hass.services.async_call.assert_any_call(
        "shopping_list", "add_item", {"name": "200 g Spaghetti"}
    )
    mock_hass.services.async_call.assert_any_call(
        "shopping_list", "add_item", {"name": "75 g Pancetta"}
    )


@pytest.mark.asyncio
async def test_generate_meal_plan(mock_hass, mock_config_entry):
    """Test generate_meal_plan service fires event with meal plan entries."""
    from custom_components.chefkoch_ha import async_setup_entry

    api_response = {
        "results": [
            {
                "recipe": {
                    "id": "111111",
                    "title": "Pasta Primavera",
                    "isPlus": False,
                }
            }
        ]
    }
    recipe_attrs = {
        "title": "Pasta Primavera",
        "status": "success",
        "subtitle": "",
        "url": "https://www.chefkoch.de/rezepte/111111/",
        "ingredients": [],
        "instructions": "",
        "servings": "4",
        "top_comments": [],
    }
    mock_api_resp = MagicMock()
    mock_api_resp.status_code = 200
    mock_api_resp.json.side_effect = [api_response, recipe_attrs]

    await async_setup_entry(mock_hass, mock_config_entry)

    # Find the registered generate_meal_plan handler
    handler = None
    for call in mock_hass.services.async_register.call_args_list:
        if call[0][1] == "generate_meal_plan":
            handler = call[0][2]
            break

    assert handler is not None

    service_call = MagicMock()
    service_call.data = {"days": 2, "query": "Pasta"}

    with (
        patch(
            "custom_components.chefkoch_ha._fetch_recipe_url",
            return_value="https://www.chefkoch.de/rezepte/111111/",
        ),
        patch(
            "custom_components.chefkoch_ha.fetch_recipe_attributes_from_api",
            return_value=recipe_attrs,
        ),
    ):
        await handler(service_call)

    assert mock_hass.bus.async_fire.called
    event_name, event_data = mock_hass.bus.async_fire.call_args[0]
    assert event_name == "chefkoch_meal_plan_generated"
    assert event_data["days"] == 2
    assert event_data["query"] == "Pasta"
    assert len(event_data["meal_plan"]) == 2
    assert event_data["meal_plan"][0]["day"] == "1"
    assert event_data["meal_plan"][0]["title"] == "Pasta Primavera"
