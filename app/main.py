from dependencies import loadConfig
from dependencies.camera_library.cameras_pylon import *
from dependencies.mqtt_functions import *
from dependencies.data_functions import *

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
BUFFER_SIZE = loadConfig.return_config_value("buffer_size")

#check if .log file exists
if not os.path.exists(LOGGING_FILE):
    file = open(LOGGING_FILE,"w")
    file.write("")
    file.close()

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

def main():
    camera = set_camera_class(CAMERA_TYPE)

    config = MQTTConfig(host=IP, port=PORT)
    client = MQTTClient(config)
    client.connect()

    event_queue = Queue()
    stop_event = Event()
    subscribe_thread = start_subscribe_thread(
        IP, 
        PORT, 
        TRIGGER_TOPIC, 
        event_queue, 
        stop_event
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
            image = camera.capture_image()

            image_bytes = encode_image_to_bytes(image)
            packet = image_bytes+date_time

            logging.info(f"Publishing image... of size {getsizeof(image_bytes)}")

            if image is not None:
                try:
                    client.publish(IMAGE_TOPIC, packet)
                except Exception as e:
                    logging.log(f"Error publishing image: {e}")
            else:
                logging.info("Failed to capture image.")

            print(f"imaging took a total of {time.time()-start_time}")
            logging.info("Image published. Waiting for next capture request...")

    except KeyboardInterrupt:
        logging.info("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        if subscribe_thread.is_alive():
            subscribe_thread.join(timeout=2)

if __name__ == "__main__":
    main()