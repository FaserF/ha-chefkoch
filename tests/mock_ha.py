import sys
from unittest.mock import AsyncMock, MagicMock


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
        def __init__(self, *args, **kwargs):
            self.hass = MagicMock()
            self.context = {}
            self.async_show_form = AsyncMock(return_value="form")
            self.async_create_entry = AsyncMock(return_value="create")
            self.async_abort = AsyncMock(return_value="abort")
            self.async_show_menu = AsyncMock(return_value="menu")

        def _async_current_entries(self, *args, **kwargs):
            return []

    # Mock modules
    m = MagicMock()
    sys.modules["homeassistant"] = m
    sys.modules["homeassistant.const"] = MagicMock()
    sys.modules["homeassistant.const"].CONF_NAME = "name"
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.callback"] = lambda x: x

    conf_entries = MagicMock()
    conf_entries.ConfigFlow = MockDataEntryFlow
    conf_entries.OptionsFlow = MockDataEntryFlow
    sys.modules["homeassistant.config_entries"] = conf_entries

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
    vol.Optional = lambda x, default=None: x  # type: ignore[assignment]
    vol.Required = lambda x, default=None: x  # type: ignore[assignment]
    vol.All = lambda *args: lambda x: x  # type: ignore[assignment]
    vol.Coerce = lambda x: lambda y: y  # type: ignore[assignment]
    vol.Range = lambda min=None, max=None: lambda x: x  # type: ignore[assignment]
    vol.In = lambda x: lambda y: y  # type: ignore[assignment]
    sys.modules["voluptuous"] = vol

    # Mock get_chefkoch
    mock_recipe = MagicMock()
    mock_recipe.id = "test_id"
    mock_recipe.name = "Test Recipe"
    mock_recipe.image = "http://image"
    mock_recipe.category = "Test"
    mock_recipe.ingredients = ["Salt"]
    mock_recipe.prepTime = "0:10:00"
    mock_recipe.totalTime = "0:30:00"
    mock_recipe.cookTime = "0:20:00"
    mock_recipe.data_dump.return_value = {
        "aggregateRating": {"ratingValue": 4.5, "ratingCount": 10, "reviewCount": 5},
        "author": {"name": "Test Author"},
        "nutrition": {"calories": "500 kcal"},
        "keywords": "Test",
        "datePublished": "2024-01-01",
        "recipeYield": "4 Portionen",
        "publisher": {"name": "Chefkoch"},
    }

    mock_search = MagicMock()
    mock_search.recipes.return_value = [mock_recipe]
    mock_search.recipeOfTheDay.return_value = mock_recipe

    get_chefkoch_mock = MagicMock()
    get_chefkoch_mock.Recipe = MagicMock(return_value=mock_recipe)
    get_chefkoch_mock.Search = MagicMock(return_value=mock_search)
    sys.modules["get_chefkoch"] = get_chefkoch_mock


setup_mocks()
