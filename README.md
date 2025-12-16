[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Chefkoch Home Assistant Sensor 👨‍🍳

The **Chefkoch** integration brings recipes from Germany's largest cooking platform, [Chefkoch.de](https://www.chefkoch.de/), directly into Home Assistant.

## Features ✨

- **Daily Inspiration**: Automatically gets the 'Recipe of the Day'.
- **Random Recipes**: Discover new meals with random recipe sensors (Standard, Vegan, Baking).
- **Custom Search**: Create sensors for specific queries (e.g., "Lasagne", "Vegan Burger").
- **Powerful Filtering**: Filter by diet (Vegan, Low Carb), detailed categories, origin (Italy, Asia), and more.
- **Rich Data**: Attributes include ingredients, preparation time, nutritional info, and images.

## Installation 🛠️

### 1. Using HACS (Recommended)

This integration works great with HACS.

1.  Open HACS.
2.  Search for "Chefkoch".
3.  Click **Download**.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=FaserF&repository=ha-chefkoch&category=integration)

> [!TIP]
> HACS updates the component automatically.

### 2. Manual Installation

1.  Download the latest [Release](https://github.com/FaserF/ha-chefkoch/releases/latest).
2.  Extract the ZIP file.
3.  Copy the `chefkoch` folder to `<config>/custom_components/`.

> [!WARNING]
> Downloading directly from `master` branch is not recommended.

## Configuration ⚙️

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for "Chefkoch".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=chefkoch)

## Accessing the data
There will be four new sensors after adding it via HA:
- sensor.chefkoch_random_recipe: Random recipe
- sensor.chefkoch_daily_recipe: Daily recipe recommendation from chefkoch
- sensor.chefkoch_vegan_recipe: Vegan recipe
- sensor.chefkoch_random_baking_recipe: Random baking recipe

## Creating Custom Search Sensors
You can create sensors that match your exact needs.
1. Go to Settings > Devices & Services and find your Chefkoch integration.
2. Click Configure.
3. Select "Add a new Search Sensor".
4. Fill out the form with your desired filters.

### Available Filters (the filters have to be in german)
[Full details here](https://github.com/M-Enderle/chefkoch?tab=readme-ov-file#available-filter-options)
- Sensor Name: A friendly name for your sensor (e.g., "Quick Pasta Dishes"). The entity ID will be generated from this.
- Search Term: The main keyword for your search (e.g., "Lasagne").
- Properties: Einfach, Schnell, Basisrezepte, Preiswert. Separate multiple values with a comma.
- Diet: Vegetarisch, Vegan, Kalorienarm, Low Carb, Ketogen, Paleo, Fettarm, Trennkost, Vollwert. Comma-separated.
- Categories: Auflauf, Pizza, Reis- oder Nudelsalat, Salat, Salatdressing, Tarte, Fingerfood, Dips, Saucen, Suppe, Klöße, Brot und Brötchen, Brotspeise, Aufstrich, Süßspeise, Eis, Kuchen, Kekse, Torte, Confiserie, Getränke, Shake, Gewürzmischung, Pasten, Studentenküche. Comma-separated.
- Countries: Deutschland, Italien, Spanien, Portugal, Frankreich, England, Osteuropa, Skandinavien, Griechenland, Türkei, Russland, Naher Osten, Asien, Indien, Japan, Amerika, Mexiko, Karibik, Lateinamerika, Afrika, Marokko, Ägypten, Australien. Comma-separated.
- Meal Type: Hauptspeise, Vorspeise, Beilage, Dessert, Snack, Frühstück Comma-separated.
- Max. Preparation Time: Choose a maximum preparation time in minutes.
- Minimum Rating: Set a minimum star rating: Alle, 2, 3, 4, Top

You can add, edit, or remove your custom search sensors at any time through the same Configure menu.

### Automations
```yaml
alias: "Daily Random Recipe"
description: "Sends a daily random recipe message with attribute details."
mode: single
trigger:
  - platform: time
    at: "09:00:00"
action:
  - service: notify.notify
    data:
      message: >
        Here's a random recipe for you today! 🎉

        **Recipe:** {{ states.sensor.chefkoch_random_recipe.state }}


        **URL:** {{ state_attr('sensor.chefkoch_random_recipe', 'url') }}

        **Image:** {{ state_attr('sensor.chefkoch_random_recipe', 'image_url') }}

        **Preparation Time:** {{ state_attr('sensor.chefkoch_random_recipe', 'totalTime') }}

        **Ingredients:** {{ state_attr('sensor.chefkoch_random_recipe', 'ingredients') | join(', ') }}

        **Calories:** {{ state_attr('sensor.chefkoch_random_recipe', 'calories') }}

        **Category:** {{ state_attr('sensor.chefkoch_random_recipe', 'category') }}

      title: "Recipe of the Day"
```

## Forcing an Update
If you don't want to wait for the daily refresh, you can force all Chefkoch sensors to update by calling the homeassistant.reload_config_entry service.

```yaml
- service: homeassistant.reload_config_entry
  target:
    entity_id: sensor.chefkoch_random_recipe # You can use any of your chefkoch sensors here
```

## Bug reporting
Open an issue over at [github issues](https://github.com/FaserF/ha-chefkoch/issues). Please prefer sending over a log with debugging enabled.

To enable debugging enter the following in your configuration.yaml

```yaml
logger:
    logs:
        custom_components.chefkoch_ha: debug
```

You can then find the log in the HA settings -> System -> Logs -> Enter "chefkoch" in the search bar -> "Load full logs"

## Why is it called chefkoch_ha and not chefkoch?
Due to the problem, that the corresponding python module is also called "chefkoch", this integration will fail to load some dependencies, when both the integration and the python module are called the same.

## Thanks to
Huge thanks to [@THDMoritzEnderle](https://github.com/THDMoritzEnderle/chefkoch) for the chefkoch python library that this integration is using.