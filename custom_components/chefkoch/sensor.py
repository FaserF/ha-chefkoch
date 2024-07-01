"""Sensor platform for Chefkoch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Chefkoch sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ChefkochSensor(coordinator)])


class ChefkochSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Chefkoch sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Chefkoch Sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get("some_key")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "attribute_1": self.coordinator.data.get("attribute_1"),
            "attribute_2": self.coordinator.data.get("attribute_2"),
        }