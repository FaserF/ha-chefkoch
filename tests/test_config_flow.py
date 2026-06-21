import importlib
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# Ensure mock_ha is applied before anything else
from . import mock_ha  # noqa: F401

# Reload the config_flow module to ensure it picks up the mocks
import custom_components.chefkoch_ha.config_flow

importlib.reload(custom_components.chefkoch_ha.config_flow)

from custom_components.chefkoch_ha.config_flow import (  # noqa: E402
    ChefkochConfigFlow,
    ChefkochOptionsFlowHandler,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.mark.asyncio
async def test_config_flow_user_step(mock_hass):
    """Test config flow user step."""
    flow = ChefkochConfigFlow()
    flow.hass = mock_hass
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    # Show form
    result = await flow.async_step_user()
    assert result["type"] == "form"

    # Create entry
    result = await flow.async_step_user({"update_interval": 12})
    assert result["type"] == "create_entry"


@pytest.mark.asyncio
async def test_options_flow_init(mock_hass):
    """Test options flow initialization."""
    entry = MagicMock()
    entry.options = {"sensors": [{"id": "1", "type": "search"}]}

    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = mock_hass
    flow.async_show_menu = MagicMock(return_value={"type": "menu"})

    result = await flow.async_step_init()
    assert result["type"] == "menu"


@pytest.mark.asyncio
async def test_options_flow_add_sensor_with_suggestions(mock_hass):
    """Test options flow add sensor with suggestions."""
    entry = MagicMock()
    entry.options = {"sensors": []}
    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(
        side_effect=lambda step_id, **kwargs: {"type": "form", "step_id": step_id}
    )
    flow.async_create_entry = MagicMock(
        return_value={
            "type": "create_entry",
            "data": {"sensors": [{"name": "My Pasta"}]},
        }
    )

    # Step 1: Search query
    mock_hass.async_add_executor_job.return_value = {"suggestions": ["Pasta Carbonara"]}
    result = await flow.async_step_add_sensor({"search_query": "Pasta"})
    assert result["type"] == "form"
    assert result["step_id"] == "add_sensor_suggestions"

    # Step 2: Choose suggestion
    result = await flow.async_step_add_sensor_suggestions(
        {"suggestion": "Pasta Carbonara"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_sensor_form"

    # Step 3: Final form
    with patch("uuid.uuid4", return_value="1234"):
        result = await flow.async_step_add_sensor_form(
            {"name": "My Pasta", "search_query": "Pasta Carbonara"}
        )
        assert result["type"] == "create_entry"


@pytest.mark.asyncio
async def test_options_flow_remove_sensor(mock_hass):
    """Test options flow remove sensor."""
    entry = MagicMock()
    entry.entry_id = "test"
    entry.options = {"sensors": [{"id": "1", "type": "search", "name": "Test"}]}
    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow.async_create_entry = MagicMock(
        return_value={"type": "create_entry", "data": {"sensors": []}}
    )

    # Show form
    result = await flow.async_step_remove_sensor()
    assert result["type"] == "form"

    # Submit
    result = await flow.async_step_remove_sensor({"sensors_to_remove": ["1"]})
    assert result["type"] == "create_entry"
    assert len(result["data"]["sensors"]) == 0
