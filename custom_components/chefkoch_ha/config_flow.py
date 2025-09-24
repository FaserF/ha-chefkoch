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
        """
        Handle the initial user step of the config flow.
        
        If an existing config entry for this integration is present, aborts the flow with reason
        "single_instance_allowed". Otherwise creates and returns a new config entry titled
        "Chefkoch" with empty data and default options containing an empty "sensors" list.
        
        Parameters:
            user_input (dict | None): Optional data provided by the user (ignored by this step).
        
        Returns:
            config_entries.ConfigEntry | FlowResult: The created config entry on success, or an abort flow result.
        """
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
        """
        Initialize the options flow handler for a given config entry.
        
        Populates the handler's state from the provided config_entry: copies the existing
        "sensors" list into self.current_sensors and initializes self.sensor_to_edit_id to None.
        
        Parameters:
            config_entry (config_entries.ConfigEntry): The config entry whose options are used to
                initialize the flow.
        """
        self.config_entry = config_entry
        self.current_sensors = self.config_entry.options.get("sensors", [])
        self.sensor_to_edit_id = None

    async def async_step_init(self, user_input=None):
        """
        Build and show the options menu for sensor management.
        
        The menu always includes "add_sensor". If any sensors already exist, "edit_sensor"
        and "remove_sensor" are added. If any of the default sensor IDs ("random",
        "daily", "vegan") are not present in the current sensors, "add_defaults" is
        inserted at the front of the menu.
        
        Returns:
            A Home Assistant flow result that displays the named menu step ("init")
            with the computed menu options.
        """
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
        """
        Add predefined default sensors that are missing and create an options entry.
        
        This adds the three built-in sensors with IDs "random", "daily", and "vegan" only if they are not already present in self.current_sensors. Existing sensors are preserved; the function returns a new config entry whose data contains the updated "sensors" list.
        """
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
        """
        Handle the "add sensor" options step.
        
        If called with `user_input` (a dict from the submitted form), creates a new search sensor with a generated UUID and the submitted fields, appends it to the current sensors list, and returns a new config entry containing {"sensors": updated_sensors}.
        
        If called without `user_input`, returns a form asking for:
        - name (required)
        - search_query (optional)
        - category (optional)
        - difficulty (optional; one of '', 'Einfach', 'Normal', 'Schwer')
        
        Parameters:
            user_input (dict | None): Submitted form values when present.
        
        Returns:
            FlowResult: either a created config entry (on submit) or a form to display (when no input).
        """
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
        """
        Display a form to edit an existing sensor's properties or apply submitted changes.
        
        If no sensor matches the previously selected sensor ID, the flow is aborted with reason "no_sensors".
        - When called with `user_input` (form submitted): updates the target sensor in `self.current_sensors` with the submitted fields
          (`name`, optional `search_query`, `category`, and `difficulty`) and finishes by creating a new entry with the updated sensors list.
        - When called without `user_input`: returns a form populated with the sensor's current values. The form fields are:
          - name (required)
          - search_query (optional)
          - category (optional)
          - difficulty (optional; allowed values: '', 'Einfach', 'Normal', 'Schwer')
        
        The created config entry has an empty title and its data contains {"sensors": self.current_sensors}.
        """
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
        """
        Remove one or more configured sensors from the options flow.
        
        If called with user input, expects a "sensors_to_remove" iterable containing sensor IDs;
        it filters those IDs out of the current sensors and finishes by creating an updated entry
        with the remaining sensors.
        
        If called without input, presents a form (step_id "remove_sensor") with a multi-select of
        currently configured sensors to choose which to remove.
        
        Returns:
            A config flow entry when removal is submitted, or a form result when prompting the user.
        """
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