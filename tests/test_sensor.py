from . import mock_ha  # noqa: F401
from unittest.mock import MagicMock
import pytest

from custom_components.chefkoch_ha.sensor import async_setup_entry, ChefkochSensor
from custom_components.chefkoch_ha.const import DOMAIN

@pytest.mark.asyncio
async def test_async_setup_entry():
    """Test setting up sensors."""
    mock_hass = MagicMock()
    mock_hass.data = {DOMAIN: {"test_entry_id": {"coordinator": MagicMock()}}}
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.options = {"sensors": [{"id": "test_id", "type": "daily", "name": "Daily"}]}
    
    async_add_entities = MagicMock()
    await async_setup_entry(mock_hass, mock_entry, async_add_entities)
    async_add_entities.assert_called_once()

def test_chefkoch_sensor():
    """Test ChefkochSensor properties."""
    coordinator = MagicMock()
    coordinator.data = {"test_id": {"title": "Test Recipe", "calories": "500"}}
    sensor_config = {"id": "test_id", "name": "Daily Recipe"}
    
    sensor = ChefkochSensor(coordinator, sensor_config)
    
    # Check if coordinator.data is indeed a dict in the test
    assert isinstance(coordinator.data, dict)
    
    assert sensor.name == "Chefkoch Daily Recipe"
    assert sensor.native_value == "Test Recipe"
    assert sensor.extra_state_attributes["calories"] == "500"

def test_chefkoch_sensor_unknown_value():
    """Test ChefkochSensor when data is missing."""
    coordinator = MagicMock()
    coordinator.data = {}
    sensor_config = {"id": "test_id", "name": "Chefkoch Test"}
    
    sensor = ChefkochSensor(coordinator, sensor_config)
    assert sensor.native_value == "unknown"
