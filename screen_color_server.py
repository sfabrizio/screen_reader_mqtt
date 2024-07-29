from flask import Flask, jsonify
from flask_cors import CORS
import numpy as np
from mss import mss
from PIL import Image
import time
import paho.mqtt.client as mqtt
import colorsys
import json
import logging
import threading

# MQTT configuration
MQTT_BROKER_HOST = '192.168.1.200'
MQTT_BROKER_PORT = 1883
MQTT_TOPIC = 'myhome'

# MQTT client
mqtt_client = mqtt.Client()

def on_mqtt_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")

mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
mqtt_client.on_connect = on_mqtt_connect

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def get_dominant_color():
    with mss() as sct:
        monitor = sct.monitors[0]  # Capture the primary monitor
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        
        # Convert to numpy array
        np_img = np.array(img)
        
        # Flatten the image and get the unique colors with their counts
        unique_colors, counts = np.unique(np_img.reshape(-1, np_img.shape[2]), axis=0, return_counts=True)
        
        # Sort the colors by their counts in descending order
        sorted_colors = unique_colors[np.argsort(counts)[::-1]]
        
        # Iterate through the sorted colors and find the first one that is not too close to white or black
        for r, g, b in sorted_colors:
            hsv = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            if hsv[1] > 0.3 and hsv[2] > 0.3:
                return int(r), int(g), int(b)
        
        # If no suitable color is found, return a default value
        return 128, 128, 128

def publish_screen_color():
    prev_color = (0, 0, 0)
    target_color = (0, 0, 0)
    transition_duration = 0.5  # Transition duration in seconds
    
    while True:
        # Get the dominant color of the screen
        r, g, b = get_dominant_color()
        target_color = (r, g, b)
        
        # Check if the color has changed since the last update
        if target_color != prev_color:
            # Transition the color smoothly
            start_time = time.time()
            while time.time() - start_time < transition_duration:
                elapsed_time = time.time() - start_time
                progress = elapsed_time / transition_duration
                
                # Interpolate the RGB values
                r = int(prev_color[0] + (target_color[0] - prev_color[0]) * progress)
                g = int(prev_color[1] + (target_color[1] - prev_color[1]) * progress)
                b = int(prev_color[2] + (target_color[2] - prev_color[2]) * progress)
                
                # Publish the intermediate color to the MQTT broker
                payload = {"cmd": "setRGB", "payload": f"{r} {g} {b}"}
                mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
                logging.info(f"Sending: {json.dumps(payload)}")
                
                # Wait for a short duration before the next update
                time.sleep(0.1)
            
            # Update the previous color
            prev_color = target_color
        
        # Wait for a short duration before the next update
        time.sleep(0.5)

if __name__ == '__main__':
    # Start the screen color publishing thread
    publish_thread = threading.Thread(target=publish_screen_color)
    publish_thread.daemon = True
    publish_thread.start()
    
    # Keep the main thread alive
    while True:
        pass