"""Constants for the Chefkoch integration."""

DOMAIN = "chefkoch_ha"
CHEFKOCH_BASE_URL = "https://www.chefkoch.de/rezepte/"

DEFAULT_SENSORS = [
    {"type": "random", "id": "random", "name": "Chefkoch Random Recipe"},
    {"type": "daily", "id": "daily", "name": "Chefkoch Daily Recipe"},
    {"type": "weather", "id": "weather", "name": "Chefkoch Weather Recipe"},
    {"type": "vegan", "id": "vegan", "name": "Chefkoch Vegan Recipe"},
    {"type": "vegetarian", "id": "vegetarian", "name": "Chefkoch Vegetarian Recipe"},
    {"type": "baking", "id": "baking", "name": "Chefkoch Random Baking Recipe"},
]

DEFAULT_UPDATE_INTERVAL = 24  # in hours
