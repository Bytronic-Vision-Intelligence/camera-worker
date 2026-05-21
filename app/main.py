from MQTT_Objects.Classes.mqtt_CameraClass import CameraClass
import time
import asyncio
import threading

IP = "localhost"
PORT = 1883
TRIGGER_TOPIC = "trigger/status"
PUBLISH_TOPIC = "camera/image"

def start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

async def listen_for_capture(camera: CameraClass) -> bool:
    # This function waits for a capture request to be sent from the broker and then triggers the camera to capture an image.
    # it returns a boolean value indicating whether the capture was received or not.

    try:
        msg = await camera.ListenForMessage()
        
    except Exception as e:
        print(f"Error occurred while listening for message: {e}")
        return False
    
    if msg:
        print("Capture request received." + str(msg))
        return True

    return False

def main():
    camera = CameraClass()
    camera.ConnectToCamera()
    camera.ConnectToServer(IP, PORT)
    camera.SubscribeToTopic(TRIGGER_TOPIC)

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_async_loop, args=(loop,), daemon=True)
    t.start()

    #asyncio.run_coroutine_threadsafe(listen_for_capture(camera), loop)

    time.sleep(0.1)

    while True:
        time.sleep(1)
        if asyncio.run_coroutine_threadsafe(listen_for_capture(camera), loop).result():
            print("Capturing image...")
            image = camera.GetImageFromCamera()

            if image is not None:
                camera.PublishMessage(PUBLISH_TOPIC, image)
            else:
                print("Failed to capture image.")

if __name__ == "__main__":
    main()