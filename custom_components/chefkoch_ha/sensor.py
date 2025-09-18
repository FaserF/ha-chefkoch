"""Sensor platform for Chefkoch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN, SENSOR_TYPES
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Chefkoch sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        ChefkochSensor(coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(entities)


class ChefkochSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Chefkoch sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_type: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = SENSOR_TYPES[sensor_type]
        self._attr_icon = "mdi:chef-hat"
        self._attr_unique_id = f"chefkoch_{sensor_type}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # The coordinator's data contains keys "random", "daily", and "vegan"
        data = self.coordinator.data.get(self._sensor_type, {})
        _LOGGER.debug(f"Sensor {self._sensor_type} state data: %s", data)
        return data.get("title", "unknown")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # The coordinator's data contains keys "random", "daily", and "vegan"
        data = self.coordinator.data.get(self._sensor_type, {})
        _LOGGER.debug(f"Sensor {self._sensor_type} attributes data: %s", data)
        return {
            "url": data.get("url", ""),
            "image_url": data.get("image_url", ""),
            "totalTime": data.get("totalTime"),
            "calories": data.get("calories"),
            "difficulty": data.get("difficulty", ""),
            "ingredients": data.get("ingredients", []),
            "category": data.get("category", ""),
        }
