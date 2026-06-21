import sys
import types
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

    class MockDataEntryFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

        def __init__(self, *args, **kwargs):
            self.hass = MagicMock()
            self.context = {}
            self.async_show_form = MagicMock(
                side_effect=lambda step_id=None, data_schema=None, errors=None, description_placeholders=None, last_step=None: {
                    "type": "form",
                    "step_id": step_id,
                    "data_schema": data_schema,
                    "errors": errors,
                    "last_step": last_step,
                }
            )
            self.async_create_entry = MagicMock(
                side_effect=lambda title="", data={}, options=None: {
                    "type": "create_entry",
                    "title": title,
                    "data": data,
                    "options": options,
                }
            )
            self.async_abort = MagicMock(
                side_effect=lambda reason="": {"type": "abort", "reason": reason}
            )
            self.async_show_menu = MagicMock(
                side_effect=lambda step_id=None, menu_options=None: {
                    "type": "menu",
                    "step_id": step_id,
                    "menu_options": menu_options,
                }
            )

        def _async_current_entries(self, *args, **kwargs):
            return []

    # Create homeassistant module structure
    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    ha_const = types.ModuleType("homeassistant.const")
    ha_const.CONF_NAME = "name"
    sys.modules["homeassistant.const"] = ha_const
    ha.const = ha_const

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock
    ha_core.callback = lambda x: x
    sys.modules["homeassistant.core"] = ha_core
    ha.core = ha_core

    ha_config_entries = types.ModuleType("homeassistant.config_entries")
    ha_config_entries.ConfigFlow = MockDataEntryFlow
    ha_config_entries.OptionsFlow = MockDataEntryFlow
    ha_config_entries.ConfigEntry = MagicMock
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    ha.config_entries = ha_config_entries

    # Mock other helpers
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
    vol.Optional = lambda x, default=None: x  # type: ignore[misc]
    vol.Required = lambda x, default=None: x  # type: ignore[misc]
    vol.All = lambda *args: lambda x: x  # type: ignore[misc]
    vol.Coerce = lambda x: lambda y: y  # type: ignore[misc]
    vol.Range = lambda min=None, max=None: lambda x: x  # type: ignore[misc]
    vol.In = lambda x: lambda y: y  # type: ignore[misc]
    sys.modules["voluptuous"] = vol

    # Mock get_chefkoch
    mock_recipe = MagicMock()
    mock_recipe._id = "test_id"
    mock_recipe.name = "Test Recipe"
    mock_recipe._url = "http://recipe/123/"

    mock_search = MagicMock()
    mock_search.recipes.return_value = [mock_recipe]
    mock_search.recipeOfTheDay.return_value = mock_recipe
    mock_search.suggestions.return_value = {"suggestions": ["Test"]}

    get_chefkoch_mock = MagicMock()
    get_chefkoch_mock.Recipe = MagicMock(return_value=mock_recipe)
    get_chefkoch_mock.Search = MagicMock(return_value=mock_search)
    sys.modules["get_chefkoch"] = get_chefkoch_mock


setup_mocks()
