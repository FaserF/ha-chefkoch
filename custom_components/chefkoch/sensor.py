"""chefkoch sensor platform."""
from datetime import timedelta, datetime
import logging
from typing import Any, Dict, Optional

from python_chefkoch import chefkoch
import async_timeout

from homeassistant import core
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    HomeAssistantType,
    DiscoveryInfoType,
)
import voluptuous as vol

from .const import (
    ATTRIBUTION,
    ATTR_RECIPE,
    ATTR_RECIPES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=2)

async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities: AddEntitiesCallback
):
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Sensor async_setup_entry")
    if entry.options:
        config.update(entry.options)
    async_add_entities(
        [
            ChefkochSensorDaily(config, hass),
            ChefkochSensorRandom(config, hass),
            ChefkochSensorDailyBacke(config, hass),
        ],
        update_before_add=True
    )

class ChefkochSensorBase(SensorEntity):
    def __init__(self, name: str, fetch_function: Callable):
        self._name = name
        self._state = None
        self._available = True
        self.updated = datetime.now()
        self.attrs: Dict[str, Any] = {}
        self._fetch_function = fetch_function

    @property
    def should_poll(self) -> bool:
        """Return True if the sensor should be polled for updates."""
        return True

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon for the frontend."""
        return "mdi:chef-hat"

    @property
    def state(self) -> Optional[str]:
        return self._state if self._state is not None else "Unknown"

    @property
    def native_value(self) -> Optional[str]:
        """Return the chefkoch data."""
        return self._state

    async def async_update(self):
        try:
            with async_timeout.timeout(30):
                data = await self.hass.async_add_executor_job(self._fetch_function)
                recipes_count = len(data)

                if recipes_count > 0:
                    recipes = [{ATTR_RECIPE: recipe} for recipe in data]

                    self.attrs[ATTR_RECIPES] = recipes
                    self.attrs[ATTR_ATTRIBUTION] = f"Last updated {datetime.now()} \n{ATTRIBUTION}"
                    self._state = recipes_count
                    self._available = True
                else:
                    _LOGGER.error(f"Data from chefkoch for '{self._name}' was empty, retrying at next sync run. Maybe also check your internet connection?")
                    self._available = False

        except Exception as e:
            self._available = False
            _LOGGER.exception(f"Cannot retrieve data for '{self._name}': {e}")

class ChefkochSensorDaily(ChefkochSensorBase):
    def __init__(self, config, hass: HomeAssistantType):
        super().__init__("Chefkoch daily recommendations", fetch_chefkoch_daily_recipes)

class ChefkochSensorRandom(ChefkochSensorBase):
    def __init__(self, config, hass: HomeAssistantType):
        super().__init__("Chefkoch random recommendations", fetch_chefkoch_random_recipes)

class ChefkochSensorDailyBacke(ChefkochSensorBase):
    def __init__(self, config, hass: HomeAssistantType):
        super().__init__("Chefkoch daily backe recommendations", fetch_chefkoch_daily_recipes_backe)

def fetch_chefkoch_daily_recipes():
    _LOGGER.debug("Fetching update from chefkoch python module for daily recommendations")
    data = chefkoch.get_daily_recommendations(category="koche")
    _LOGGER.debug(f"Fetched daily data: {data}")
    return data

def fetch_chefkoch_daily_recipes_backe():
    _LOGGER.debug("Fetching update from chefkoch python module for daily backe recommendations")
    data = chefkoch.get_daily_recommendations(category="backe")
    _LOGGER.debug(f"Fetched daily backe data: {data}")
    return data

def fetch_chefkoch_random_recipes():
    _LOGGER.debug("Fetching update from chefkoch python module for random recommendations")
    data = chefkoch.get_random_recipe()
    _LOGGER.debug(f"Fetched random data: {data}")
    return data
