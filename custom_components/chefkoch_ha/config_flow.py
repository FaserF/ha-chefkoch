"""Config flow for Chefkoch integration."""

from homeassistant import config_entries
from .const import DOMAIN

class ChefkochConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chefkoch."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return self.async_create_entry(title="Chefkoch", data={})
