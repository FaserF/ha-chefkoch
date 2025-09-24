[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
# Chefkoch Homeassistant Sensor
The chefkoch_ha integration provides recipes from Germany's largest cooking platform, Chefkoch.de, directly within Home Assistant. It automatically creates three standard recipe sensors and allows you to add an unlimited number of custom search sensors with powerful filters to find the perfect meal for any occasion.
All sensors refresh automatically once a day or upon a restart of Home Assistant.

## Features
- Default Sensors: Automatically creates sensors for a random recipe, the daily recipe recommendation, and a random vegan recipe upon setup.
- Powerful Custom Search Sensors: Create your own sensors with specific search queries and fine-grained filters.
- Extensive Filtering: Filter recipes by properties (e.g., "Simple", "Quick"), diet (e.g., "Vegan", "Low Carb"), categories, countries, meal types, preparation time, and minimum rating.
- Rich Attributes: Each sensor provides a wealth of information, including title, URL, image, ingredients, instructions, preparation times, calories, and ratings.

## Installation
### 1. Using HACS (recommended way)

This integration is NO official HACS Integration right now.

Open HACS then install the "chefkoch" integration or use the link below.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=FaserF&repository=ha-chefkoch&category=integration)

If you use this method, your component will always update to the latest version.

### 2. Manual

- Download the latest zip release from [here](https://github.com/FaserF/ha-chefkoch/releases/latest)
- Extract the zip file
- Copy the folder "chefkoch" from within custom_components with all of its components to `<config>/custom_components/`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly, the status in the "master" branch can be in development and therefore is maybe not working.

## Configuration

Go to Configuration -> Integrations and click on "add integration". Then search for "Chefkoch".

## Accessing the data
There will be three new sensors after adding it via HA:
- sensor.chefkoch_random_recipe: Random recipe
- sensor.chefkoch_daily_recipe: Daily recipe recommendation from chefkoch
- sensor.chefkoch_vegan_recipe: Vegan recipe

## Creating Custom Search Sensors
You can create sensors that match your exact needs.
1. Go to Settings > Devices & Services and find your Chefkoch integration.
2. Click Configure.
3. Select "Add a new Search Sensor".
4. Fill out the form with your desired filters.

### Available Filters
- Sensor Name: A friendly name for your sensor (e.g., "Quick Pasta Dishes"). The entity ID will be generated from this.
- Search Term: The main keyword for your search (e.g., "Lasagne").
- Properties: Add tags like Simple, Quick, Party. Separate multiple values with a comma.
- Diet: Filter for dietary restrictions like Vegan, Vegetarian, Low Carb. Comma-separated.
- Categories: Filter by recipe categories like Pizza, Salad. Comma-separated.
- Countries: Find recipes from specific countries like Italy, German. Comma-separated.
- Meal Type: Filter by meal types such as Main Dish, Dessert. Comma-separated.
- Max. Preparation Time: Choose a maximum preparation time in minutes.
- Minimum Rating: Set a minimum star rating.

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