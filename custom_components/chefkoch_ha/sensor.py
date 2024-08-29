"""Sensor platform for Chefkoch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, SENSOR_TYPES
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Chefkoch sensor platform."""
    coordinators = {
        "random": hass.data[DOMAIN][entry.entry_id]["coordinator_random"],
        "daily": hass.data[DOMAIN][entry.entry_id]["coordinator_daily"],
        "vegan": hass.data[DOMAIN][entry.entry_id]["coordinator_vegan"],
    }
    entities = [ChefkochSensor(coordinator, sensor_type) for sensor_type, coordinator in coordinators.items()]
    async_add_entities(entities)

class ChefkochSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Chefkoch sensor."""

    def __init__(self, coordinator, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = SENSOR_TYPES[sensor_type]
        self._sensor_type = sensor_type
        self._attr_icon = "mdi:chef-hat"

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data.get(self._sensor_type, {})
        _LOGGER.debug("Sensor state data: %s", data)
        return data.get("title", "unknown")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = self.coordinator.data.get(self._sensor_type, {})
        _LOGGER.debug("Sensor state attributes: %s", data)
        return {
            "url": data.get("url", ""),
            "image_url": data.get("image_url", ""),
            "totalTime": data.get("totalTime", ""),
            "ingredients": data.get("ingredients", ""),
            "calories": data.get("calories", ""),
            "difficulty": data.get("difficulty", ""),
            "ingredients": data.get("ingredients", []),
        }