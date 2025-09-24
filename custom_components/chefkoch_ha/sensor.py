"""Sensor platform for Chefkoch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Set up Chefkoch sensor entities for a config entry.
    
    Reads the integration coordinator from hass.data and the configured sensor list from
    entry.options["sensors"]. If no sensors are configured, logs a warning and does nothing.
    Otherwise instantiates a ChefkochSensor for each sensor configuration and registers them
    via async_add_entities.
    """
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
        """
        Initialize the Chefkoch sensor entity.
        
        Stores the provided sensor configuration and coordinator, derives the entity display name (prefixing with "Chefkoch " when the configured name does not already start with it), sets the sensor icon to "mdi:chef-hat", and sets a stable unique_id of the form "chefkoch_{id}".
        
        Parameters:
            sensor_config (dict): Sensor configuration containing at least:
                - "name": display name for the sensor
                - "id": unique identifier used to build the entity's unique_id
        """
        super().__init__(coordinator)
        self.sensor_config = sensor_config

        name = sensor_config["name"]

        if not name.lower().startswith("chefkoch"):
            self._attr_name = f"Chefkoch {name}"
        else:
            self._attr_name = name

        self._attr_icon = "mdi:chef-hat"
        self._attr_unique_id = f"chefkoch_{sensor_config['id']}"

    @property
    def sensor_id(self):
        """Return the unique id of the sensor config."""
        return self.sensor_config["id"]

    @property
    def native_value(self):
        """
        Return the sensor's current native value.
        
        Looks up this sensor's data from the coordinator by sensor_id and returns the `title` field. If no data or `title` is present, returns "unknown".
        """
        data = self.coordinator.data.get(self.sensor_id, {})
        return data.get("title", "unknown")

    @property
    def extra_state_attributes(self):
        """
        Return additional state attributes for the sensor.
        
        Builds a dictionary from the coordinator's data for this sensor (keyed by sensor_id),
        including only entries whose values are not None, not the empty string, and not an
        empty list. The keys "title" and "status" are removed from the resulting attributes.
        
        Returns:
            dict: Filtered attribute mapping to attach to the sensor's state.
        """
        data = self.coordinator.data.get(self.sensor_id, {})

        attributes = {
            key: value
            for key, value in data.items()
            if value is not None and value != '' and value != []
        }
        attributes.pop("title", None)
        attributes.pop("status", None)

        return attributes