"""deutschebahn sensor platform."""
from datetime import timedelta, datetime
import logging
from typing import Any, Callable, Dict, Optional

from python_chefkoch import chefkoch
import async_timeout

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    HomeAssistantType,
    DiscoveryInfoType,
)
import homeassistant.util.dt as dt_util
import voluptuous as vol

from .const import (
    ATTRIBUTION,
    ATTR_DATA,

    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=2)

async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
):
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Sensor async_setup_entry")
    if entry.options:
        config.update(entry.options)
    sensors = ChefkochSensor(config, hass)
    async_add_entities(sensors, update_before_add=True)
    async_add_entities(
        [
            ChefkochSensor(config, hass)
        ],
        update_before_add=True
    )

class ChefkochSensor(SensorEntity):
    """Implementation of a Deutsche Bahn sensor."""

    def __init__(self, config, hass: HomeAssistantType):
        super().__init__()
        self._name = "Chefkoch daily recommendations"
        self._state = None
        self._available = True
        self.hass = hass
        self.updated = datetime.now()
        self.chefkoch = chefkoch.chefkoch()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return "mdi:chef-hat"

    @property
    def state(self) -> Optional[str]:
        if self._state is not None:
            return self._state
        else:
            return "Unknown"

    @property
    def native_value(self):
        """Return the chefkoch data."""
        return self._state

    async def async_update(self):
        try:
            with async_timeout.timeout(30):
                hass = self.hass
                """Pull data from the chefkoch.de web page."""
                data = await hass.async_add_executor_job(
                        fetch_chefkoch_data, hass, self
                    )

                recipes = []
                for recipe in data['categories']:
                    _LOGGER.debug(f"Processing recipe: '{recipe}")
                    recipes.append(
                        {
                            ATTR_RECIPE: item['title'],
                        }
                    )

                # Get the amount of offers
                recipes_count = len(recipes)

                self.attrs[ATTR_RECIPES] = recipes
                self.attrs[ATTR_ATTRIBUTION] = f"last updated {datetime.now()} \n{ATTRIBUTION}"
                self._state = recipes_count
                self._available = True

        except:
            self._available = False
            _LOGGER.exception(f"Cannot retrieve data for '{self._name}'")

def fetch_chefkoch_data(hass, self):
    _LOGGER.debug(f"Fetching update from chefkoch python module for '{self._name}'")
    data = chefkoch.get_daily_recommendations

    _LOGGER.debug(f"Fetched data: {data}")
    return data
