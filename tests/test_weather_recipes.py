"""Tests for Chefkoch weather- and season-based recipe recommendations."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

from custom_components.chefkoch_ha.recipe_fetcher import (
    _get_seasonal_specials,
    _get_weather_recipe_query,
)


def test_seasonal_specials_halloween():
    """Test seasonal keywords around Halloween."""
    halloween_dt = datetime(2026, 10, 31, 12, 0)
    keywords, label = _get_seasonal_specials(halloween_dt)
    assert "halloween" in keywords
    assert "Halloween" in label


def test_seasonal_specials_christmas():
    """Test seasonal keywords during December."""
    xmas_dt = datetime(2026, 12, 24, 18, 0)
    keywords, label = _get_seasonal_specials(xmas_dt)
    assert "weihnachten" in keywords
    assert "Weihnachtliche" in label


def test_seasonal_specials_summer():
    """Test seasonal keywords during summer."""
    summer_dt = datetime(2026, 7, 15, 12, 0)
    keywords, label = _get_seasonal_specials(summer_dt)
    assert any(k in ["sommersalat", "wraps", "grillen"] for k in keywords)
    assert "Sommerlich" in label


def test_get_weather_recipe_query_hot():
    """Test query generation when weather is hot."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.entity_id = "weather.home"
    mock_state.state = "sunny"
    mock_state.attributes = {"temperature": 28.5}
    mock_hass.states.async_all.return_value = [mock_state]
    mock_hass.states.get.return_value = mock_state

    with patch(
        "custom_components.chefkoch_ha.recipe_fetcher._fetch_api_suggestions",
        return_value=["sommerrollen", "sommersalat"],
    ):
        query, category = _get_weather_recipe_query(mock_hass)

    assert category == "Sommerlich leicht"
    assert isinstance(query, str)
    assert len(query) > 0


def test_get_weather_recipe_query_cold():
    """Test query generation when weather is cold or rainy."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.entity_id = "weather.home"
    mock_state.state = "rainy"
    mock_state.attributes = {"temperature": 8.0}
    mock_hass.states.async_all.return_value = [mock_state]
    mock_hass.states.get.return_value = mock_state

    with patch(
        "custom_components.chefkoch_ha.recipe_fetcher._fetch_api_suggestions",
        return_value=["kürbissuppe", "eintopf"],
    ):
        query, category = _get_weather_recipe_query(mock_hass)

    assert category == "Wärmend & Deftig"
    assert isinstance(query, str)
    assert len(query) > 0


def test_get_weather_recipe_query_explicit_halloween():
    """Test query generation with explicit Halloween mode in options."""
    mock_hass = MagicMock()
    opts = {"weather_seasonal_mode": "halloween"}

    with patch(
        "custom_components.chefkoch_ha.recipe_fetcher._fetch_api_suggestions",
        return_value=["halloween fingerfood", "halloween kuchen"],
    ):
        query, category = _get_weather_recipe_query(mock_hass, options=opts)

    assert "Halloween" in category
    assert isinstance(query, str)
    assert len(query) > 0


def test_get_weather_recipe_query_explicit_christmas():
    """Test query generation with explicit Christmas mode in options."""
    mock_hass = MagicMock()
    opts = {"weather_seasonal_mode": "christmas"}

    with patch(
        "custom_components.chefkoch_ha.recipe_fetcher._fetch_api_suggestions",
        return_value=["weihnachtsplätzchen", "weihnachtsbraten"],
    ):
        query, category = _get_weather_recipe_query(mock_hass, options=opts)

    assert "Weihnachtliche" in category
    assert isinstance(query, str)
    assert len(query) > 0


def test_fetch_recipe_url_weather_type():
    """Test fetching recipe URL for weather type sensor."""
    sensor_config = {
        "id": "weather",
        "type": "weather",
        "name": "Chefkoch Weather Recipe",
    }
    api_response = {
        "results": [
            {
                "recipe": {
                    "id": "777888",
                    "title": "Wärmender Gemüseeintopf",
                    "isPlus": False,
                }
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = api_response

    with (
        patch("requests.get", return_value=mock_resp),
        patch(
            "custom_components.chefkoch_ha.recipe_fetcher._get_weather_recipe_query",
            return_value=("Eintopf", "Wärmend & Deftig"),
        ),
    ):
        from custom_components.chefkoch_ha import _fetch_recipe_url

        url = asyncio.run(_fetch_recipe_url(sensor_config))

    assert url == "https://www.chefkoch.de/rezepte/777888/"
