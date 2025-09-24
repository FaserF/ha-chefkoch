"""Config flow for Chefkoch integration."""
import voluptuous as vol
import uuid
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN

class ChefkochConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chefkoch."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Chefkoch", data={}, options={"sensors": []})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ChefkochOptionsFlowHandler(config_entry)


class ChefkochOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Chefkoch."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.current_sensors = self.config_entry.options.get("sensors", [])
        self.sensor_to_edit_id = None

    async def async_step_init(self, user_input=None):
        """Manage the options menu."""
        menu_options = ["add_sensor"]
        if self.current_sensors:
             menu_options.extend(["edit_sensor", "remove_sensor"])

        default_ids = {"random", "daily", "vegan"}
        current_ids = {s.get("id") for s in self.current_sensors}
        if not default_ids.issubset(current_ids):
            menu_options.insert(0, "add_defaults")

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_add_defaults(self, user_input=None):
        """Handle adding default sensors."""
        default_sensors = [
            {"type": "random", "id": "random", "name": "Chefkoch Random Recipe"},
            {"type": "daily", "id": "daily", "name": "Chefkoch Daily Recipe"},
            {"type": "vegan", "id": "vegan", "name": "Chefkoch Vegan Recipe"}
        ]

        current_ids = {s.get("id") for s in self.current_sensors}
        new_sensors = [s for s in default_sensors if s["id"] not in current_ids]

        updated_sensors = self.current_sensors + new_sensors

        return self.async_create_entry(title="", data={"sensors": updated_sensors})

    async def async_step_add_sensor(self, user_input=None):
        """Handle the step to add a new search sensor."""
        if user_input is not None:
            new_sensor = {
                "id": str(uuid.uuid4()),
                "type": "search",
                "name": user_input["name"],
                "search_query": user_input.get("search_query", ""),
                "category": user_input.get("category", ""),
                "difficulty": user_input.get("difficulty", ""),
            }
            updated_sensors = self.current_sensors + [new_sensor]
            return self.async_create_entry(title="", data={"sensors": updated_sensors})

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Optional("search_query"): str,
                vol.Optional("category"): str,
                vol.Optional("difficulty"): vol.In(['', 'Einfach', 'Normal', 'Schwer']),
            }),
            last_step=True
        )

    async def async_step_edit_sensor(self, user_input=None):
        """Show a list of sensors to edit."""
        if user_input is not None:
            self.sensor_to_edit_id = user_input["sensor_id"]
            return await self.async_step_edit_sensor_form()

        sensor_list = {s["id"]: s["name"] for s in self.current_sensors}
        return self.async_show_form(
            step_id="edit_sensor",
            data_schema=vol.Schema({vol.Required("sensor_id"): vol.In(sensor_list)})
        )

    async def async_step_edit_sensor_form(self, user_input=None):
        """Show the form to edit a sensor's details."""
        sensor_to_edit = next((s for s in self.current_sensors if s["id"] == self.sensor_to_edit_id), None)
        if not sensor_to_edit:
             return self.async_abort(reason="no_sensors") # Should not happen

        if user_input is not None:
            sensor_to_edit.update({
                "name": user_input["name"],
                "search_query": user_input.get("search_query", ""),
                "category": user_input.get("category", ""),
                "difficulty": user_input.get("difficulty", ""),
            })
            return self.async_create_entry(title="", data={"sensors": self.current_sensors})

        schema = vol.Schema({
            vol.Required("name", default=sensor_to_edit.get("name")): str,
            vol.Optional("search_query", default=sensor_to_edit.get("search_query")): str,
            vol.Optional("category", default=sensor_to_edit.get("category")): str,
            vol.Optional("difficulty", default=sensor_to_edit.get("difficulty")): vol.In(['', 'Einfach', 'Normal', 'Schwer']),
        })

        return self.async_show_form(
            step_id="edit_sensor_form",
            data_schema=schema,
            last_step=True
        )

    async def async_step_remove_sensor(self, user_input=None):
        """Handle sensor removal."""
        if user_input is not None:
            sensors_to_remove = user_input["sensors_to_remove"]
            updated_sensors = [s for s in self.current_sensors if s["id"] not in sensors_to_remove]
            return self.async_create_entry(title="", data={"sensors": updated_sensors})

        sensor_list = {s["id"]: s["name"] for s in self.current_sensors}
        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema({
                vol.Required("sensors_to_remove"): cv.multi_select(sensor_list)
            }),
            last_step=True
        )