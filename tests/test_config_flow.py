from . import mock_ha  # noqa: F401
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.chefkoch_ha.config_flow import (
    ChefkochConfigFlow,
    ChefkochOptionsFlowHandler,
)

@pytest.mark.asyncio
async def test_config_flow_user_step():
    """Test config flow user step."""
    flow = ChefkochConfigFlow()
    flow.hass = MagicMock()
    flow._async_current_entries = MagicMock(return_value=[])
    flow.async_show_form = AsyncMock(return_value="form")
    flow.async_create_entry = MagicMock(return_value="create")
    
    # Show form
    result = await flow.async_step_user()
    assert result == "form"
    
    # Create entry
    result = await flow.async_step_user({"update_interval": 12})
    assert result == "create"

@pytest.mark.asyncio
async def test_options_flow_init():
    """Test options flow initialization."""
    entry = MagicMock()
    entry.options = {"sensors": [{"id": "1", "type": "search"}]}
    
    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = MagicMock()
    flow.async_show_menu = AsyncMock(return_value="menu")
    
    result = await flow.async_step_init()
    assert result == "menu"

@pytest.mark.asyncio
async def test_options_flow_update_interval():
    """Test options flow update interval."""
    entry = MagicMock()
    entry.options = {"update_interval": 24}
    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = MagicMock()
    flow.async_show_form = AsyncMock(return_value="form")
    flow.async_create_entry = MagicMock(return_value="create")
    
    # Show form
    assert await flow.async_step_update_interval() == "form"
    
    # Submit
    assert await flow.async_step_update_interval({"update_interval": 12}) == "create"

@pytest.mark.asyncio
async def test_options_flow_add_sensor():
    """Test options flow add sensor."""
    entry = MagicMock()
    entry.options = {"sensors": []}
    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = MagicMock()
    flow.async_show_form = AsyncMock(return_value="form")
    flow.async_create_entry = MagicMock(return_value="create")
    
    # Show form
    assert await flow.async_step_add_sensor() == "form"
    
    # Submit
    with patch("uuid.uuid4", return_value="1234"):
        assert await flow.async_step_add_sensor({"name": "Test", "prep_times": "Alle", "ratings": "Top", "properties": ["Schnell"]}) == "create"

@pytest.mark.asyncio
async def test_options_flow_remove_sensor():
    """Test options flow remove sensor."""
    entry = MagicMock()
    entry.options = {"sensors": [{"id": "1", "type": "search"}]}
    flow = ChefkochOptionsFlowHandler(entry)
    flow.hass = MagicMock()
    flow.async_show_form = AsyncMock(return_value="form")
    flow.async_create_entry = MagicMock(return_value="create")
    
    # Show form
    assert await flow.async_step_remove_sensor() == "form"
    
    # Submit
    assert await flow.async_step_remove_sensor({"sensors_to_remove": ["1"]}) == "create"
