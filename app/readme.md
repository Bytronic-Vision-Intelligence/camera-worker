# app

This folder contains the main application logic for the Example Camera Worker.

## Purpose

The `app` package launches the MQTT-based camera worker and manages the capture workflow.

## Main entrypoint

- `app/main.py` is the primary script.
- It loads configuration values from `app/Dependencies/config.yaml`.
- It initializes the requested camera implementation and connects to the MQTT broker.
- It listens for trigger messages and publishes captured images to the configured image topic.

## Configuration

The app uses `app/Dependencies/loadConfig.py` to read YAML values from `app/Dependencies/config.yaml`.

Required config keys:

- `ip`
- `port`
- `trigger_topic`
- `image_topic`
- `camera_type`

Optional keys:

- `message`

## Camera types

- `opencv`: uses `cv2.VideoCapture(0)` to capture from the local webcam.
- `pylon`: imports `MQTT_Objects.Classes.mqtt_Camera_PylonClass.PylonClass` and expects that package to be installed and available.

## Running

```powershell
python app/main.py
```

## Notes

- The worker uses a background asyncio event loop to listen for capture requests.
- Captured images are resized to `6400x4800` before publishing.
- If the configured `camera_type` is unsupported, the app raises a `ValueError`.
