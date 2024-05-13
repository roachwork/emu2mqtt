# EMU2MQTT

An alternative way to integrate the [Rainforest EMU-2](https://www.rainforestautomation.com/rfa-z105-2-emu-2-2/) into the Home Assistant Energy Dashboard over mqtt.

## Installation

Via docker
```
docker run -d --privileged --rm --name emu2mqtt \
  -e TZ=America/Los_Angeles \
  -e MQTT_HOSTNAME=127.0.0.1 \
  -e MQTT_USERNAME=user \
  -e MQTT_PASSWORD=pass \
  -e MQTT_PASSWORD=1883 \
  -e SERIAL_DEVICE=/dev/ttyACM0 \
  -e SERIAL_BAUDRATE=115200 \
  -e LOG_LEVEL=INFO \
  ghcr.io/roachwork/emu2mqtt:latest
```

Via docker-compose.yml
```
version: '3'
services:
  emu2mqtt:
    container_name: emu2mqtt
    image: ghcr.io/roachwork/emu2mqtt:latest
    environment:
      - TZ=America/Los_Angeles
      - MQTT_HOSTNAME=127.0.0.1
      - MQTT_USERNAME=user
      - MQTT_PASSWORD=pass
      - MQTT_PORT=1883
      - SERIAL_DEVICE=/dev/ttyACM0
      - SERIAL_BAUDRATE=115200
      - LOG_LEVEL=INFO
    restart: unless-stopped
    privileged: true
```

## Main Features
- Runs using asyncio based on the Python 3.12 alpine docker image
- Gracefully reconnects after disconnect
- Runs on raspberry pi's
- Auto-discovers device and entities in Home Assistant
- Home Assistant
  - Sensors
    - Power - Current power being used
    - Current Price - The cost per kWh in cents
    - Current Period Usage - Total power delivered since the period started
    - Total Delivered - The total power delivered to your meter from the grid
    - Total Received - The total power received by your meter from your solar panels
    - Current Period Start - The date which the current period started
    - Meter Connection Strength - The EMU-2 device's connection strength to the meter
    - Meter Status - Is the EMU-2 actively connected to the meter
    - Status - Is this service actively connected to the EMU-2 device
  - Buttons
    - Restart - Restart EMU-2 device
    - Set energy price - Set the price on EMU-2 device
    - Close current period - Mark that the current period is closed on EMU-2 device to start a new period
