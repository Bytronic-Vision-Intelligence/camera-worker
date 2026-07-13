from pypylon import pylon
from Dependencies.CameraLibrary.cameras import Camera
from Dependencies.CameraLibrary.hardware_trigger import (
    HardwareTriggerConfig,
    wait_for_gpio_edge_frames,
)
from Dependencies.CameraLibrary.pylon_trigger import PylonHardwareTrigger
from queue import Queue
from threading import Event
import logging
import time
import numpy as np


class PylonCamera(Camera):
    def __init__(self):
        super().__init__()
        self.cam = None
        self._trigger: PylonHardwareTrigger | None = None

    def _find_camera(self) -> pylon.InstantCamera:
        self.cam = None

        try:
            device = pylon.TlFactory.GetInstance().CreateFirstDevice()
            cam = pylon.InstantCamera(device)
            camera_info_message = f"Camera found: {cam.GetDeviceInfo().GetModelName()}"
            logging.info(camera_info_message)
            self.cam = cam
            return cam
        except Exception as e:
            raise RuntimeError("Error finding camera: " + str(e)) from e

    def connect_to_camera(self, timeout_ms: int = 5000) -> pylon.InstantCamera:
        timeout_s = timeout_ms / 1000.0
        start = time.time()

        self.cam = self._find_camera()

        try:
            if not self.cam.IsOpen():
                try:
                    self.cam.Open()
                except Exception:
                    logging.error("Initial Open() failed; entering wait loop")

            while not self.cam.IsOpen():
                if time.time() - start > timeout_s:
                    raise TimeoutError("Timeout while waiting for camera to open.")
                time.sleep(0.1)

            trigger_cfg = HardwareTriggerConfig.from_app_config()
            self._trigger = PylonHardwareTrigger(self.cam, trigger_cfg)
            self._trigger.configure()
            if self._trigger.uses_gpio_poll:
                self._trigger.sample_idle_line()

            logging.info("Camera connected successfully")
            return self.cam

        except Exception as e:
            if self.cam is not None and self.cam.IsOpen():
                self.cam.Close()
            raise RuntimeError("Failed to open camera within timeout.") from e

    def capture_image(
            self,
            camera: pylon.InstantCamera = None,
            timeout_ms: int = 5000,
            is_converted=True
            ) -> np.ndarray:

        if camera is None:
            camera = self.cam
        if camera is None:
            raise ValueError("camera is None")
        if not camera.IsOpen():
            raise RuntimeError("camera is not open")

        try:
            grab_result = camera.GrabOne(timeout_ms)
        except Exception as e:
            logging.error("GrabOne raised an exception")
            raise RuntimeError("Failed to grab image") from e

        try:
            if not grab_result.GrabSucceeded():
                error_code = getattr(grab_result, "ErrorCode", None)
                error_desc = getattr(grab_result, "ErrorDescription", None)
                error_info = f"Grab failed with error code {error_code}, description: {error_desc}"
                raise RuntimeError(error_info)

            img = grab_result.Array  # type: ignore

            if is_converted:
                converter = pylon.ImageFormatConverter()
                converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                converted = converter.Convert(grab_result)
                img = converted.Array

            logging.info("Captured image shape: %s", getattr(img, "shape", None))
            return np.asarray(img)

        finally:
            try:
                grab_result.Release()
            except Exception:
                logging.error("Failed to release grab_result", exc_info=True)

    def wait_for_frame(
            self,
            queue: Queue,
            stop_event: Event,
            camera: pylon.InstantCamera = None,
            timeout_ms: int = 5000,
            is_converted: bool = True,
            ):
        if camera is None:
            camera = self.cam
        if camera is None:
            raise ValueError("camera is None")
        if not camera.IsOpen():
            raise RuntimeError("camera is not open")

        if self._trigger is not None and self._trigger.uses_gpio_poll:
            wait_for_gpio_edge_frames(
                read_line=self._trigger.read_line,
                capture_frame=lambda: self.capture_image(
                    camera=camera,
                    timeout_ms=timeout_ms,
                    is_converted=is_converted,
                ),
                queue=queue,
                stop_event=stop_event,
                config=self._trigger.config,
                initial_status=self._trigger.last_line_status,
            )
            return

        if not camera.IsGrabbing():
            camera.StartGrabbing(pylon.GrabStrategy_OneByOne)

        try:
            while not stop_event.is_set():
                try:
                    grab_result = camera.RetrieveResult(
                        timeout_ms, pylon.TimeoutHandling_ThrowException
                    )
                except Exception as e:
                    if stop_event.is_set():
                        break
                    logging.error("Failed to retrieve frame: %s", e, exc_info=True)
                    continue

                try:
                    if not grab_result.GrabSucceeded():
                        error_code = getattr(grab_result, "ErrorCode", None)
                        error_desc = getattr(grab_result, "ErrorDescription", None)
                        logging.error(
                            "Grab failed with error code %s, description: %s",
                            error_code,
                            error_desc,
                        )
                        continue

                    img = grab_result.Array
                    if is_converted:
                        converter = pylon.ImageFormatConverter()
                        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                        converted = converter.Convert(grab_result)
                        img = converted.Array

                    queue.put(np.asarray(img))
                finally:
                    try:
                        grab_result.Release()
                    except Exception:
                        logging.error("Failed to release grab_result", exc_info=True)
        finally:
            if camera.IsGrabbing():
                camera.StopGrabbing()

    def disconnect_camera(self, camera) -> None:
        if self._trigger is not None:
            try:
                self._trigger.reset()
            except Exception:
                logging.debug("Failed resetting Pylon hardware trigger", exc_info=True)
            self._trigger = None
        if camera is not None and camera.IsOpen():
            camera.Close()
