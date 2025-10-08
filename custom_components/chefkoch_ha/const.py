"""Constants for the Chefkoch integration."""
DOMAIN = "chefkoch_ha"

DEFAULT_SENSORS = [
    {"type": "random", "id": "random", "name": "Chefkoch Random Recipe"},
    {"type": "daily", "id": "daily", "name": "Chefkoch Daily Recipe"},
    {"type": "vegan", "id": "vegan", "name": "Chefkoch Vegan Recipe"},
    {"type": "baking", "id": "baking", "name": "Chefkoch Random Baking Recipe"},
]

DEFAULT_UPDATE_INTERVAL = 24  # in hours