# Screen Color Reader MQTT

Kinda of Ambilight feature from Philips TV, but done by me so it will conect to all my led strips arround the house with mqtt messages. I did with that IA help but my ideas. I was testing Sonet 3.5 and I sastified with the results:

## Demo Video

[![Screen Color Reader MQTT Demo](https://img.youtube.com/vi/x_EGztl94cI/0.jpg)](https://www.youtube.com/watch?v=x_EGztl94cI)


This Python script captures the dominant color from your screen (with support for extended displays) and publishes it to an MQTT broker. It's designed to work seamlessly with home automation systems, allowing you to create dynamic lighting effects based on your screen content.

## Features

- Detects dominant color from the screen in real-time
- Supports extended displays
- Publishes color changes to MQTT broker
- Smooth color transitions
- Configurable update intervals and sensitivity
- Differentiates between various shades of colors
- Sends "turn off" signal (black color) when script is terminated
- Automatically retries MQTT connection if it fails

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/screen-color-publisher.git
cd screen-color-publisher
```

2. Create a virtual environment (optional but recommended):

```bash
python -m venv screen-color
source screen-color/bin/activate  # On Windows use venv\Scripts\activate
```

3. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the script with:

```bash
python screen_color_publisher.py
```

### Command-line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--transition-duration` | Color transition duration in seconds | 0.5 |
| `--update-interval` | Screen color update interval in seconds | 0.1 |
| `--capture-interval` | Screen capture interval in seconds | 0.1 |
| `--mqtt-retry-interval` | MQTT connection retry interval in seconds | 5 |

### Examples

1. Run with default settings:

```bash
python screen_color_publisher.py
```

2. Set a longer transition duration:
```bash
python screen_color_publisher.py --transition-duration 1.0
```

3. Decrease update frequency:
```bash
python screen_color_publisher.py --update-interval 0.5 --capture-interval 0.5
```

4. Change MQTT retry interval:
```bash
python screen_color_publisher.py --mqtt-retry-interval 10
```

## Configuration

Edit the `Config` class in the script to customize:

- MQTT broker settings
- Color difference threshold
- Force update interval
- Cooldown period
- MQTT retry interval

## Troubleshooting

If you encounter any issues:

1. Check your MQTT broker connection settings
2. Ensure you have permission to capture screen content
3. Verify that your display is detected correctly

For extended displays, make sure the script is detecting the correct monitor.

If the MQTT connection fails, the script will automatically retry connecting at the specified interval.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [mss](https://github.com/BoboTiG/python-mss) for screen capture functionality
- [paho-mqtt](https://github.com/eclipse/paho.mqtt.python) for MQTT communication

---

**Note**: This script is intended for creative and home automation purposes. Always respect copyright and privacy when capturing and processing screen content.