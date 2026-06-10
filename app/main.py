import cv2
from Dependencies import loadConfig
import time
import threading
from queue import Empty, Queue
import numpy as np

from mqtt_client import MQTTClient, MQTTConfig
from Dependencies.CameraLibrary.Cameras import Camera
from Dependencies.CameraLibrary.PylonCamera import PylonCamera
import logging
import os
from sys import getsizeof
#
IP = loadConfig.return_config_value("ip")
PORT = loadConfig.return_config_value("port")
TRIGGER_TOPIC = loadConfig.return_config_value("trigger_topic")
IMAGE_TOPIC = loadConfig.return_config_value("image_topic")
TRIGGER_TIME_TOPIC = loadConfig.return_config_value("trigger_time_topic")
MESSAGE = loadConfig.return_config_value("message")
CAMERA_TYPE = loadConfig.return_config_value("camera_type")
LOGGING_FILE = f'./logs/{CAMERA_TYPE}_worker{time.strftime("%Y%m%d")}.log'
#check if dio.log exists

if not os.path.exists(LOGGING_FILE):
    with open(LOGGING_FILE, "w") as file:
        file.write("")

logging.basicConfig(
    filename=LOGGING_FILE,
    level=logging.INFO,
    format='%(asctime)s - [PID %(process)d] - %(levelname)s - %(message)s',
    force=True,  # Force configuration even if the logger was previously configured
    filemode='a'  # Append mode instead of overwrite
)

def set_camera_class(camera_type: str):
    if not camera_type:
        raise ValueError("Camera type cannot be empty.")
    
    if camera_type == "opencv":
        camera = Camera()
    elif camera_type == "pylon":
        camera = PylonCamera()
    else:
        raise ValueError(f"Unsupported camera type: {camera_type}")
    
    camera.connect_to_camera()
    return camera

def subscribe_listener(ip: str, port: int, trigger_topic: str, result_queue: Queue, stop_event: threading.Event):
    config = MQTTConfig(host=IP, port=PORT)
    client = MQTTClient(config)
    client.connect()

    def on_message(topic: str, payload: str) -> None:
        # Handler signature used by mqtt_client.MQTTClient.subscribe
        try:
            decoded = payload
        except Exception:
            decoded = payload
        #logging.log(f"Capture request received: {trigger_topic}")
        result_queue.put(decoded)

    client.subscribe(trigger_topic, on_message)

def encode_image_to_bytes(image: np.ndarray) -> bytes:
    # Encode the image as JPEG and return the bytes
    if image is None:
        raise ValueError("Input image is None.")
    if not isinstance(image, np.ndarray):
        raise ValueError("Input image must be a numpy array.")
    
    success, encoded_image = cv2.imencode('.jpg', image)

    if not success:
        raise RuntimeError("Failed to encode image to JPEG format.")
    return encoded_image.tobytes()

def encode_date_time_to_bytes() -> bytes:
    date_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    return date_time.encode("utf-8")

def start_subscribe_thread(ip: str, port: int, topic: str, queue: Queue, stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(
        target=subscribe_listener,
        args=(ip, port, topic, queue, stop_event),
        daemon=True,
    )
    thread.start()
    return thread

def main():
    camera = set_camera_class(CAMERA_TYPE)

    config = MQTTConfig(host=IP, port=PORT)
    client = MQTTClient(config)
    client.connect()

    event_queue = Queue()
    stop_event = threading.Event()
    subscribe_thread = start_subscribe_thread(IP, PORT, TRIGGER_TOPIC, event_queue, stop_event)

    try:
        while True:
            time.sleep(0.1)

            try:
                msg = event_queue.get_nowait()
            except Empty:
                continue

            if msg is None:
                logging.info("Received invalid trigger payload; ignoring.")
                continue

            date_time = encode_date_time_to_bytes()

            logging.info("Capturing image...")
            image = camera.capture_image()
            image=cv2.resize(image, (1920,1080))
            image_bytes = encode_image_to_bytes(image)
            packet = image_bytes+date_time
            print(packet[getsizeof(packet)-52:])

            logging.info("Publishing image...")
            if image is not None:
                try:
                    client.publish(IMAGE_TOPIC, packet)
                except Exception as e:
                    logging.exception(f"Error publishing image: {e}")
            else:
                logging.info("Failed to capture image.")

            logging.info("Image published. Waiting for next capture request...")

    except KeyboardInterrupt:
        logging.info("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        if subscribe_thread.is_alive():
            subscribe_thread.join(timeout=2)

if __name__ == "__main__":
    main()