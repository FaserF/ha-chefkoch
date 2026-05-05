from . import mock_ha  # noqa: F401
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from custom_components.chefkoch_ha import (
    async_setup_entry,
    async_unload_entry,
    options_update_listener,
    async_update_data,
    extract_recipe_attributes,
    _fetch_recipe_url
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
        "update_interval": 12
    }
    entry.add_update_listener = MagicMock()
    return entry

@pytest.mark.asyncio
async def test_setup_and_unload_entry(mock_hass, mock_config_entry):
    """Test setting up and unloading the integration."""
    with patch("custom_components.chefkoch_ha.DataUpdateCoordinator") as mock_coordinator_cls:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_cls.return_value = mock_coordinator
        
        # Setup
        assert await async_setup_entry(mock_hass, mock_config_entry) is True
        assert DOMAIN in mock_hass.data
        assert "coordinator" in mock_hass.data[DOMAIN]["test_entry_id"]
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(mock_config_entry, ["sensor"])
        
        # Unload
        assert await async_unload_entry(mock_hass, mock_config_entry) is True
        assert "test_entry_id" not in mock_hass.data[DOMAIN]
        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(mock_config_entry, ["sensor"])

@pytest.mark.asyncio
async def test_options_update_listener(mock_hass, mock_config_entry):
    """Test that options update triggers a reload."""
    await options_update_listener(mock_hass, mock_config_entry)
    mock_hass.config_entries.async_reload.assert_called_once_with("test_entry_id")

def test_extract_recipe_attributes():
    """Test extracting attributes from a mock recipe."""
    with patch("custom_components.chefkoch_ha.Recipe") as mock_recipe_cls:
        mock_recipe = MagicMock()
        mock_recipe.title = "Test Recipe"
        mock_recipe.url = "http://test"
        mock_recipe.image_url = "http://image"
        mock_recipe.calories = "500"
        mock_recipe.difficulty = "easy"
        mock_recipe.ingredients = ["Salt"]
        mock_recipe.instructions = ["Cook"]
        mock_recipe.category = "Main"
        mock_recipe.servings = "4"
        mock_recipe.author = "Chef"
        mock_recipe.publisher = "Publisher"
        mock_recipe.keywords = "Tasty"
        mock_recipe.date_published = "2024-01-01"
        mock_recipe.rating = {"rating": 4.5, "count": 10}
        mock_recipe.number_ratings = 10
        mock_recipe.number_reviews = 5
        mock_recipe.total_time = "1h"
        mock_recipe.prep_time = "30m"
        mock_recipe.cook_time = "30m"
        mock_recipe.rest_time = ""
        mock_recipe_cls.return_value = mock_recipe

        attributes = extract_recipe_attributes("http://test")
        assert attributes["title"] == "Test Recipe"
        assert attributes["status"] == "success"
        assert attributes["author"] == "Chef"
        assert attributes["totalTime"] == "1h"

def test_extract_recipe_attributes_error():
    """Test extracting attributes when recipe parsing fails."""
    with patch("custom_components.chefkoch_ha.Recipe", side_effect=Exception("Failed")):
        attributes = extract_recipe_attributes("http://test")
        assert attributes["title"] == "Error loading recipe"
        assert attributes["status"] == "error"

@pytest.mark.asyncio
async def test_fetch_recipe_url_random():
    """Test fetching random recipe URL."""
    with patch("custom_components.chefkoch_ha.RandomRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_recipe = MagicMock()
        mock_recipe.url = "http://random"
        mock_retriever.get_recipe.return_value = mock_recipe
        mock_retriever_cls.return_value = mock_retriever

        url = await _fetch_recipe_url({"type": "random"})
        assert url == "http://random"

@pytest.mark.asyncio
async def test_fetch_recipe_url_daily():
    """Test fetching daily recipe URL."""
    with patch("custom_components.chefkoch_ha.DailyRecipeRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_recipe = MagicMock()
        mock_recipe.url = "http://daily"
        mock_retriever.get_recipes.return_value = [mock_recipe]
        mock_retriever_cls.return_value = mock_retriever

        url = await _fetch_recipe_url({"type": "daily"})
        assert url == "http://daily"

@pytest.mark.asyncio
async def test_fetch_recipe_url_vegan():
    """Test fetching vegan recipe URL."""
    with patch("custom_components.chefkoch_ha.SearchRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_recipe = MagicMock()
        mock_recipe.url = "http://vegan"
        mock_retriever.get_recipes.return_value = [mock_recipe]
        mock_retriever_cls.return_value = mock_retriever

        url = await _fetch_recipe_url({"type": "vegan"})
        assert url == "http://vegan"
        mock_retriever_cls.assert_called_with(health=["Vegan"])

@pytest.mark.asyncio
async def test_fetch_recipe_url_vegetarian():
    """Test fetching vegetarian recipe URL."""
    with patch("custom_components.chefkoch_ha.SearchRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_recipe = MagicMock()
        mock_recipe.url = "http://veg"
        mock_retriever.get_recipes.return_value = [mock_recipe]
        mock_retriever_cls.return_value = mock_retriever

        url = await _fetch_recipe_url({"type": "vegetarian"})
        assert url == "http://veg"
        mock_retriever_cls.assert_called_with(health=["Vegetarisch"])

@pytest.mark.asyncio
async def test_fetch_recipe_url_baking():
    """Test fetching baking recipe URL."""
    with patch("custom_components.chefkoch_ha.DailyRecipeRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_recipe = MagicMock()
        mock_recipe.url = "http://baking"
        mock_retriever.get_recipes.return_value = [mock_recipe]
        mock_retriever_cls.return_value = mock_retriever

        url = await _fetch_recipe_url({"type": "baking"})
        assert url == "http://baking"
        mock_retriever.get_recipes.assert_called_with(type="backen")

@pytest.mark.asyncio
async def test_fetch_recipe_url_search():
    """Test fetching search recipe URL."""
    with patch("custom_components.chefkoch_ha.SearchRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_recipe = MagicMock()
        mock_recipe.url = "http://search"
        mock_retriever.get_recipes.return_value = [mock_recipe]
        mock_retriever_cls.return_value = mock_retriever

        config = {
            "type": "search",
            "search_query": "Pasta",
            "properties": "Einfach, Schnell"
        }
        url = await _fetch_recipe_url(config)
        assert url == "http://search"
        mock_retriever_cls.assert_called_with(properties=["Einfach", "Schnell"])
        mock_retriever.get_recipes.assert_called_with(search_query="Pasta")

@pytest.mark.asyncio
async def test_async_update_data(mock_hass, mock_config_entry):
    """Test updating data for all sensors."""
    mock_hass.async_add_executor_job = AsyncMock(return_value={"title": "Data"})
    with patch("custom_components.chefkoch_ha._fetch_recipe_url", return_value="http://recipe"):
        data = await async_update_data(mock_hass, mock_config_entry)
        assert "test_sensor" in data
        assert data["test_sensor"] == {"title": "Data"}

@pytest.mark.asyncio
async def test_async_update_data_no_url(mock_hass, mock_config_entry):
    """Test updating data when URL fetch fails."""
    with patch("custom_components.chefkoch_ha._fetch_recipe_url", return_value=None):
        data = await async_update_data(mock_hass, mock_config_entry)
        assert "test_sensor" in data
        assert data["test_sensor"]["status"] == "warning"

@pytest.mark.asyncio
async def test_async_update_data_error(mock_hass, mock_config_entry):
    """Test updating data when an exception occurs."""
    with patch("custom_components.chefkoch_ha._fetch_recipe_url", side_effect=Exception("Network error")):
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
