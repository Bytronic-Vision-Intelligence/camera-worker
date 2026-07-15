import logging
import os
import time
from sys import getsizeof
from queue import Empty, Queue
from threading import Event, Thread
import numpy as np

from Dependencies import loadConfig
from Dependencies.CameraLibrary import Camera, PylonCamera, LJSCamera
from Dependencies.mqtt_functions import start_subscribe_thread
from Dependencies.data_functions import encode_date_time_to_bytes, encode_image_to_bytes
from Dependencies.archive_functions import archive_image
from Dependencies.archive_functions import save_image_to_file
from mqtt_client import MQTTClient, MQTTConfig

IP = loadConfig.return_config_value("ip")
PORT = loadConfig.return_config_value("port")
TRIGGER_TOPIC = loadConfig.return_config_value("trigger_topic")
IMAGE_TOPIC = loadConfig.return_config_value("image_topic")
TRIGGER_TIME_TOPIC = loadConfig.return_config_value("trigger_time_topic")
MESSAGE = loadConfig.return_config_value("message")

CAMERA_TYPE = loadConfig.return_config_value("camera_type")
TRIGGER_TYPE = loadConfig.return_config_value("trigger_type")

ARCHIVE_DIRECTORY = loadConfig.return_config_value("archive_directory")
SAVE_IMAGES = loadConfig.return_config_value("save_images")
SAVE_DIR = loadConfig.return_config_value("save_dir")
LOGGING_FILE = f'./logs/{CAMERA_TYPE}_worker{time.strftime("%Y%m%d")}.log'
BUFFER_SIZE = loadConfig.return_config_value("buffer_size")
IS_ARCHIVED = loadConfig.return_config_value("is_archived") == "true"

#check if .log file exists
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
    elif camera_type == "ljs":
        camera = LJSCamera()
    else:
        raise ValueError(f"Unsupported camera type: {camera_type}")
    
    camera.connect_to_camera()
    return camera

def start_frame_thread(
        queue: Queue,
        camera: PylonCamera,
        stop_event: Event,
        ) -> Thread:

    thread = Thread(
        target=camera.wait_for_frame,
        args=(queue, stop_event, camera),
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
    stop_event = Event()

    if TRIGGER_TYPE == "external" or CAMERA_TYPE != "opencv":
        is_external_trigger = True
    else:
        is_external_trigger = False

    if not is_external_trigger:
        subscribe_thread = start_subscribe_thread(
            IP,
            PORT,
            TRIGGER_TOPIC,
            event_queue,
            stop_event,
        )
    else:
        subscribe_thread = start_frame_thread(
            event_queue,
            camera,
            stop_event,
        )
    
    time.sleep(0.1)
    try:
        while True:
            
            try:
                msg = event_queue.get(timeout = 1.0)
                start_time = time.time()
            except Empty:
                continue

            if msg is None:
                logging.info("Received invalid trigger payload; ignoring.")
                continue

            date_time = encode_date_time_to_bytes()

            logging.info("Capturing image...")
            if not is_external_trigger:
                image = camera.capture_image()
            else:
                if not isinstance(msg, np.ndarray):
                    logging.error("Expected image frame from queue, got %s", type(msg))
                    continue
                image = msg

            if image is None:
                logging.error("No image available to encode.")
                continue
            
            if IS_ARCHIVED:
                ms = int((start_time % 1) * 1000)
                archive_name = f"{CAMERA_TYPE}_{time.strftime('%Y%m%d_%H%M%S')}_{ms:03d}"
                archive_image(image, ARCHIVE_DIRECTORY, archive_name)

            image_bytes = encode_image_to_bytes(image)

            if SAVE_IMAGES:
                safe_timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(start_time))
                Thread(
                    target=save_image_to_file,
                    args=(image, SAVE_DIR, safe_timestamp),
                    daemon=True,
                ).start()
            packet = image_bytes + date_time

            logging.info(f"Publishing image... of size {getsizeof(image_bytes)}")

            if image is not None:
                try:
                    client.publish(IMAGE_TOPIC, packet)
                except Exception as e:
                    logging.error(f"Error publishing image: {e}")
            else:
                logging.info("Failed to capture image.")

            print(f"imaging took a total of {time.time()-start_time}")
            logging.info("Image published. Waiting for next capture request...")

    except KeyboardInterrupt:
        logging.info("Shutting down and exiting.")

    finally:
        stop_event.set()
        if subscribe_thread is not None and subscribe_thread.is_alive():
            subscribe_thread.join(timeout=2)

        camera.disconnect_camera(camera.cam)

if __name__ == "__main__":
    main()
