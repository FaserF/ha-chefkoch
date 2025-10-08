import voluptuous as vol
import uuid
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN, DEFAULT_SENSORS

# Define the available filter options for the user
PROPERTIES_OPTIONS = ["Einfach", "Schnell", "Basisrezepte", "Preiswert"]
HEALTH_OPTIONS = ["Vegetarisch", "Vegan", "Kalorienarm", "Low Carb", "Ketogen", "Paleo", "Fettarm", "Trennkost", "Vollwert"]
CATEGORIES_OPTIONS = [
    "Auflauf", "Pizza", "Reis- oder Nudelsalat", "Salat", "Salatdressing", "Tarte", "Fingerfood", "Dips", "Saucen",
    "Suppe", "Klöße", "Brot und Brötchen", "Brotspeise", "Aufstrich", "Süßspeise", "Eis", "Kuchen", "Kekse",
    "Torte", "Confiserie", "Getränke", "Shake", "Gewürzmischung", "Pasten", "Studentenküche"
]
COUNTRIES_OPTIONS = [
    "Deutschland", "Italien", "Spanien", "Portugal", "Frankreich", "England", "Osteuropa", "Skandinavien",
    "Griechenland", "Türkei", "Russland", "Naher Osten", "Asien", "Indien", "Japan", "Amerika", "Mexiko",
    "Karibik", "Lateinamerika", "Afrika", "Marokko", "Ägypten", "Australien"
]
MEAL_TYPE_OPTIONS = ["Hauptspeise", "Vorspeise", "Beilage", "Dessert", "Snack", "Frühstück"]
PREP_TIMES_OPTIONS = ["Alle", "15", "30", "60", "120"]
RATINGS_OPTIONS = ["Alle", "2", "3", "4", "Top"]
SORT_OPTIONS = ["Empfehlung", "Bewertung", "Neuheiten"]

def get_search_schema(sensor_data=None):
    """Return the schema for the search sensor form."""
    sensor_data = sensor_data or {}

    # Helper to convert comma-separated string from storage to a list for the multi-select default value
    def str_to_list(value):
        if not value or not isinstance(value, str):
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

    return vol.Schema({
        vol.Required("name", default=sensor_data.get("name")): str,
        vol.Optional("search_query", default=sensor_data.get("search_query", "")): str,
        vol.Optional("properties", default=str_to_list(sensor_data.get("properties"))): cv.multi_select(PROPERTIES_OPTIONS),
        vol.Optional("health", default=str_to_list(sensor_data.get("health"))): cv.multi_select(HEALTH_OPTIONS),
        vol.Optional("categories", default=str_to_list(sensor_data.get("categories"))): cv.multi_select(CATEGORIES_OPTIONS),
        vol.Optional("countries", default=str_to_list(sensor_data.get("countries"))): cv.multi_select(COUNTRIES_OPTIONS),
        vol.Optional("meal_type", default=str_to_list(sensor_data.get("meal_type"))): cv.multi_select(MEAL_TYPE_OPTIONS),
        vol.Optional("prep_times", default=sensor_data.get("prep_times", "Alle")): vol.In(PREP_TIMES_OPTIONS),
        vol.Optional("ratings", default=sensor_data.get("ratings", "Alle")): vol.In(RATINGS_OPTIONS),
        vol.Optional("sort", default=sensor_data.get("sort", "Empfehlung")): vol.In(SORT_OPTIONS),
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

    def _process_user_input(self, user_input):
        """Process user input to convert lists to strings and handle special values for storage."""
        processed_input = user_input.copy()

        # Convert lists from multi-select back to comma-separated strings
        for key in ["properties", "health", "categories", "countries", "meal_type"]:
            if key in processed_input and isinstance(processed_input[key], list):
                processed_input[key] = ",".join(processed_input[key])

        # Handle 'Alle' for prep_times
        selected_prep_time = processed_input.get("prep_times")
        if selected_prep_time == "Alle":
            processed_input["prep_times"] = ""
        else:
            processed_input["prep_times"] = int(selected_prep_time)

        # Handle 'Alle' and 'Top' for ratings
        ratings_map = {"2": "2", "3": "3", "4": "4", "Top": "5"}
        selected_rating = processed_input.get("ratings")
        if selected_rating in ratings_map:
            processed_input["ratings"] = ratings_map[selected_rating]
        else:  # "Alle"
            processed_input["ratings"] = ""

        return processed_input

    async def async_step_init(self, user_input=None):
        menu_options = ["add_sensor"]
        custom_sensors = [s for s in self.current_sensors if s.get("type") == "search"]
        if custom_sensors:
            menu_options.extend(["edit_sensor", "remove_sensor"])
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_add_sensor(self, user_input=None):
        if user_input is not None:
            processed_input = self._process_user_input(user_input)
            new_sensor = {"id": str(uuid.uuid4()), "type": "search", **processed_input}
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
            processed_input = self._process_user_input(user_input)
            sensor_to_edit.update(processed_input)
            return self.async_create_entry(title="", data={"sensors": self.current_sensors})

        # Prepare the data to be displayed in the form, mapping stored values back to form options
        form_data = sensor_to_edit.copy()

        stored_prep_time = str(form_data.get("prep_times", ""))
        if stored_prep_time not in PREP_TIMES_OPTIONS:
            form_data["prep_times"] = "Alle"

        ratings_map_inv = {"2": "2", "3": "3", "4": "4", "5": "Top"}
        stored_rating = str(form_data.get("ratings", ""))
        if stored_rating in ratings_map_inv:
            form_data["ratings"] = ratings_map_inv[stored_rating]
        else:
            form_data["ratings"] = "Alle"

        return self.async_show_form(
            step_id="edit_sensor_form",
            data_schema=get_search_schema(form_data),
            last_step=True
        )

    async def async_step_remove_sensor(self, user_input=None):
        custom_sensors = {s["id"]: s["name"] for s in self.current_sensors if s.get("type") == "search"}
        if not custom_sensors:
            return self.async_abort(reason="no_custom_sensors")
        if user_input is not None:
            sensors_to_remove = user_input["sensors_to_remove"]
            updated_sensors = [s for s in self.current_sensors if s["id"] not in sensors_to_remove]
            return self.async_create_entry(title="", data={"sensors": updated_sensors})
        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema({vol.Required("sensors_to_remove"): cv.multi_select(custom_sensors)}),
            last_step=True
        )