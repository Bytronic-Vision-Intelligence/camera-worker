from Dependencies.CameraLibrary.cameras import Camera
from Dependencies.CameraLibrary.hardware_trigger import (
    HardwareTriggerConfig,
    wait_for_gpio_edge_frames,
)
from Dependencies.CameraLibrary.spinnaker_trigger import SpinnakerHardwareTrigger
import PySpin
import logging
import time
from queue import Queue
from threading import Event

import numpy as np


logger = logging.getLogger(__name__)


class FlirCamera(Camera):
    def __init__(self):
        super().__init__()
        self.cam = None
        self.system = None
        self.cam_list = None
        self.processor = None
        self.pixel_format_out = None
        self._trigger: SpinnakerHardwareTrigger | None = None

    def _find_camera(self):
        self.cam = None

        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        count = self.cam_list.GetSize()
        if count == 0:
            self.cam_list.Clear()
            self.system.ReleaseInstance()
            self.cam_list = None
            self.system = None
            raise RuntimeError("No FLIR cameras detected")

        self.cam = self.cam_list.GetByIndex(0)
        if self.cam is None or not self.cam.IsValid():
            raise RuntimeError("Failed to get a valid FLIR camera handle")
        logger.info("FLIR camera found")
        return self.cam

    def connect_to_camera(self, timeout_ms: int = 5000):
        timeout_s = timeout_ms / 1000.0
        start = time.time()

        self.cam = self._find_camera()

        try:
            self.cam.Init()
            nodemap = self.cam.GetNodeMap()

            try:
                model = PySpin.CStringPtr(nodemap.GetNode("DeviceModelName"))
                if PySpin.IsAvailable(model) and PySpin.IsReadable(model):
                    logger.info("Camera model: %s", model.GetValue())
            except Exception:
                pass

            acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
            if PySpin.IsAvailable(acquisition_mode) and PySpin.IsWritable(acquisition_mode):
                continuous = PySpin.CEnumEntryPtr(acquisition_mode.GetEntryByName("Continuous"))
                if PySpin.IsAvailable(continuous) and PySpin.IsReadable(continuous):
                    acquisition_mode.SetIntValue(continuous.GetValue())

            trigger_cfg = HardwareTriggerConfig.from_app_config()
            self._trigger = SpinnakerHardwareTrigger(self.cam, trigger_cfg)
            self._trigger.configure(nodemap)

            self.processor = PySpin.ImageProcessor()
            self.processor.SetColorProcessing(
                PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR
            )
            self.pixel_format_out = PySpin.PixelFormat_BGR8

            self.cam.BeginAcquisition()

            while True:
                if self.cam.IsStreaming():
                    break
                if (time.time() - start) > timeout_s:
                    raise TimeoutError("Timeout while waiting for FLIR acquisition to start.")
                time.sleep(0.05)

            if self._trigger.uses_gpio_poll:
                self._trigger.sample_idle_line()

            logger.info("FLIR camera connected successfully")
            return self.cam
        except Exception as e:
            self.disconnect_camera(self.cam)
            raise RuntimeError("Failed to connect FLIR camera.") from e

    def stop_acquisition(self) -> None:
        if self.cam is None:
            return
        try:
            if self.cam.IsStreaming():
                self.cam.EndAcquisition()
                logger.info("Acquisition stopped")
        except Exception:
            logger.debug("stop_acquisition failed", exc_info=True)

    def capture_image(self, camera=None, timeout_ms: int = 5000, is_converted: bool = True) -> np.ndarray:
        if camera is None:
            camera = self.cam
        if camera is None:
            raise ValueError("camera is None")

        try:
            grab_result = camera.GetNextImage(timeout_ms)
        except PySpin.SpinnakerException as e:
            native_hw = (
                self._trigger is not None
                and self._trigger.mode == "native"
                and "timeout" in str(e).lower()
            )
            if native_hw:
                raise TimeoutError("No hardware trigger within grab timeout") from e
            logger.error("GetNextImage raised an exception", exc_info=True)
            raise RuntimeError("Failed to grab image from FLIR camera") from e
        except Exception as e:
            logger.error("GetNextImage raised an exception", exc_info=True)
            raise RuntimeError("Failed to grab image from FLIR camera") from e

        try:
            if grab_result.IsIncomplete():
                raise RuntimeError(f"Incomplete frame, status={grab_result.GetImageStatus()}")

            if is_converted:
                converted = self.processor.Convert(grab_result, self.pixel_format_out)
                img = converted.GetNDArray()
            else:
                img = grab_result.GetNDArray()

            logging.info("Captured image shape: %s", getattr(img, "shape", None))
            return np.asarray(img)
        finally:
            try:
                grab_result.Release()
            except Exception:
                logger.error("Failed to release FLIR image buffer", exc_info=True)

    def wait_for_frame(
        self,
        queue: Queue,
        stop_event: Event,
        camera=None,
        timeout_ms: int = 5000,
        is_converted: bool = True,
    ):
        if camera is None:
            camera = self.cam
        if camera is None:
            raise ValueError("camera is None")

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

        while not stop_event.is_set():
            try:
                frame = self.capture_image(
                    camera=camera,
                    timeout_ms=timeout_ms,
                    is_converted=is_converted,
                )
                queue.put(frame)
            except TimeoutError:
                continue
            except Exception as e:
                if stop_event.is_set():
                    break
                logger.error("Failed to retrieve FLIR frame: %s", e, exc_info=True)

    def disconnect_camera(self, camera=None) -> None:
        if camera is None:
            camera = self.cam

        if camera is not None:
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
            except Exception:
                logger.debug("EndAcquisition failed during shutdown", exc_info=True)
            try:
                if self._trigger is not None:
                    self._trigger.reset(camera.GetNodeMap())
            except Exception:
                logger.debug("Failed resetting hardware trigger during shutdown", exc_info=True)
            try:
                if camera.IsInitialized():
                    camera.DeInit()
            except Exception:
                logger.debug("DeInit failed during shutdown", exc_info=True)

        self.cam = None
        self._trigger = None
        try:
            del camera
        except Exception:
            pass

        if self.cam_list is not None:
            try:
                self.cam_list.Clear()
            except Exception:
                logger.debug("Failed clearing FLIR camera list", exc_info=True)
            try:
                del self.cam_list
            except Exception:
                pass
            self.cam_list = None

        if self.system is not None:
            try:
                self.system.ReleaseInstance()
            except Exception:
                logger.debug("Failed releasing FLIR system instance", exc_info=True)
            self.system = None

        logger.info("FLIR camera disconnected")
