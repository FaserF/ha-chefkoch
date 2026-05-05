from . import mock_ha  # noqa: F401
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from custom_components.chefkoch_ha import (
    async_setup_entry,
    async_unload_entry,
    options_update_listener,
    async_update_data,
    extract_recipe_attributes,
    _fetch_recipe_url,
)
from custom_components.chefkoch_ha.const import DOMAIN


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
        mock_coordinator_cls.return_value = mock_coordinator

        # Setup
        assert await async_setup_entry(mock_hass, mock_config_entry) is True
        assert DOMAIN in mock_hass.data
        assert "coordinator" in mock_hass.data[DOMAIN]["test_entry_id"]
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_config_entry, ["sensor"]
        )
        mock_hass.services.async_register.assert_called_once()

        # Unload
        assert await async_unload_entry(mock_hass, mock_config_entry) is True
        assert "test_entry_id" not in mock_hass.data[DOMAIN]
        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
            mock_config_entry, ["sensor"]
        )


@pytest.mark.asyncio
async def test_options_update_listener(mock_hass, mock_config_entry):
    """Test that options update triggers a reload."""
    await options_update_listener(mock_hass, mock_config_entry)
    mock_hass.config_entries.async_reload.assert_called_once_with("test_entry_id")


def test_extract_recipe_attributes():
    """Test extracting attributes from a mock recipe using get_chefkoch API."""
    mock_recipe = MagicMock()
    mock_recipe.name = "Test Recipe von Chef"
    mock_recipe.image = "http://image"
    mock_recipe.category = "Main"
    mock_recipe.ingredients = ["Salt"]
    mock_recipe.totalTime = "0:30:00"
    mock_recipe.prepTime = "0:10:00"
    mock_recipe.cookTime = "0:20:00"
    mock_recipe.data_dump.return_value = {
        "aggregateRating": {"ratingValue": 4.5, "ratingCount": 10, "reviewCount": 5},
        "author": {"name": "Chef"},
        "nutrition": {
            "calories": "500 kcal",
            "proteinContent": "20 g",
            "fatContent": "10 g",
            "carbohydrateContent": "50 g",
        },
        "keywords": "Tasty",
        "datePublished": "2024-01-01",
        "recipeYield": "4 Portionen",
        "recipeCuisine": "Italian",
        "video": {"contentUrl": "http://video"},
        "publisher": {"name": "Chefkoch"},
        "recipeInstructions": "Cook it",
        "difficulty": "easy",
    }

    with patch("custom_components.chefkoch_ha.Recipe", return_value=mock_recipe):
        attributes = extract_recipe_attributes("http://test")

    assert attributes["title"] == "Test Recipe"  # "von Chef" stripped
    assert attributes["status"] == "success"
    assert attributes["author"] == "Chef"
    assert attributes["calories"] == "500 kcal"
    assert attributes["protein"] == "20 g"
    assert attributes["fat"] == "10 g"
    assert attributes["carbohydrates"] == "50 g"
    assert attributes["cuisine"] == "Italian"
    assert attributes["video_url"] == "http://video"
    assert attributes["rating"] == 4.5
    assert attributes["number_ratings"] == 10
    assert attributes["number_reviews"] == 5
    assert attributes["totalTime"] == "0:30:00"


def test_extract_recipe_attributes_error():
    """Test extracting attributes when recipe parsing fails."""
    with patch("custom_components.chefkoch_ha.Recipe", side_effect=Exception("Failed")):
        attributes = extract_recipe_attributes("http://test")
    assert attributes["title"] == "Error loading recipe"
    assert attributes["status"] == "error"


