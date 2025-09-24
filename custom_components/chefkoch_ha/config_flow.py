import voluptuous as vol
import uuid
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN, DEFAULT_SENSORS

def get_search_schema(sensor_data=None):
    """Return the schema for the search sensor form."""
    sensor_data = sensor_data or {}
    return vol.Schema({
        vol.Required("name", default=sensor_data.get("name")): str,
        vol.Required("search_query", default=sensor_data.get("search_query", "")): str,
        vol.Optional("properties", default=sensor_data.get("properties", "")): str,
        vol.Optional("health", default=sensor_data.get("health", "")): str,
        vol.Optional("categories", default=sensor_data.get("categories", "")): str,
        vol.Optional("countries", default=sensor_data.get("countries", "")): str,
        vol.Optional("meal_type", default=sensor_data.get("meal_type", "")): str,
        #vol.Optional("prep_times", default=sensor_data.get("prep_times", "")): int,
        #vol.Optional("ratings", default=sensor_data.get("ratings")): vol.In(['1', '2', '3', '4', '5']),
    })

class ChefkochConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Chefkoch", data={}, options={"sensors": DEFAULT_SENSORS})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChefkochOptionsFlowHandler(config_entry)

class ChefkochOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        self.current_sensors = self.config_entry.options.get("sensors", [])
        self.sensor_to_edit_id = None

    async def async_step_init(self, user_input=None):
        menu_options = ["add_sensor"]
        custom_sensors = [s for s in self.current_sensors if s.get("type") == "search"]
        if custom_sensors:
            menu_options.extend(["edit_sensor", "remove_sensor"])
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_add_sensor(self, user_input=None):
        if user_input is not None:
            new_sensor = {"id": str(uuid.uuid4()), "type": "search", **user_input}
            updated_sensors = self.current_sensors + [new_sensor]
            return self.async_create_entry(title="", data={"sensors": updated_sensors})
        return self.async_show_form(step_id="add_sensor", data_schema=get_search_schema(), last_step=True)

    async def async_step_edit_sensor(self, user_input=None):
        custom_sensors = {s["id"]: s["name"] for s in self.current_sensors if s.get("type") == "search"}
        if not custom_sensors:
            return self.async_abort(reason="no_custom_sensors")
        if user_input is not None:
            self.sensor_to_edit_id = user_input["sensor_id"]
            return await self.async_step_edit_sensor_form()
        return self.async_show_form(step_id="edit_sensor", data_schema=vol.Schema({vol.Required("sensor_id"): vol.In(custom_sensors)}))

    async def async_step_edit_sensor_form(self, user_input=None):
        sensor_to_edit = next((s for s in self.current_sensors if s["id"] == self.sensor_to_edit_id), None)
        if not sensor_to_edit:
            return self.async_abort(reason="no_sensors")
        if user_input is not None:
            sensor_to_edit.update(user_input)
            return self.async_create_entry(title="", data={"sensors": self.current_sensors})
        return self.async_show_form(step_id="edit_sensor_form", data_schema=get_search_schema(sensor_to_edit), last_step=True)

    async def async_step_remove_sensor(self, user_input=None):
        custom_sensors = {s["id"]: s["name"] for s in self.current_sensors if s.get("type") == "search"}
        if not custom_sensors:
            return self.async_abort(reason="no_custom_sensors")
        if user_input is not None:
            sensors_to_remove = user_input["sensors_to_remove"]
            updated_sensors = [s for s in self.current_sensors if s["id"] not in sensors_to_remove]
            return self.async_create_entry(title="", data={"sensors": updated_sensors})
        return self.async_show_form(step_id="remove_sensor", data_schema=vol.Schema({vol.Required("sensors_to_remove"): cv.multi_select(custom_sensors)}), last_step=True)