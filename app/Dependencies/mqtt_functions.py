from threading import Event, Thread
from mqtt_client import MQTTClient, MQTTConfig
from queue import Empty, Queue

def start_subscribe_thread(
        ip: str, 
        port: int, 
        topic: str, 
        queue: Queue, 
        stop_event: Event
        ) -> Thread:
    
    thread = Thread(
        target=subscribe_listener,
        args=(ip, port, topic, queue, stop_event),
        daemon=True,
    )
    thread.start()
    return thread

def subscribe_listener(
        ip: str, 
        port: int, 
        trigger_topic: str, 
        result_queue: Queue, 
        stop_event: Event
        ):
    
    config = MQTTConfig(host=ip, port=port)
    client = MQTTClient(config)
    client.connect()

    def on_message(topic: str, payload: str) -> None:
        # Handler signature used by mqtt_client.MQTTClient.subscribe
        decoded = payload
        #logging.log(f"Capture request received: {trigger_topic}")
        result_queue.put(decoded)

    client.subscribe(trigger_topic, on_message)
    stop_event.wait()
