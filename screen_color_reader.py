import argparse
import colorsys
import json
import logging
import threading
import time
from typing import Tuple
from collections import deque

import numpy as np
import paho.mqtt.client as mqtt
from mss import mss
from PIL import Image
from scipy.spatial import distance

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('color_detection.log', mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

class Config:
    MQTT_BROKER_HOST = '192.168.1.200'
    MQTT_BROKER_PORT = 1883
    MQTT_TOPIC = 'myhome'
    TRANSITION_DURATION = 0.5
    UPDATE_INTERVAL = 0.1
    SCREEN_CAPTURE_INTERVAL = 0.1
    COLOR_DIFFERENCE_THRESHOLD = 30
    FORCE_UPDATE_INTERVAL = 5
    COOLDOWN_PERIOD = 1.0

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
        self.last_capture_time = 0
        self.last_update_time = 0
        self.lock = threading.Lock()
        self.last_significant_change_time = 0
        self.color_history = deque(maxlen=5)
        self.ema_color = (0, 0, 0)
        self.ema_alpha = 0.3

    def get_dominant_color(self) -> Tuple[int, int, int]:
        current_time = time.time()
        with self.lock:
            if current_time - self.last_capture_time < Config.SCREEN_CAPTURE_INTERVAL:
                return self.target_color

            with mss() as sct:
                extended_screen = next((m for m in sct.monitors if m['left'] > 0 or m['top'] > 0), None)
                monitor = extended_screen if extended_screen else sct.monitors[0]
                screenshot = sct.grab(monitor)

            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img = img.resize((50, 50), Image.LANCZOS)
            np_img = np.array(img)

            self.last_capture_time = current_time

        pixels = np_img.reshape(-1, 3)
        unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)
        sorted_indices = np.argsort(counts)[::-1]

        for r, g, b in unique_colors[sorted_indices]:
            h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            if s > 0.15 and v > 0.15:
                return int(r), int(g), int(b)

        return 128, 128, 128

    def get_color_name(self, color):
        r, g, b = color
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        if s < 0.1 and v > 0.9:
            return "White"
        elif v < 0.1:
            return "Black"
        elif s < 0.1:
            return "Gray"
        
        if h < 0.05 or h > 0.95:
            return "Red"
        elif 0.05 <= h < 0.10:
            return "Orange"
        elif 0.10 <= h < 0.18:
            return "Yellow"
        elif 0.18 <= h < 0.40:
            return "Green"
        elif 0.40 <= h < 0.70:
            if v < 0.3:
                return "Dark Blue"
            elif v < 0.7:
                return "Blue"
            else:
                return "Light Blue"
        elif 0.70 <= h < 0.85:
            return "Purple"
        else:
            return "Pink"

    def is_color_different(self, color1, color2):
        return distance.euclidean(color1, color2) > Config.COLOR_DIFFERENCE_THRESHOLD

    def update_ema_color(self, new_color):
        self.ema_color = tuple(int(self.ema_alpha * new + (1 - self.ema_alpha) * old) 
                               for new, old in zip(new_color, self.ema_color))

    def is_color_stable(self, color):
        return len(self.color_history) == 5 and all(self.get_color_name(c) == self.get_color_name(color) for c in self.color_history)

    def publish_color(self):
        last_published_color = None
        last_published_time = 0

        while True:
            try:
                new_color = self.get_dominant_color()
                current_time = time.time()
                
                self.update_ema_color(new_color)
                self.color_history.append(self.ema_color)
                
                if self.is_color_different(self.ema_color, self.target_color) or \
                   current_time - self.last_significant_change_time > Config.FORCE_UPDATE_INTERVAL:
                    
                    if self.is_color_stable(self.ema_color) or \
                       current_time - self.last_significant_change_time > Config.FORCE_UPDATE_INTERVAL:
                        
                        color_name = self.get_color_name(self.ema_color)
                        
                        if (last_published_color is None or 
                            color_name != self.get_color_name(last_published_color) or
                            current_time - last_published_time > Config.COOLDOWN_PERIOD):
                            
                            with self.lock:
                                self.target_color = self.ema_color
                            logger.info(f"Color change: {self.prev_color} -> {self.target_color} ({color_name})")
                            self.transition_color()
                            self.prev_color = self.target_color
                            self.last_significant_change_time = current_time
                            last_published_color = self.ema_color
                            last_published_time = current_time
                
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
            time.sleep(0.01)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Screen Color Publisher")
    parser.add_argument("--transition-duration", type=float, default=0.5, help="Color transition duration in seconds")
    parser.add_argument("--update-interval", type=float, default=0.1, help="Screen color update interval in seconds")
    parser.add_argument("--capture-interval", type=float, default=0.1, help="Screen capture interval in seconds")
    return parser.parse_args()

def main():
    args = parse_arguments()
    Config.TRANSITION_DURATION = args.transition_duration
    Config.UPDATE_INTERVAL = args.update_interval
    Config.SCREEN_CAPTURE_INTERVAL = args.capture_interval

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