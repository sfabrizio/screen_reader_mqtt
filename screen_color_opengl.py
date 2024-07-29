import argparse
import colorsys
import json
import logging
import threading
import time
from typing import Tuple

import numpy as np
import paho.mqtt.client as mqtt
from mss import mss
from PIL import Image

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

class Config:
    MQTT_BROKER_HOST = '192.168.1.200'
    MQTT_BROKER_PORT = 1883
    MQTT_TOPIC = 'myhome'
    TRANSITION_DURATION = 0.5
    UPDATE_INTERVAL = 0.1

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect

    def connect(self):
        try:
            self.client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"Connected to MQTT broker with result code {rc}")

    def publish(self, topic: str, payload: dict):
        try:
            self.client.publish(topic, json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")

class ScreenColorPublisher:
    def __init__(self, mqtt_client: MQTTClient):
        self.mqtt_client = mqtt_client
        self.prev_color = (0, 0, 0)
        self.target_color = (0, 0, 0)

    def get_dominant_color(self) -> Tuple[int, int, int]:
        with mss() as sct:
            extended_screen = next((m for m in sct.monitors if m['left'] > 0 or m['top'] > 0), sct.monitors[0])
            screenshot = sct.grab(extended_screen)
            image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            np_img = np.array(image)

        unique_colors, counts = np.unique(np_img.reshape(-1, np_img.shape[2]), axis=0, return_counts=True)
        sorted_colors = unique_colors[np.argsort(counts)[::-1]]

        for r, g, b in sorted_colors:
            h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            if s > 0.3 and v > 0.3:
                return int(r), int(g), int(b)

        return 128, 128, 128

    def publish_color(self):
        while True:
            try:
                self.target_color = self.get_dominant_color()
                if self.target_color != self.prev_color:
                    logger.info(f"Color change: {self.prev_color} -> {self.target_color}")
                    self.transition_color()
                    self.prev_color = self.target_color
                time.sleep(Config.UPDATE_INTERVAL)
            except Exception as e:
                logger.error(f"Error in publish_color: {e}")

    def transition_color(self):
        start_time = time.time()
        while time.time() - start_time < Config.TRANSITION_DURATION:
            progress = (time.time() - start_time) / Config.TRANSITION_DURATION
            r = int(self.prev_color[0] + (self.target_color[0] - self.prev_color[0]) * progress)
            g = int(self.prev_color[1] + (self.target_color[1] - self.prev_color[1]) * progress)
            b = int(self.prev_color[2] + (self.target_color[2] - self.prev_color[2]) * progress)

            payload = {"cmd": "setRGB", "payload": f"{r} {g} {b}"}
            self.mqtt_client.publish(Config.MQTT_TOPIC, payload)
            logger.debug(f"Sending: {payload}")
            time.sleep(0.01)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Screen Color Publisher")
    parser.add_argument("--transition-duration", type=float, default=0.5, help="Color transition duration in seconds")
    parser.add_argument("--update-interval", type=float, default=0.1, help="Screen color update interval in seconds")
    return parser.parse_args()

def main():
    args = parse_arguments()
    Config.TRANSITION_DURATION = args.transition_duration
    Config.UPDATE_INTERVAL = args.update_interval

    mqtt_client = MQTTClient()
    mqtt_client.connect()

    publisher = ScreenColorPublisher(mqtt_client)
    publish_thread = threading.Thread(target=publisher.publish_color)
    publish_thread.daemon = True
    publish_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")

if __name__ == '__main__':
    main()