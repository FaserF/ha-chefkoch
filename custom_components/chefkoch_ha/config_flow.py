"""Config & options flow for the Chefkoch integration.

Navigation (options):

* Sensors -> add / edit / remove sensors, choose which default sensors exist
* Default filters -> meal type, diet, time, rating, keywords, ... (global)
* Recipe sources -> primary provider, fallbacks, API keys
* Weather & seasonal specials
* Update interval
"""

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULT_SENSORS, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .engine import DEFAULT_GLOBAL_FILTERS, RECIPE_TYPES
from .filters import (
    DIETS,
    DIFFICULTIES,
    MEAL_TYPES,
    SORT_MODES,
    RecipeFilter,
    parse_list,
)
from .providers import DEFAULT_PROVIDER_ORDER, PROVIDER_LABELS
from .recipe_fetcher import _fetch_api_suggestions

_LOGGER = logging.getLogger(__name__)

# Suggested values for the free-form "categories" filter (matched against the
# recipe's category breadcrumb / cuisine, so any text is allowed as well).
CATEGORY_SUGGESTIONS = [
    "Auflauf",
    "Suppen",
    "Eintopf",
    "Pasta",
    "Salat",
    "Fisch",
    "Gemüse",
    "Fingerfood",
    "Snacks und kleine Gerichte",
    "Deutschland",
    "Italien",
    "Frankreich",
    "Spanien",
    "Griechenland",
    "Türkei",
    "Asien",
    "Indien",
    "Amerika",
    "Mexiko",
    "Afrika",
]

# Keys written by the filter forms (and legacy v3.1 keys that get migrated on save)
FILTER_BASIC_KEYS = [
    "meal_type",
    "diets",
    "max_total_minutes",
    "min_rating",
    "max_difficulty",
    "sort",
]
FILTER_ADVANCED_KEYS = [
    "include_keywords",
    "exclude_keywords",
    "exclude_ingredients",
    "categories",
    "exclude_categories",
    "max_calories",
]
LEGACY_FILTER_KEYS = ["properties", "health", "prep_times", "ratings", "countries"]
SENSOR_FORM_KEYS = ["search_query", "provider", "meal_type"]


def _select(
    options: list[str],
    translation_key: str,
    *,
    multiple: bool = False,
    custom: bool = False,
) -> Any:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=multiple,
            custom_value=custom,
            translation_key=translation_key,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _number(min_: float, max_: float, step: float, unit: str | None = None) -> Any:
    kwargs: dict[str, Any] = {}
    if unit:  # the selector schema rejects unit_of_measurement=None
        kwargs["unit_of_measurement"] = unit
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_,
            max=max_,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
            **kwargs,
        )
    )


def _words() -> Any:
    return selector.TextSelector(selector.TextSelectorConfig(multiple=True))


