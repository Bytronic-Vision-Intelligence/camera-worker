import cv2
from Dependencies import loadConfig
import time
import threading
from queue import Empty, Queue
from MQTT_Objects.Classes.mqttClass import mqttClass
from MQTT_Objects.Classes.mqtt_Camera_PylonClass import PylonClass
from MQTT_Objects.Classes.mqtt_CameraClass import CameraClass
#
IP = loadConfig.return_config_value("ip")
PORT = loadConfig.return_config_value("port")
TRIGGER_TOPIC = loadConfig.return_config_value("trigger_topic")
IMAGE_TOPIC = loadConfig.return_config_value("image_topic")
TRIGGER_TIME_TOPIC = loadConfig.return_config_value("trigger_time_topic")
MESSAGE = loadConfig.return_config_value("message")
CAMERA_TYPE = loadConfig.return_config_value("camera_type")

def set_camera_class(camera_type: str):
    if not camera_type:
        raise ValueError("Camera type cannot be empty.")
    
    if camera_type == "opencv":
        camera = CameraClass()
        camera.ConnectToCamera()
        return camera

    if camera_type == "pylon":
        camera = PylonClass()
        camera.ConnectToCamera()
        return camera
    else:
        raise ValueError(f"Unsupported camera type: {camera_type}")
    
def capture_image(camera):
    if isinstance(camera, cv2.VideoCapture):
        ret, frame = camera.read()
        if not ret:
            raise Exception("Failed to capture image from OpenCV camera.")
        return frame
    elif isinstance(camera, PylonClass):
        return camera.GetImageFromCamera()
    else:
        raise ValueError("Unsupported camera object type.")

def subscribe_listener(ip: str, port: int, trigger_topic: str, result_queue: Queue, stop_event: threading.Event):
    mqtt_listener = mqttClass()
    mqtt_listener.ConnectToServer(ip, port)
    mqtt_listener.SubscribeToTopic(trigger_topic)

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
        except Exception:
            payload = msg.payload
        print("Capture request received:", msg.topic)
        result_queue.put(payload)

    mqtt_listener.client.on_message = on_message
    mqtt_listener.client.loop_start()

    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        mqtt_listener.client.loop_stop()
        try:
            mqtt_listener.client.disconnect()
        except Exception:
            pass


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
    camera.ConnectToServer(IP, PORT)

    mqtt = mqttClass()
    mqtt.ConnectToServer(IP, PORT)

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
                print("Received invalid trigger payload; ignoring.")
                continue

            date_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            mqtt.PublishMessage(TRIGGER_TIME_TOPIC, date_time.encode("utf-8"))
            print("Capturing image...")
            image = camera.GetImageFromCamera()
            image = cv2.resize(image, (1920, 1080))

            print("Publishing image...")
            if image is not None:
                try:
                    camera.PublishMessage(IMAGE_TOPIC, image)
                except Exception as e:
                    print(f"Error publishing image: {e}")
            else:
                print("Failed to capture image.")

            print("Image published. Waiting for next capture request...")
    except KeyboardInterrupt:
        print("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        if subscribe_thread.is_alive():
            subscribe_thread.join(timeout=2)

if __name__ == "__main__":
    main()