@pytest.mark.asyncio
async def test_fetch_recipe_url_daily():
    """Test fetching daily (recipe of the day) URL."""
    mock_recipe = MagicMock()
    mock_recipe.id = "123456"
    mock_searcher = MagicMock()
    mock_searcher.recipeOfTheDay.return_value = mock_recipe

    with patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher):
        url = await _fetch_recipe_url({"type": "daily"})

    assert url == "https://www.chefkoch.de/rezepte/123456/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_random():
    """Test fetching random recipe URL."""
    mock_recipe = MagicMock()
    mock_recipe.id = "789"
    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [mock_recipe]

    with patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher):
        with patch(
            "custom_components.chefkoch_ha.random.choice", return_value=mock_recipe
        ):
            url = await _fetch_recipe_url({"type": "random"})

    assert url == "https://www.chefkoch.de/rezepte/789/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_vegan():
    """Test fetching vegan recipe URL."""
    mock_recipe = MagicMock()
    mock_recipe.id = "111"
    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [mock_recipe]

    with patch(
        "custom_components.chefkoch_ha.Search", return_value=mock_searcher
    ) as mock_search_cls:
        with patch(
            "custom_components.chefkoch_ha.random.choice", return_value=mock_recipe
        ):
            url = await _fetch_recipe_url({"type": "vegan"})

    mock_search_cls.assert_called_with("vegan")
    assert url == "https://www.chefkoch.de/rezepte/111/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_vegetarian():
    """Test fetching vegetarian recipe URL."""
    mock_recipe = MagicMock()
    mock_recipe.id = "222"
    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [mock_recipe]

    with patch(
        "custom_components.chefkoch_ha.Search", return_value=mock_searcher
    ) as mock_search_cls:
        with patch(
            "custom_components.chefkoch_ha.random.choice", return_value=mock_recipe
        ):
            url = await _fetch_recipe_url({"type": "vegetarian"})

    mock_search_cls.assert_called_with("vegetarisch")
    assert url == "https://www.chefkoch.de/rezepte/222/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_baking():
    """Test fetching baking recipe URL."""
    mock_recipe = MagicMock()
    mock_recipe.id = "333"
    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [mock_recipe]

    with patch(
        "custom_components.chefkoch_ha.Search", return_value=mock_searcher
    ) as mock_search_cls:
        with patch(
            "custom_components.chefkoch_ha.random.choice", return_value=mock_recipe
        ):
            url = await _fetch_recipe_url({"type": "baking"})

    mock_search_cls.assert_called_with("backen")
    assert url == "https://www.chefkoch.de/rezepte/333/"


@pytest.mark.asyncio
async def test_fetch_recipe_url_search():
    """Test fetching search recipe URL."""
    mock_recipe = MagicMock()
    mock_recipe.id = "444"
    mock_searcher = MagicMock()
    mock_searcher.recipes.return_value = [mock_recipe]

    with patch(
        "custom_components.chefkoch_ha.Search", return_value=mock_searcher
    ) as mock_search_cls:
        with patch(
            "custom_components.chefkoch_ha.random.choice", return_value=mock_recipe
        ):
            url = await _fetch_recipe_url({"type": "search", "search_query": "Pasta"})

    mock_search_cls.assert_called_with("Pasta")
    assert url == "https://www.chefkoch.de/rezepte/444/"


@pytest.mark.asyncio
async def test_async_update_data(mock_hass, mock_config_entry):
    """Test updating data for all sensors."""
    mock_hass.async_add_executor_job = AsyncMock(
        return_value={"title": "Data", "status": "success"}
    )
    with patch(
        "custom_components.chefkoch_ha._fetch_recipe_url", return_value="http://recipe"
    ):
        data = await async_update_data(mock_hass, mock_config_entry)
    assert "test_sensor" in data
    assert data["test_sensor"] == {"title": "Data", "status": "success"}


@pytest.mark.asyncio
async def test_async_update_data_no_url(mock_hass, mock_config_entry):
    """Test updating data when URL fetch returns None."""
    with patch("custom_components.chefkoch_ha._fetch_recipe_url", return_value=None):
        data = await async_update_data(mock_hass, mock_config_entry)
    assert "test_sensor" in data
    assert data["test_sensor"]["status"] == "warning"


@pytest.mark.asyncio
async def test_async_update_data_error(mock_hass, mock_config_entry):
    """Test updating data when an exception occurs."""
    with patch(
        "custom_components.chefkoch_ha._fetch_recipe_url",
        side_effect=Exception("Network error"),
    ):
        data = await async_update_data(mock_hass, mock_config_entry)
    assert "test_sensor" in data
    assert data["test_sensor"]["status"] == "error"
    assert "Network error" in data["test_sensor"]["error_message"]


@pytest.mark.asyncio
async def test_async_update_data_no_sensors(mock_hass):
    """Test updating data with no sensors configured."""
    entry = MagicMock()
    entry.options = {}
    data = await async_update_data(mock_hass, entry)
    assert data == {}
