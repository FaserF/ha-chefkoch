[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Chefkoch Home Assistant Sensor 👨‍🍳

The **Chefkoch** integration brings recipes from Germany's largest cooking platform, [Chefkoch.de](https://www.chefkoch.de/), directly into Home Assistant.

## Features ✨

- **Daily Inspiration**: Automatically gets the 'Recipe of the Day'.
- **Search Suggestions**: Get autocomplete suggestions from Chefkoch when adding a new sensor.
- **Plus-Filter**: Automatically filters out "Chefkoch Plus" recipes that are behind a paywall.
- **Random Recipes**: Discover new meals with random recipe sensors (Standard, Vegan, Vegetarian, Baking).
- **Custom Search**: Create sensors for specific queries (e.g., "Lasagne", "Vegan Burger").
- **Rich Data**: Attributes include ingredients, instructions, preparation time, nutritional info (protein, fat, carbs), cuisine style, video links, and images.
- **No Flicker**: Sensors maintain their state during background updates or when adding new sensors.

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
3.  Copy the `chefkoch_ha` folder to `<config>/custom_components/`.

> [!WARNING]
> Downloading directly from `master` branch is not recommended.

## Configuration ⚙️

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for "Chefkoch".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=chefkoch_ha)

### Accessing the data

By default, the following sensors are created:
- `sensor.chefkoch_random_recipe`: Random recipe
- `sensor.chefkoch_daily_recipe`: Daily recipe recommendation from Chefkoch
- `sensor.chefkoch_vegan_recipe`: Vegan recipe
- `sensor.chefkoch_vegetarian_recipe`: Vegetarian recipe
- `sensor.chefkoch_random_baking_recipe`: Random baking recipe

## Custom Search Sensors

You can create sensors that match your exact needs using the configuration wizard.

1. Go to **Settings > Devices & Services** and find your Chefkoch integration.
2. Click **Configure**.
3. Select "**Add a new Search Sensor**".
4. Enter a keyword (e.g. "Pasta").
5. Choose from the **Autocomplete Suggestions** or enter a custom search term.

The integration will then find a random matching recipe for that term on every update.

## Automation Example

Send a notification with the daily recipe:

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
      title: "Recipe of the Day 👨‍🍳"
      message: >
        Here's a random recipe for you today! 🎉

        **Recipe:** {{ states('sensor.chefkoch_random_recipe') }}

        **Preparation Time:** {{ state_attr('sensor.chefkoch_random_recipe', 'totalTime') }}
        **Nutrition:** {{ state_attr('sensor.chefkoch_random_recipe', 'calories') }}, {{ state_attr('sensor.chefkoch_random_recipe', 'protein') }} Protein, {{ state_attr('sensor.chefkoch_random_recipe', 'fat') }} Fett, {{ state_attr('sensor.chefkoch_random_recipe', 'carbohydrates') }} Kohlenhydrate
        **Instructions:** {{ state_attr('sensor.chefkoch_random_recipe', 'instructions') | truncate(200) }}

        [View Recipe]({{ state_attr('sensor.chefkoch_random_recipe', 'url') }})
      data:
        image: "{{ state_attr('sensor.chefkoch_random_recipe', 'image_url') }}"
```

### Forcing an Update

If you don't want to wait for the update interval, you can force all Chefkoch sensors to refresh:

```yaml
service: chefkoch_ha.refresh_recipe
target:
  entity_id: sensor.chefkoch_random_recipe
```

## Services 🛠️

### `chefkoch_ha.refresh_recipe`
Forces an immediate refresh of all recipes.

### `chefkoch_ha.add_to_shopping_list`
Adds all ingredients from a specific Chefkoch sensor to the Home Assistant shopping list.

| Field | Description |
| :--- | :--- |
| `entity_id` | (Required) The entity ID of the Chefkoch sensor (e.g., `sensor.chefkoch_daily_recipe`). |

## Credits

- Huge thanks to [@THDMoritzEnderle](https://github.com/THDMoritzEnderle/chefkoch) for the original python library.
- Thanks to [@M-Enderle](https://github.com/M-Enderle/get-chefkoch) for the new [get-chefkoch](https://github.com/M-Enderle/get-chefkoch) library used in the latest versions.