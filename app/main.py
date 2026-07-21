import logging
import os
import time
from sys import getsizeof
from queue import Empty, Queue
from threading import Event, Thread
import numpy as np
from pathlib import Path

from Dependencies import loadConfig
from Dependencies.CameraLibrary import Camera, PylonCamera, LJSCamera, FlirCamera
from Dependencies.CameraLibrary.hardware_trigger import CameraLossError
from Dependencies.mqtt_functions import start_subscribe_thread
from Dependencies.data_functions import encode_date_time_to_bytes, encode_image_to_bytes
from Dependencies.archive_functions import archive_image
from mqtt_client import MQTTClient, MQTTConfig

IP = loadConfig.return_config_value("ip")
PORT = loadConfig.return_config_value("port")
TRIGGER_TOPIC = loadConfig.return_config_value("trigger_topic")
TRIGGER_TIME_TOPIC = loadConfig.return_config_value("trigger_time_topic")
MESSAGE = loadConfig.return_config_value("message")

CAMERA_TYPE = loadConfig.return_config_value("camera.camera_type")
try:
    CAMERA_ID = loadConfig.return_config_value("camera.serial_number")
except KeyError:
    CAMERA_ID = None
if CAMERA_ID is not None:
    CAMERA_ID = str(CAMERA_ID).strip() or None
IMAGE_TOPIC = loadConfig.return_config_value("image_topic")
if CAMERA_ID:
    IMAGE_TOPIC = IMAGE_TOPIC.replace("/camera/", f"/camera_{CAMERA_ID}/")
TRIGGER_TYPE = loadConfig.return_config_value("trigger.trigger_type")

ARCHIVE_DIRECTORY = Path(loadConfig.return_config_value("archiving.archive_directory"))
LOGGING_FILE = f'./logs/{CAMERA_TYPE}_worker{time.strftime("%Y%m%d")}.log'
BUFFER_SIZE = loadConfig.get_section("camera_settings").get("buffer_size")
IS_ARCHIVED = str(loadConfig.return_config_value("archiving.is_archived")).lower() == "true"
ARCHIVE_PARAMS = loadConfig.return_config_value("archiving.archive_parameters")


#check if .log file exists
os.makedirs(os.path.dirname(LOGGING_FILE), exist_ok=True)
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
    elif camera_type == "flir":
        camera = FlirCamera()
    elif camera_type == "ljs":
        camera = LJSCamera()
    else:
        raise ValueError(f"Unsupported camera type: {camera_type}")
    
    camera.connect_to_camera()
    return camera

def start_frame_thread(
        queue: Queue,
        camera: Camera,
        stop_event: Event,
        ) -> Thread:
    # Do not pass the wrapper as `camera=` — wait_for_frame expects the
    # vendor handle (self.cam). Omitting it lets Pylon/FLIR use self.cam.
    thread = Thread(
        target=camera.wait_for_frame,
        args=(queue, stop_event),
        daemon=True,
    )
    thread.start()
    return thread

def main() -> int:
    camera = set_camera_class(CAMERA_TYPE)

    config = MQTTConfig(host=IP, port=PORT)
    client = MQTTClient(config)
    client.connect()

    event_queue = Queue()
    stop_event = Event()
    exit_code = 0

    # opencv defaults to MQTT (internal) unless trigger_type is external.
    # ljs supports both: internal = MQTT + LJS8IF_Trigger; external = hardware TRG.
    # other backends (pylon/flir) stay on the frame-thread path.
    _trigger = str(TRIGGER_TYPE).strip().lower()
    if CAMERA_TYPE == "ljs":
        is_external_trigger = _trigger in ("external", "hardware")
    elif CAMERA_TYPE == "opencv":
        is_external_trigger = _trigger == "external"
    else:
        is_external_trigger = True

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

            if isinstance(msg, CameraLossError):
                logging.critical("CAMERA LOSS: %s", msg)
                print(f"CAMERA LOSS: {msg}", flush=True)
                exit_code = 1
                break

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
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                archive_filename = f"cam{CAMERA_ID or '0'}_{CAMERA_TYPE}_{timestamp}"
                archive_image(image, ARCHIVE_DIRECTORY, archive_filename, ARCHIVE_PARAMS, CAMERA_ID)

            image_bytes = encode_image_to_bytes(image)
            packet = image_bytes + date_time

            logging.info(f"Publishing image... of size {getsizeof(image_bytes)}")

            if image is not None:
                try:
                    client.publish(IMAGE_TOPIC, packet)
                except Exception as e:
                    logging.error("Error publishing image: %s", e)
            else:
                logging.info("Failed to capture image.")

            print(f"imaging took a total of {time.time()-start_time}")
            logging.info("Image published. Waiting for next capture request...")

    except KeyboardInterrupt:
        logging.info("Shutting down and exiting.")

    finally:
        stop_event.set()
        # End acquisition first so a blocked GetNextImage unblocks and the
        # frame thread can exit before we DeInit (avoids leaving the camera locked).
        try:
            if hasattr(camera, "stop_acquisition"):
                camera.stop_acquisition()
        except Exception:
            logging.debug("stop_acquisition during shutdown failed", exc_info=True)

        if subscribe_thread is not None and subscribe_thread.is_alive():
            subscribe_thread.join(timeout=2)

        camera.disconnect_camera(camera.cam)

    return exit_code

if __name__ == "__main__":
    raise SystemExit(main())