def _field(
    key: str, value: Any = None, *, required: bool = False, sticky: bool = False
):
    """Schema key. ``sticky`` uses a default; otherwise a clearable suggestion."""
    marker = vol.Required if required else vol.Optional
    if value in (None, "", []):
        return marker(key)
    if sticky or required:
        return marker(key, default=value)
    return marker(key, description={"suggested_value": value})


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop empty values so cleared fields are really removed from storage."""
    return {k: v for k, v in user_input.items() if v not in (None, "", [])}


def _normalized(values: dict[str, Any]) -> dict[str, Any]:
    """Filter values (legacy keys migrated) used to pre-fill forms."""
    return RecipeFilter.from_dict(values).to_dict()


def basic_filter_fields(
    values: dict[str, Any], *, sticky_meal: bool = False, include_meal: bool = True
) -> dict[Any, Any]:
    """Form fields for the commonly used filters."""
    cur = _normalized(values)
    fields: dict[Any, Any] = {}
    if include_meal:
        fields[_field("meal_type", cur.get("meal_type"), sticky=sticky_meal)] = _select(
            MEAL_TYPES, "meal_type"
        )
    fields[_field("diets", cur.get("diets"))] = _select(DIETS, "diet", multiple=True)
    fields[_field("max_total_minutes", cur.get("max_total_minutes"))] = _number(
        5, 600, 5, "min"
    )
    fields[_field("min_rating", cur.get("min_rating"))] = _number(1, 5, 0.5)
    fields[_field("max_difficulty", cur.get("max_difficulty"))] = _select(
        DIFFICULTIES, "difficulty"
    )
    fields[_field("sort", cur.get("sort"))] = _select(SORT_MODES, "sort")
    return fields


def advanced_filter_fields(values: dict[str, Any]) -> dict[Any, Any]:
    """Form fields for keyword / ingredient / category filters."""
    cur = _normalized(values)
    return {
        _field("include_keywords", cur.get("include_keywords")): _words(),
        _field("exclude_keywords", cur.get("exclude_keywords")): _words(),
        _field("exclude_ingredients", cur.get("exclude_ingredients")): _words(),
        _field("categories", cur.get("categories")): _select(
            CATEGORY_SUGGESTIONS, "category", multiple=True, custom=True
        ),
        _field("exclude_categories", cur.get("exclude_categories")): _select(
            CATEGORY_SUGGESTIONS, "category", multiple=True, custom=True
        ),
        _field("max_calories", cur.get("max_calories")): _number(50, 3000, 50, "kcal"),
    }


class ChefkochConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            selected = user_input.get("default_sensors")
            sensors = (
                [s for s in DEFAULT_SENSORS if s["id"] in selected]
                if selected is not None
                else list(DEFAULT_SENSORS)
            )
            options: dict[str, Any] = {
                "sensors": sensors,
                "update_interval": user_input.get(
                    "update_interval", DEFAULT_UPDATE_INTERVAL
                ),
                "filters": {
                    "meal_type": user_input.get(
                        "meal_type", DEFAULT_GLOBAL_FILTERS["meal_type"]
                    )
                },
            }
            return self.async_create_entry(title="Chefkoch", data={}, options=options)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "update_interval", default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "meal_type", default=DEFAULT_GLOBAL_FILTERS["meal_type"]
                ): _select(MEAL_TYPES, "meal_type"),
                vol.Optional(
                    "default_sensors", default=[s["id"] for s in DEFAULT_SENSORS]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": s["id"], "label": s["name"]}
                            for s in DEFAULT_SENSORS
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChefkochOptionsFlowHandler(config_entry)


class ChefkochOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry
        self.current_sensors: list[dict[str, Any]] = [
            dict(s) for s in config_entry.options.get("sensors", [])
        ]
        self.sensor_to_edit_id: str | None = None
        self.data = dict(config_entry.options)
        self.search_query = ""
        self.suggestions: list[str] = []
        self._draft: dict[str, Any] = {}
        self._editing = False
        self._filters_draft: dict[str, Any] = {}

    # ------------------------------------------------------------------ menus
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "sensors",
                "filters",
                "providers",
                "configure_weather",
                "update_interval",
            ],
        )

    async def async_step_sensors(self, user_input=None):
        menu_options = ["add_sensor", "default_sensors"]
        if self.current_sensors:
            menu_options.extend(["edit_sensor", "remove_sensor"])
        return self.async_show_menu(step_id="sensors", menu_options=menu_options)

    def _save(self):
        self.data["sensors"] = self.current_sensors
        return self.async_create_entry(title="", data=self.data)

    # -------------------------------------------------------- default sensors
    async def async_step_default_sensors(self, user_input=None):
        """Choose which of the built-in sensors should exist."""
        default_ids = [s["id"] for s in DEFAULT_SENSORS]
        present = [s["id"] for s in self.current_sensors if s["id"] in default_ids]
        if user_input is not None:
            wanted = set(user_input.get("default_sensors", []))
            by_id = {s["id"]: s for s in self.current_sensors}
            kept_custom = [
                s for s in self.current_sensors if s["id"] not in default_ids
            ]
            defaults = [
                by_id.get(d["id"], dict(d))
                for d in DEFAULT_SENSORS
                if d["id"] in wanted
            ]
            self.current_sensors = defaults + kept_custom
            return self._save()

        return self.async_show_form(
            step_id="default_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional("default_sensors", default=present): (
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    {"value": s["id"], "label": s["name"]}
                                    for s in DEFAULT_SENSORS
                                ],
                                multiple=True,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        )
                    )
                }
            ),
            last_step=True,
        )

    # ------------------------------------------------------- global settings
    async def async_step_update_interval(self, user_input=None):
        """Handle update interval setup."""
        if user_input is not None:
            self.data["update_interval"] = user_input["update_interval"]
            return self.async_create_entry(title="", data=self.data)

        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "update_interval",
                        default=self.data.get(
                            "update_interval", DEFAULT_UPDATE_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
        )

    async def async_step_configure_weather(self, user_input=None):
        """Configure weather and seasonal specials."""
        from .recipe_fetcher import SEASONAL_MODES

        if user_input is not None:
            self.data["weather_seasonal_mode"] = user_input.get(
                "weather_seasonal_mode", "auto"
            )
            self.data["include_holiday_specials"] = user_input.get(
                "include_holiday_specials", True
            )
            self.data["weather_entity"] = user_input.get("weather_entity", "")
            return self.async_create_entry(title="", data=self.data)

        schema = vol.Schema(
            {
                vol.Required(
                    "weather_seasonal_mode",
                    default=self.data.get("weather_seasonal_mode", "auto"),
                ): _select(SEASONAL_MODES, "seasonal_mode"),
                vol.Required(
                    "include_holiday_specials",
                    default=self.data.get("include_holiday_specials", True),
                ): bool,
                _field("weather_entity", self.data.get("weather_entity")): (
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="weather")
                    )
                ),
            }
        )
        return self.async_show_form(step_id="configure_weather", data_schema=schema)

    async def async_step_providers(self, user_input=None):
        """Choose recipe sources, their order (primary + fallbacks) and API keys."""
        errors: dict[str, str] = {}
        current = parse_list(self.data.get("providers")) or list(DEFAULT_PROVIDER_ORDER)
        if user_input is not None:
            primary = user_input.get("primary_provider", current[0])
            fallbacks = [
                p
                for p in parse_list(user_input.get("fallback_providers"))
                if p != primary
            ]
            api_key = str(user_input.get("spoonacular_api_key") or "").strip()
            if "spoonacular" in [primary, *fallbacks] and not api_key:
                errors["base"] = "api_key_required"
            else:
                self.data["providers"] = [primary, *fallbacks]
                if api_key:
                    self.data["spoonacular_api_key"] = api_key
                else:
                    self.data.pop("spoonacular_api_key", None)
                return self.async_create_entry(title="", data=self.data)
            current = [primary, *fallbacks]

        providers = list(PROVIDER_LABELS)
        schema = vol.Schema(
            {
                vol.Required("primary_provider", default=current[0]): _select(
                    providers, "provider"
                ),
                vol.Optional("fallback_providers", default=current[1:]): _select(
                    providers, "provider", multiple=True
                ),
                _field(
                    "spoonacular_api_key", self.data.get("spoonacular_api_key")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="providers", data_schema=schema, errors=errors
        )

    async def async_step_filters(self, user_input=None):
        """Global default filters (basic)."""
        if user_input is not None:
            self._filters_draft = _clean(user_input)
            return await self.async_step_filters_advanced()

        values = self.data.get("filters", DEFAULT_GLOBAL_FILTERS)
        return self.async_show_form(
            step_id="filters",
            data_schema=vol.Schema(basic_filter_fields(values, sticky_meal=True)),
        )

    async def async_step_filters_advanced(self, user_input=None):
        """Global default filters (keywords, ingredients, categories)."""
        if user_input is not None:
            self.data["filters"] = {**self._filters_draft, **_clean(user_input)}
            return self.async_create_entry(title="", data=self.data)

        values = {**self.data.get("filters", {}), **self._filters_draft}
        return self.async_show_form(
            step_id="filters_advanced",
            data_schema=vol.Schema(advanced_filter_fields(values)),
            last_step=True,
        )

    # ------------------------------------------------------------ add sensor
    async def async_step_add_sensor(self, user_input=None):
        """Step 1: Ask for search keyword to get suggestions or skip."""
        if user_input is not None:
            self.search_query = user_input.get("search_query", "").strip()
            if self.search_query:
                try:
                    result = await self.hass.async_add_executor_job(
                        _fetch_api_suggestions, self.search_query
                    )
                    self.suggestions = (
                        result.get("suggestions", [])
                        if isinstance(result, dict)
                        else list(result or [])
                    )
                    if self.suggestions:
                        return await self.async_step_add_sensor_suggestions()
                except (AttributeError, ValueError, KeyError, TypeError) as e:
                    _LOGGER.error("Error fetching suggestions: %s", e)

            return await self.async_step_add_sensor_form()

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema({vol.Optional("search_query"): str}),
        )

    async def async_step_add_sensor_suggestions(self, user_input=None):
        """Step 2: Choose from suggestions."""
        if user_input is not None:
            choice = user_input.get("suggestion")
            if choice != "Manual Entry":
                self.search_query = choice
            return await self.async_step_add_sensor_form()

        options = self.suggestions + ["Manual Entry"]
        return self.async_show_form(
            step_id="add_sensor_suggestions",
            data_schema=vol.Schema({vol.Required("suggestion"): vol.In(options)}),
        )

    def _sensor_form_schema(
        self, values: dict[str, Any], *, with_type: bool
    ) -> vol.Schema:
        fields: dict[Any, Any] = {
            vol.Required("name", default=values.get("name", "")): str
        }
        if with_type:
            fields[vol.Required("type", default=values.get("type", "search"))] = (
                _select(RECIPE_TYPES, "sensor_type")
            )
        fields[_field("search_query", values.get("search_query"))] = str
        fields[_field("provider", values.get("provider"))] = _select(
            ["auto", *PROVIDER_LABELS], "provider"
        )
        fields[_field("meal_type", _normalized(values).get("meal_type"))] = _select(
            MEAL_TYPES, "meal_type"
        )
        fields[vol.Optional("configure_filters", default=False)] = bool
        return vol.Schema(fields)

    async def async_step_add_sensor_form(self, user_input=None):
        """Step 3: Sensor basics (name, type, query, source, meal type)."""
        if user_input is not None:
            data = _clean(user_input)
            go_filters = data.pop("configure_filters", False)
            if data.get("provider") == "auto":
                data.pop("provider")
            self._editing = False
            self._draft = {
                "id": str(uuid.uuid4()),
                "type": data.pop("type", "search"),
                **data,
            }
            if go_filters:
                return await self.async_step_sensor_filters()
            self.current_sensors = [*self.current_sensors, self._draft]
            return self._save()

        return self.async_show_form(
            step_id="add_sensor_form",
            data_schema=self._sensor_form_schema(
                {"search_query": self.search_query}, with_type=True
            ),
            last_step=True,
        )

    # ----------------------------------------------------------- edit sensor
    async def async_step_edit_sensor(self, user_input=None):
        custom_sensors = {s["id"]: s["name"] for s in self.current_sensors}
        if not custom_sensors:
            return self.async_abort(reason="no_custom_sensors")
        if user_input is not None:
            self.sensor_to_edit_id = user_input["sensor_id"]
            return await self.async_step_edit_sensor_form()
        return self.async_show_form(
            step_id="edit_sensor",
            data_schema=vol.Schema({vol.Required("sensor_id"): vol.In(custom_sensors)}),
        )

    def _sensor_to_edit(self) -> dict[str, Any] | None:
        return next(
            (s for s in self.current_sensors if s["id"] == self.sensor_to_edit_id), None
        )

    async def async_step_edit_sensor_form(self, user_input=None):
        sensor = self._sensor_to_edit()
        if not sensor:
            return self.async_abort(reason="no_sensors")

        if user_input is not None:
            data = _clean(user_input)
            go_filters = data.pop("configure_filters", False)
            if data.get("provider") == "auto":
                data.pop("provider")
            for key in ["name", *SENSOR_FORM_KEYS]:
                sensor.pop(key, None)
            sensor.update(data)
            self._editing = True
            self._draft = sensor
            if go_filters:
                return await self.async_step_sensor_filters()
            return self._save()

        return self.async_show_form(
            step_id="edit_sensor_form",
            data_schema=self._sensor_form_schema(sensor, with_type=False),
            last_step=True,
        )

    # --------------------------------------------------- per-sensor filters
    async def async_step_sensor_filters(self, user_input=None):
        """Detailed filters for one sensor (overrides the global defaults)."""
        if user_input is not None:
            for key in [*FILTER_BASIC_KEYS, *FILTER_ADVANCED_KEYS, *LEGACY_FILTER_KEYS]:
                if key != "meal_type":  # meal type is edited in the previous form
                    self._draft.pop(key, None)
            self._draft.update(_clean(user_input))
            if not self._editing:
                self.current_sensors = [*self.current_sensors, self._draft]
            return self._save()

        fields = {
            **basic_filter_fields(self._draft, include_meal=False),
            **advanced_filter_fields(self._draft),
        }
        return self.async_show_form(
            step_id="sensor_filters", data_schema=vol.Schema(fields), last_step=True
        )

    # ---------------------------------------------------------- remove sensor
    async def async_step_remove_sensor(self, user_input=None):
        custom_sensors = {s["id"]: s["name"] for s in self.current_sensors}
        if not custom_sensors:
            return self.async_abort(reason="no_custom_sensors")
        if user_input is not None:
            sensors_to_remove = user_input["sensors_to_remove"]
            self.current_sensors = [
                s for s in self.current_sensors if s["id"] not in sensors_to_remove
            ]
            return self._save()
        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("sensors_to_remove"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v}
                                for k, v in custom_sensors.items()
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            last_step=True,
        )
