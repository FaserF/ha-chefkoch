[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
# Chefkoch Homeassistant Sensor
The `chefkoch` sensor will give you the daily top reciepe from chefkoch.

PLEASE NOTE: NOT WORKING YET - work in progress!

## Installation
### 1. Using HACS (recommended way)

This integration will be a official HACS Integration, once it is fully working.

Open HACS then install the "Chefkoch" integration.

If you use this method, your component will always update to the latest version.

### 2. Manual

- Download the latest zip release from [here](https://github.com/FaserF/ha-chefkoch/releases/latest)
- Extract the zip file
- Copy the folder "chefkoch" from within custom_components with all of its components to `<config>/custom_components/`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly, the status in the "master" branch can be in development and therefore is maybe not working.

## Configuration

Go to Configuration -> Integrations and click on "add integration". Then search for "Chefkoch".

## Bug reporting
Open an issue over at [github issues](https://github.com/FaserF/ha-chefkoch/issues). Please prefer sending over a log with debugging enabled.

To enable debugging enter the following in your configuration.yaml

```yaml
logger:
    logs:
        custom_components.chefkoch: debug
```

You can then find the log in the HA settings -> System -> Logs -> Enter "chefkoch" in the search bar -> "Load full logs"

## Thanks to
Huge thanks to [@THDMoritzEnderle](https://github.com/THDMoritzEnderle/chefkoch) for the chefkoch python library that this integration is using.