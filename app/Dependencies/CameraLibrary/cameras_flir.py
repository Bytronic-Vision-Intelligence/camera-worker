from Dependencies.CameraLibrary.cameras import Camera
import PySpin
import logging
import time
from queue import Queue
from threading import Event

import cv2
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

            acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
            if PySpin.IsWritable(acquisition_mode):
                continuous = acquisition_mode.GetEntryByName("Continuous")
                if PySpin.IsReadable(continuous):
                    acquisition_mode.SetIntValue(continuous.GetValue())

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

            logger.info("FLIR camera connected successfully")
            return self.cam
        except Exception as e:
            self.disconnect_camera(self.cam)
            raise RuntimeError("Failed to connect FLIR camera.") from e

    def capture_image(self, camera=None, timeout_ms: int = 5000, is_converted: bool = True) -> np.ndarray:
        import PySpin

        if camera is None:
            camera = self.cam
        if camera is None:
            raise ValueError("camera is None")

        try:
            grab_result = camera.GetNextImage(timeout_ms)
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

        while not stop_event.is_set():
            try:
                frame = self.capture_image(
                    camera=camera,
                    timeout_ms=timeout_ms,
                    is_converted=is_converted,
                )
                queue.put(frame)
            except Exception as e:
                logger.error("Failed to retrieve FLIR frame: %s", e, exc_info=True)

    def disconnect_camera(self, camera) -> None:
        if camera is not None:
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
            except Exception:
                logger.debug("EndAcquisition failed during shutdown", exc_info=True)
            try:
                camera.DeInit()
            except Exception:
                logger.debug("DeInit failed during shutdown", exc_info=True)
            self.cam = None

        if self.cam_list is not None:
            try:
                self.cam_list.Clear()
            except Exception:
                logger.debug("Failed clearing FLIR camera list", exc_info=True)
            self.cam_list = None

        if self.system is not None:
            try:
                self.system.ReleaseInstance()
            except Exception:
                logger.debug("Failed releasing FLIR system instance", exc_info=True)
            self.system = None