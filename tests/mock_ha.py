import sys
from unittest.mock import MagicMock


def setup_mocks():
    """Setup Home Assistant mocks."""

    # Define base classes
    class MockEntity:
        def __init__(self, *args, **kwargs):
            self._attr_name = None
            self._attr_unique_id = None
            self._attr_icon = None
            self._attr_extra_state_attributes = {}
            self.hass = MagicMock()
            self.entity_id = "sensor.test"
            self.coordinator = None
            if args:
                self.coordinator = args[0]

        @property
        def name(self):
            return self._attr_name or "unknown"

        @property
        def unique_id(self):
            return self._attr_unique_id

        @property
        def icon(self):
            return self._attr_icon

        @property
        def extra_state_attributes(self):
            return self._attr_extra_state_attributes or {}

        @property
        def device_info(self):
            return {"name": "Recipes", "manufacturer": "Chefkoch", "model": "Recipes"}

    class MockCoordinatorEntity(MockEntity):
        def __init__(self, coordinator, context=None):
            super().__init__()
            self.coordinator = coordinator

    class MockOptionsFlow:
        def __init__(self, config_entry=None):
            self.config_entry = config_entry
            self.hass = MagicMock()

        async def async_show_menu(self, **kwargs):
            return "menu"

        async def async_show_form(self, **kwargs):
            return "form"

        def async_create_entry(self, **kwargs):
            return "create"

        def async_abort(self, **kwargs):
            return "abort"

    # Mock modules
    m = MagicMock()
    sys.modules["homeassistant"] = m
    sys.modules["homeassistant.const"] = MagicMock()
    sys.modules["homeassistant.const"].CONF_NAME = "name"
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.callback"] = lambda x: x
    sys.modules["homeassistant.config_entries"] = MagicMock()
    sys.modules["homeassistant.config_entries"].OptionsFlow = MockOptionsFlow
    sys.modules["homeassistant.helpers"] = MagicMock()
    sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
    sys.modules[
        "homeassistant.helpers.update_coordinator"
    ].CoordinatorEntity = MockCoordinatorEntity
    sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
    sys.modules["homeassistant.helpers.config_validation"] = MagicMock()
    sys.modules["homeassistant.components"] = MagicMock()
    sys.modules["homeassistant.components.sensor"] = MagicMock()
    sys.modules["homeassistant.components.sensor"].SensorEntity = MockEntity
    sys.modules["homeassistant.components.diagnostics"] = MagicMock()

    # Voluptuous
    import voluptuous as vol

    class MockSchema:
        def __init__(self, schema):
            self.schema = schema

        def __call__(self, data):
            return data

        def extend(self, *args, **kwargs):
            return self

    vol.Schema = MockSchema
    vol.Optional = lambda x, default=None: x
    vol.Required = lambda x, default=None: x
    vol.All = lambda *args: lambda x: x
    vol.Coerce = lambda x: lambda y: y
    vol.Range = lambda min=None, max=None: lambda x: x
    vol.In = lambda x: lambda y: y
    sys.modules["voluptuous"] = vol


setup_mocks()
