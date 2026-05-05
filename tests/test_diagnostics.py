from . import mock_ha  # noqa: F401
from unittest.mock import MagicMock
import pytest

from custom_components.chefkoch_ha.diagnostics import async_get_config_entry_diagnostics
from custom_components.chefkoch_ha.const import DOMAIN

@pytest.mark.asyncio
async def test_async_get_config_entry_diagnostics():
    """Test diagnostics."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.as_dict.return_value = {"options": {}}
    
    coordinator = MagicMock()
    coordinator.data = {"test": "data"}
    
    mock_hass.data = {DOMAIN: {"test_entry_id": {"coordinator": coordinator}}}
    
    diagnostics = await async_get_config_entry_diagnostics(mock_hass, mock_entry)
    
    assert diagnostics["coordinator_data"] == {"test": "data"}
    assert "entry" in diagnostics
