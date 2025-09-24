"""Sensor platform for Chefkoch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Chefkoch sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    sensors = entry.options.get("sensors", [])
    if not sensors:
        _LOGGER.warning("No sensors configured for Chefkoch integration.")
        return

    entities = [ChefkochSensor(coordinator, sensor_config) for sensor_config in sensors]
    async_add_entities(entities)


class ChefkochSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Chefkoch sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_config: dict):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sensor_config = sensor_config

        self._attr_name = sensor_config["name"]
        self._attr_icon = "mdi:chef-hat"
        self._attr_unique_id = f"chefkoch_{sensor_config['id']}"

    @property
    def sensor_id(self):
        """Return the unique id of the sensor config."""
        return self.sensor_config["id"]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data.get(self.sensor_id, {})
        return data.get("title", "unknown")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = self.coordinator.data.get(self.sensor_id, {})

        # Dynamically add all attributes that are not None, empty strings or empty lists
        attributes = {
            key: value
            for key, value in data.items()
            if value is not None and value != '' and value != []
        }
        # We don't need title and status as attributes, they are state or for internal use
        attributes.pop("title", None)
        attributes.pop("status", None)

        return attributes