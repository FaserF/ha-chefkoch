[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Chefkoch Home Assistant Sensor 👨‍🍳

The **Chefkoch** integration brings recipes from Germany's largest cooking platform, [Chefkoch.de](https://www.chefkoch.de/), directly into Home Assistant.

## Features ✨

- **Daily Inspiration**: Automatically gets the 'Recipe of the Day'.
- **Search Suggestions**: Get autocomplete suggestions from Chefkoch when adding a new sensor.
- **Random Recipes**: Discover new meals with random recipe sensors (Standard, Vegan, Baking).
- **Custom Search**: Create sensors for specific queries (e.g., "Lasagne", "Vegan Burger").
- **Powerful Filtering**: Filter by diet (Vegan, Low Carb), detailed categories, origin (Italy, Asia), and more.
- **Rich Data**: Attributes include ingredients, preparation time, nutritional info (protein, fat, carbs), cuisine style, video links, and images.

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

There will be four new sensors after adding it via HA:
- `sensor.chefkoch_random_recipe`: Random recipe
- `sensor.chefkoch_daily_recipe`: Daily recipe recommendation from chefkoch
- `sensor.chefkoch_vegan_recipe`: Vegan recipe
- `sensor.chefkoch_random_baking_recipe`: Random baking recipe

## Custom Search Sensors

You can create sensors that match your exact needs.

1. Go to **Settings > Devices & Services** and find your Chefkoch integration.
2. Click **Configure**.
3. Select "**Add a new Search Sensor**".
4. Fill out the form with your desired filters.

### Available Filters
> [!NOTE]
> Values must be in **German** as they are passed directly to the Chefkoch API.

[Full details here](https://github.com/M-Enderle/chefkoch?tab=readme-ov-file#available-filter-options)

- **Sensor Name**: Friendly name (e.g., "Quick Pasta").
- **Search Term**: Main keyword (e.g., "Lasagne").
- **Properties**: `Einfach`, `Schnell`, `Basisrezepte`, `Preiswert`.
- **Diet**: `Vegetarisch`, `Vegan`, `Kalorienarm`, `Low Carb`, `Ketogen`, `Paleo`, `Fettarm`, `Trennkost`, `Vollwert`.
- **Categories**: `Auflauf`, `Pizza`, `Salat`, `Suppe`, `Kuchen`, `Dessert`, etc.
- **Countries**: `Italien`, `Asien`, `Indien`, `Mexiko`, `Deutschland`, etc.
- **Meal Type**: `Hauptspeise`, `Vorspeise`, `Beilage`, `Dessert`, `Snack`, `Frühstück`.
- **Max. Preparation Time**: In minutes.
- **Minimum Rating**: `Alle`, `2`, `3`, `4`, `Top`.

You can add, edit, or remove your custom search sensors at any time through the same **Configure** menu.

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
        **Category:** {{ state_attr('sensor.chefkoch_random_recipe', 'category') }}

        [View Recipe]({{ state_attr('sensor.chefkoch_random_recipe', 'url') }})
      data:
        image: "{{ state_attr('sensor.chefkoch_random_recipe', 'image_url') }}"
```

### Forcing an Update

If you don't want to wait for the daily refresh, you can force all Chefkoch sensors to update:

```yaml
service: chefkoch_ha.refresh_recipe
target:
  entity_id: sensor.chefkoch_random_recipe # Any chefkoch sensor works
```

## Services 🛠️

### `chefkoch_ha.refresh_recipe`
Forces an immediate refresh of all recipes. This is particularly useful for getting a new random recipe without waiting for the next update interval.

| Field | Description |
| :--- | :--- |
| `target` | (Required) Target the Chefkoch integration or a specific sensor. |

### `chefkoch_ha.add_to_shopping_list`
Adds all ingredients from a specific Chefkoch sensor to the Home Assistant shopping list.

| Field | Description |
| :--- | :--- |
| `entity_id` | (Required) The entity ID of the Chefkoch sensor (e.g., `sensor.chefkoch_daily_recipe`). |

## Troubleshooting & Bug Reporting

Open an issue over at [GitHub Issues](https://github.com/FaserF/ha-chefkoch/issues). Please attach logs with debugging enabled.

To enable debugging:

```yaml
logger:
  logs:
    custom_components.chefkoch_ha: debug
```

## Credits

Huge thanks to [@THDMoritzEnderle](https://github.com/THDMoritzEnderle/chefkoch) for the underlying python library.