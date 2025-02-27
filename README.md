[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
# Chefkoch Homeassistant Sensor
The `chefkoch_ha` sensor will give you random reciepes from chefkoch.

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