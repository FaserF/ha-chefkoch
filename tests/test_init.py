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

    with patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher):
        with patch("requests.get", return_value=mock_response):
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

    with patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher):
        with patch("requests.get", return_value=mock_response):
            with patch("random.sample", return_value=[mock_recipe]):
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

    with patch("custom_components.chefkoch_ha.Search", return_value=mock_searcher):
        with patch("requests.get", side_effect=mock_get):
            with patch("random.sample", return_value=[recipe_plus, recipe_ok]):
                url = await _fetch_recipe_url(
                    {"type": "search", "search_query": "test"}
                )

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
