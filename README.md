[![Home Assistant Marketplace](https://img.shields.io/badge/Marketplace-Chefkoch-41BDF5.svg?style=for-the-badge&logo=home-assistant)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=FaserF&repository=ha-chefkoch&category=integration)
[![Downloads (Current release)](https://img.shields.io/github/downloads/FaserF/ha-chefkoch/latest/chefkoch_ha.zip?label=Downloads%20(Current%20release)&style=for-the-badge)](https://github.com/FaserF/ha-chefkoch/releases)

# Chefkoch Home Assistant Integration 👨‍🍳

The **Chefkoch** integration brings recipes from Germany's largest cooking platform, [Chefkoch.de](https://www.chefkoch.de/), directly into Home Assistant via the official Chefkoch REST API (100% pure API, zero webscraping).

---

## ❤️ Support This Project

> I maintain this integration in my **free time alongside my regular job** — bug hunting, new features, and testing on real hardware. Test devices cost money, and every donation helps me stay independent and free up more time for open-source work.
>
> Donations are completely voluntary — but the more support I receive, the less I depend on other income sources and the more time I can realistically invest into these GitHub projects. 💪

<div align="center">

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor%20on-GitHub-%23EA4AAA?style=for-the-badge&logo=github-sponsors&logoColor=white)](https://github.com/sponsors/FaserF)&nbsp;&nbsp;
[![PayPal](https://img.shields.io/badge/Donate%20via-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/FaserF)

</div>

---
## Features ✨

- **Official REST API v2**: Fast, stable, and clean API queries without webscraping or brittle RSS feeds.
- **Weather & Seasonal Intelligence**: Automatically suggests recipes based on current outdoor temperatures and conditions (light salads/wraps/bowls in summer; hearty soups/stews/casseroles in winter; seasonal specials for Halloween, Christmas, and Easter).
- **Daily Inspiration**: Automatically gets top-rated and trending daily recommendations from Chefkoch.
- **Search Suggestions**: Get real-time autocomplete suggestions from Chefkoch when adding or configuring sensors.
- **Plus-Filter**: Automatically filters out "Chefkoch Plus" recipes that are behind a paywall.
- **Random Recipes**: Discover new meals with random recipe sensors (Standard, Weather, Vegan, Vegetarian, Baking).
- **Custom Search**: Create sensors for specific queries (e.g., "Lasagne", "Vegan Burger", "Kürbis").
- **Rich Data**: Attributes include ingredients, instructions, preparation time, nutritional info (protein, fat, carbs), cuisine style, saved cookbook count (`saved_recipes_count`), view count (`view_count`), top user comments (`top_comments`), subtitle, tags, category path (`category_breadcrumb`), author notes (`author_notes`), video links/IDs, and images.
- **Meal Plan**: Generate a multi-day recipe plan via the `chefkoch_ha.generate_meal_plan` service; results are fired as a `chefkoch_meal_plan_generated` event.
- **No Flicker**: Sensors maintain their state during background updates or when adding new sensors.

## Installation 🛠️

### 1. Using Home Assistant Marketplace (Recommended)

This integration is available in the **Home Assistant Marketplace** (Home Assistant 2026.11+ / HACS):

1. Open Home Assistant and navigate to **Marketplace** (or **HACS** on older releases).
2. Search for "**Chefkoch**".
3. Click **Install** / **Download**.

[![Open your Home Assistant instance and open a repository inside the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=FaserF&repository=ha-chefkoch&category=integration)

> [!TIP]
> Home Assistant Marketplace automatically tracks and installs updates for the component.

### 2. Manual Installation

1. Download the latest [Release](https://github.com/FaserF/ha-chefkoch/releases/latest).
2. Extract the ZIP file.
3. Copy the `chefkoch_ha` folder to `<config>/custom_components/`.

> [!WARNING]
> Downloading directly from `main` branch without a release zip is not recommended.

## Configuration ⚙️

1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration**.
3. Search for "Chefkoch".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=chefkoch_ha)

### Accessing the data

By default, the following sensors are created:
- `sensor.chefkoch_daily_recipe`: Daily recipe recommendation from Chefkoch
- `sensor.chefkoch_weather_recipe`: Weather- and season-adaptive recipe (hot weather light/salads, cold weather stews/soul food, holiday specials)
- `sensor.chefkoch_random_recipe`: Random recipe
- `sensor.chefkoch_vegan_recipe`: Vegan recipe
- `sensor.chefkoch_vegetarian_recipe`: Vegetarian recipe
- `sensor.chefkoch_random_baking_recipe`: Random baking recipe

### Weather & Seasonal Customization
You can tune the weather-adaptive sensor via **Settings > Devices & Services > Chefkoch > Configure > Configure Weather & Seasonal Sensor**:
- **Seasonal Mode**: Automatic outdoor temperature & seasonal sync (`auto`), seasonal forced modes (`spring`, `summer`, `autumn`, `winter`), or holiday specials (`halloween`, `christmas`, `easter`).
- **Holiday Specials**: Toggle automatic holiday-themed recipes during special weeks (e.g., Halloween treats & pumpkin dishes; Christmas cookies & roasts).
- **Weather Entity**: Choose an outdoor weather entity (e.g., `weather.home`) to track local temperature and outdoor conditions.

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
| `servings` | (Optional) Target number of servings to dynamically scale ingredient quantities (e.g., `2`). |

### `chefkoch_ha.generate_meal_plan`
Generates a multi-day meal plan with recipe suggestions. Fires a `chefkoch_meal_plan_generated` event on the Home Assistant event bus with the results.

| Field | Description |
| :--- | :--- |
| `days` | (Optional, 1–7) Number of days to generate recipes for. Defaults to `7`. |
| `query` | (Optional) Search query or diet keyword (e.g., `Vegetarisch`, `Pasta`, `Schnell`). |

**Event payload** (`chefkoch_meal_plan_generated`):
```json
{
  "meal_plan": [
    {"day": 1, "title": "Spaghetti Carbonara", "url": "https://www.chefkoch.de/rezepte/..."},
    ...
  ],
  "days": 7,
  "query": "Vegetarisch"
}
```

### `chefkoch_ha.get_recommendations`
Fetches 3 distinct curated recipes directly via API without needing an integration reload or refreshing sensor states. Returns response data directly via `response_variable`:
- `recipe_1`: Weather/seasonal dish (e.g. salads/wraps in summer, stews/soups in winter, holiday specials)
- `recipe_2`: Vegetarian or vegan dish
- `recipe_3`: Alternative weather/seasonal dish (guaranteed distinct from #1)

```yaml
service: chefkoch_ha.get_recommendations
response_variable: food_recs

# Access in automations or scripts:
# {{ food_recs.recipe_1.title }} ({{ food_recs.recipe_1.url }})
# {{ food_recs.recipe_2.title }} ({{ food_recs.recipe_2.url }})
# {{ food_recs.recipe_3.title }} ({{ food_recs.recipe_3.url }})
```

### `chefkoch_ha.get_recipe`
Fetches a single fresh recipe directly via API on-demand with full details (prep time, difficulty, rating, calories, ingredients, category path, image) and returns it in the response variable.

| Field | Description |
| :--- | :--- |
| `recipe_type` | (Optional) Recipe type: `random`, `weather`, `vegan`, `vegetarian`, `baking`, or `search`. Default: `random`. |
| `query` | (Optional) Custom search term or ingredient (e.g., `Pasta`, `Kürbis`, `Tofu`). |

```yaml
service: chefkoch_ha.get_recipe
data:
  recipe_type: weather
response_variable: result

# Access in automations or scripts:
# {{ result.recipe.title }} - {{ result.recipe.url }}
# {{ result.recipe.totalTime }} | {{ result.recipe.calories }}
```

## Credits

- Huge thanks to [@THDMoritzEnderle](https://github.com/THDMoritzEnderle/chefkoch) for the original python library.
- Thanks to [@M-Enderle](https://github.com/M-Enderle/get-chefkoch) for the [get-chefkoch](https://github.com/M-Enderle/get-chefkoch) library.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
