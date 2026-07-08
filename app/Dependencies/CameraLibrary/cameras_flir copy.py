"""
camera/flir_camera.py
=====================
FLIR Spinnaker / PySpin backend implementing CameraBase.

Key PySpin patterns used
------------------------
* System.GetInstance() -> cam_list -> cam.Init()
* NodeMap access via CEnumerationPtr / CFloatPtr / CIntegerPtr
* ImageProcessor for Bayer -> BGR8 conversion
* cam.GetNextImage(timeout_ms) with Release() handshake
* Image.GetNDArray() -> numpy array (zero-copy view)

Thermal camera notes (FLIR A-series, Boson, etc.)
--------------------------------------------------
Thermal cameras lock many nodes that visible-light cameras expose
(ExposureAuto, GainAuto, Width, Height are camera-controlled).
All configure() calls are now silent no-ops when a node is read-only —
they demote to DEBUG rather than WARNING so the console stays clean.
The actual sensor dimensions are always read back from the camera after
configure() and used to resize the ring buffer if needed.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import numpy as np

from vs_camera.base import CameraBase, CameraInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node-map helpers  (all silent on read-only nodes)
# ---------------------------------------------------------------------------

def _try_set_enum(nodemap, node_name: str, entry_name: str) -> bool:
    """Set an enumeration node. Returns True on success, False silently if
    the node is absent or read-only (common on thermal / locked cameras)."""
    try:
        import PySpin
        node = PySpin.CEnumerationPtr(nodemap.GetNode(node_name))
        if not PySpin.IsReadable(node) or not PySpin.IsWritable(node):
            logger.debug("Node '%s' not writable - skipped", node_name)
            return False
        entry = node.GetEntryByName(entry_name)
        if not PySpin.IsReadable(entry):
            logger.debug("Entry '%s.%s' not readable - skipped", node_name, entry_name)
            return False
        node.SetIntValue(entry.GetValue())
        logger.debug("Set %s -> %s", node_name, entry_name)
        return True
    except Exception as exc:
        logger.debug("_try_set_enum %s/%s: %s", node_name, entry_name, exc)
        return False


def _try_set_float(nodemap, node_name: str, value: float) -> bool:
    try:
        import PySpin
        node = PySpin.CFloatPtr(nodemap.GetNode(node_name))
        if not PySpin.IsReadable(node) or not PySpin.IsWritable(node):
            logger.debug("Node '%s' not writable - skipped", node_name)
            return False
        clamped = max(node.GetMin(), min(node.GetMax(), value))
        node.SetValue(clamped)
        logger.debug("Set %s -> %.2f (clamped from %.2f)", node_name, clamped, value)
        return True
    except Exception as exc:
        logger.debug("_try_set_float %s: %s", node_name, exc)
        return False


def _try_set_int(nodemap, node_name: str, value: int) -> bool:
    try:
        import PySpin
        node = PySpin.CIntegerPtr(nodemap.GetNode(node_name))
        if not PySpin.IsReadable(node) or not PySpin.IsWritable(node):
            logger.debug("Node '%s' not writable - skipped", node_name)
            return False
        inc = node.GetInc()
        clamped = max(node.GetMin(), min(node.GetMax(), value))
        if inc > 1:
            clamped = (clamped // inc) * inc
        node.SetValue(clamped)
        logger.debug("Set %s -> %d", node_name, clamped)
        return True
    except Exception as exc:
        logger.debug("_try_set_int %s: %s", node_name, exc)
        return False


def _read_int(nodemap, node_name: str, default: int = 0) -> int:
    try:
        import PySpin
        node = PySpin.CIntegerPtr(nodemap.GetNode(node_name))
        if PySpin.IsReadable(node):
            return int(node.GetValue())
    except Exception:
        pass
    return default


def _read_float(nodemap, node_name: str, default: float = 0.0) -> float:
    try:
        import PySpin
        node = PySpin.CFloatPtr(nodemap.GetNode(node_name))
        if PySpin.IsReadable(node):
            return float(node.GetValue())
    except Exception:
        pass
    return default


# ---------------------------------------------------------------------------
# FlirCamera
# ---------------------------------------------------------------------------

class FlirCamera(CameraBase):
    """
    FLIR/Spinnaker camera backend.

    Works with both visible-light (Blackfly, Grasshopper, Oryx …) and
    thermal (A70, A50, Boson …) cameras.  Read-only nodes on thermal
    cameras are silently skipped at DEBUG level.

    Actual sensor dimensions are read back from the camera AFTER configure()
    and stored in self.actual_width / self.actual_height so the orchestrator
    can resize the ring buffer to match.
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._system            = None
        self._cam_list          = None
        self._cam               = None
        self._nodemap           = None
        self._processor         = None
        self._pixel_format_out  = None
        self._is_thermal        = False   # set True when native fmt is Mono14/16
        self._clahe             = None    # cv2 CLAHE instance for thermal display
        self._trigger_mgr       = None    # TriggerManager instance
        self.actual_width:  int = 0
        self.actual_height: int = 0

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def open(self) -> None:
        import PySpin
        logger.info("Opening FLIR camera system ...")
        self._system = PySpin.System.GetInstance()
        ver = self._system.GetLibraryVersion()
        logger.info("Spinnaker SDK %d.%d.%d.%d",
                    ver.major, ver.minor, ver.type, ver.build)

        self._cam_list = self._system.GetCameras()
        count = self._cam_list.GetSize()
        if count == 0:
            self._cam_list.Clear()
            self._system.ReleaseInstance()
            raise RuntimeError("No FLIR cameras detected")
        logger.info("Found %d camera(s)", count)

        serial = self._cfg.camera.get("serial_number", "")
        if serial:
            self._cam = self._cam_list.GetBySerial(str(serial))
            if not self._cam.IsValid():
                raise RuntimeError(f"Camera with serial '{serial}' not found")
            logger.info("Selected camera by serial: %s", serial)
        else:
            self._cam = self._cam_list.GetByIndex(0)
            logger.info("Selected first available camera")

        self._cam.Init()
        self._nodemap = self._cam.GetNodeMap()

        self._processor = PySpin.ImageProcessor()
        self._processor.SetColorProcessing(
            PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR
        )

        # Detect native pixel format so we know if this is a thermal camera
        try:
            native_node = PySpin.CEnumerationPtr(
                self._nodemap.GetNode("PixelFormat")
            )
            native_name = native_node.GetCurrentEntry().GetSymbolic() if PySpin.IsReadable(native_node) else ""
        except Exception:
            native_name = ""

        self._is_thermal = any(x in native_name for x in
                               ("Mono14", "Mono16", "Mono12", "Coord3D"))
        if self._is_thermal:
            logger.info("Thermal camera detected (native format: %s) "
                        "-- normalizing each frame for display", native_name)
            import cv2
            # CLAHE gives local contrast enhancement; better than global normalize
            # for thermal scenes where most pixels cluster in a narrow temp range
            # After percentile stretch the image already has good global contrast.
            # CLAHE with small clip + medium tiles adds local detail without
            # introducing the blocky artefacts that killed the earlier version.
            # tileGridSize=(8,8) on 640x483 = ~80x60px tiles -- good granularity.
            self._clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
            # Always pull raw Mono16 from PySpin; we convert+normalize ourselves
            self._pixel_format_out = PySpin.PixelFormat_Mono16
        else:
            pf = self._cfg.camera.get("pixel_format", "BGR8")
            self._pixel_format_out = getattr(
                PySpin, f"PixelFormat_{pf}", PySpin.PixelFormat_BGR8
            )
        logger.info("Camera opened; native=%s  output=%s  thermal=%s",
                    native_name or "unknown", 
                    "Mono16->BGR8+CLAHE" if self._is_thermal else self._cfg.camera.get("pixel_format", "BGR8"),
                    self._is_thermal)

    def configure(self) -> None:
        import PySpin
        cam_cfg = self._cfg.camera
        nm      = self._nodemap

        # Acquisition mode
        _try_set_enum(nm, "AcquisitionMode",
                      cam_cfg.get("acquisition_mode", "Continuous"))

        # Exposure  (silently skipped on thermal cameras)
        exp_auto = cam_cfg.get("exposure_auto", "Continuous")
        if _try_set_enum(nm, "ExposureAuto", exp_auto):
            if exp_auto == "Off":
                _try_set_float(nm, "ExposureTime",
                               float(cam_cfg.get("exposure_time_us", 10000)))

        # Gain  (silently skipped on thermal cameras)
        gain_auto = cam_cfg.get("gain_auto", "Continuous")
        if _try_set_enum(nm, "GainAuto", gain_auto):
            if gain_auto == "Off":
                _try_set_float(nm, "Gain",
                               float(cam_cfg.get("gain_db", 0.0)))

        # Frame rate
        fps = float(cam_cfg.get("fps_target", 30))
        try:
            node_fre = PySpin.CBooleanPtr(nm.GetNode("AcquisitionFrameRateEnable"))
            if PySpin.IsWritable(node_fre):
                node_fre.SetValue(True)
        except Exception:
            pass
        _try_set_float(nm, "AcquisitionFrameRate", fps)

        # ROI / resolution (silently skipped if camera controls its own size)
        _try_set_int(nm, "Width",  int(cam_cfg.get("width",  1280)))
        _try_set_int(nm, "Height", int(cam_cfg.get("height", 1024)))

        # Stream buffer
        try:
            strnm = self._cam.GetTLStreamNodeMap()
            _try_set_enum(strnm, "StreamBufferHandlingMode", "NewestOnly")
            _try_set_int(strnm, "StreamDefaultBufferCount",
                         int(cam_cfg.get("buffer_count", 10)))
        except Exception as exc:
            logger.debug("Stream buffer config skipped: %s", exc)

        # --- Trigger configuration ---
        from vs_camera.trigger import TriggerManager
        self._trigger_mgr = TriggerManager(cam_cfg, nm, self._cam)
        self._trigger_mgr.configure()

        # --- Read back ACTUAL dimensions after configure ---
        self.actual_width  = _read_int(nm, "Width",  int(cam_cfg.get("width",  1280)))
        self.actual_height = _read_int(nm, "Height", int(cam_cfg.get("height", 1024)))
        logger.info("Camera configured | actual sensor size: %dx%d",
                    self.actual_width, self.actual_height)

    def start_acquisition(self) -> None:
        self._cam.BeginAcquisition()
        self._running = True
        logger.info("Acquisition started")

    def stop_acquisition(self) -> None:
        if self._running:
            try:
                self._cam.EndAcquisition()
            except Exception:
                pass
            self._running = False
        # Reset trigger mode to Off so camera is in clean state for next run
        if self._trigger_mgr:
            self._trigger_mgr.reset()
        logger.info("Acquisition stopped")

    def close(self) -> None:
        """
        Release all PySpin resources in the correct order.

        Order mandated by Spinnaker SDK:
          1. DeInit camera
          2. del camera reference
          3. cam_list.Clear()
          4. del cam_list reference
          5. system.ReleaseInstance()

        Skipping or reordering causes "Can't clear a camera because
        something still holds a reference" (-1004).
        Each step is wrapped individually so a failure in one step
        doesn't prevent cleanup of subsequent resources.
        """
        # Step 1+2: DeInit and delete camera
        if self._cam is not None:
            try:
                if self._cam.IsStreaming():
                    self._cam.EndAcquisition()
            except Exception:
                pass
            try:
                self._cam.DeInit()
            except Exception:
                pass
            try:
                del self._cam
            except Exception:
                pass
            self._cam = None

        # Step 3+4: Clear camera list
        if self._cam_list is not None:
            try:
                self._cam_list.Clear()
            except Exception:
                pass
            try:
                del self._cam_list
            except Exception:
                pass
            self._cam_list = None

        # Step 5: Release system -- only after cam and cam_list are gone
        if self._system is not None:
            try:
                self._system.ReleaseInstance()
            except Exception as exc:
                # Non-fatal: another process or thread may still hold a ref.
                # Log at debug -- this is a clean-shutdown cosmetic issue.
                logger.debug("ReleaseInstance warning (non-fatal): %s", exc)
            self._system = None

        logger.info("FLIR camera closed")

    # -------------------------------------------------------------------------
    # Frame retrieval
    # -------------------------------------------------------------------------

    def get_frame(self, timeout_ms: int = 1000) -> Tuple[Optional[np.ndarray], float]:
        """
        Retrieve next frame.  Returns (bgr_uint8, monotonic_ts) or (None, ts).

        Thermal path (A70 / Mono14 / Mono16 cameras)
        ---------------------------------------------
        Follows the FLIR AcquireAndDisplay.py example: call GetNDArray()
        directly on the raw image without any Convert() call.  The A70
        delivers a 2-D numpy array (h x w) of uint8 or uint16.
        We then:
          1. Ensure the array is 2-D uint8 (normalize uint16 if needed)
          2. Apply CLAHE for local contrast enhancement
          3. Apply false-colour colormap so hot/cold regions are distinct
          4. Return BGR uint8 so the rest of the pipeline is unchanged

        Visible-light path
        ------------------
        Convert() to BGR8 then strip stride padding.
        """
        import PySpin
        import cv2
        ts = time.monotonic()
        try:
            # Software trigger: fire before each GetNextImage call.
            # Hardware trigger: camera waits internally for the GPIO pulse.
            # Continuous: no-op.
            # Note: during warm-up, camera_process calls fire_software_trigger()
            # directly on _trigger_mgr, so this path is only hit in the main loop.
            if self._trigger_mgr and self._trigger_mgr.mode == "software":
                if not self._trigger_mgr.fire_software_trigger():
                    logger.debug("Software trigger fire failed -- will retry next call")
                    return None, time.monotonic()

            img = self._cam.GetNextImage(timeout_ms)
            ts  = time.monotonic()

            if img.IsIncomplete():
                logger.debug("Incomplete image, status=%d", img.GetImageStatus())
                img.Release()
                return None, ts

            if self._is_thermal:
                # Thermal path: follow FLIR AcquireAndDisplay.py example.
                # GetNDArray() on the raw (unconverted) image gives the best data.
                raw = img.GetNDArray().copy()   # copy before Release
                img.Release()

                logger.debug("Thermal GetNDArray: shape=%s dtype=%s min=%s max=%s",
                             raw.shape, raw.dtype,
                             raw.min() if raw.size else '?',
                             raw.max() if raw.size else '?')

                # Ensure 2-D (h, w)
                if raw.ndim == 3:
                    raw = raw[:, :, 0]

                # ── Percentile stretch (matches matplotlib auto-scale) ──────────
                # matplotlib imshow() with no vmin/vmax clips to 2%–98% by
                # default for integer arrays.  Plain min-max on a uint8 image
                # that the camera has already AGC-compressed produces a flat grey
                # because all values sit in a narrow band.
                # Percentile stretch re-maps the actual scene range to full 0-255.
                lo = float(np.percentile(raw, 2))
                hi = float(np.percentile(raw, 98))
                spread = hi - lo if hi > lo else 1.0

                stretched = np.clip(
                    (raw.astype(np.float32) - lo) / spread * 255.0,
                    0, 255
                ).astype(np.uint8)

                # Must be C-contiguous uint8 for CLAHE
                mono8 = np.ascontiguousarray(stretched)

                # CLAHE for local contrast (subtle temp differences in flat regions)
                mono8_eq = self._clahe.apply(mono8)

                colormap_id = self._get_colormap()
                if colormap_id is None:
                    # Greyscale — matches FLIR AcquireAndDisplay cmap='gray'
                    frame = cv2.cvtColor(mono8_eq, cv2.COLOR_GRAY2BGR)
                else:
                    frame = cv2.applyColorMap(mono8_eq, colormap_id)

            else:
                # Visible-light path
                converted = self._processor.Convert(img, self._pixel_format_out)
                img.Release()

                w      = converted.GetWidth()
                h      = converted.GetHeight()
                stride = converted.GetStride()
                data   = converted.GetData()

                bpp = stride // w if w > 0 else 3
                if bpp == 3:
                    frame = (
                        data.reshape(h, stride)[:, :w * 3]
                            .reshape(h, w, 3)
                            .copy()
                    )
                else:
                    mono = data.reshape(h, stride)[:, :w].reshape(h, w).copy()
                    frame = cv2.cvtColor(mono, cv2.COLOR_GRAY2BGR)

            return frame, ts

        except PySpin.SpinnakerException as exc:
            msg = str(exc).lower()
            if "timeout" in msg:
                logger.debug("Frame timeout (%d ms)", timeout_ms)
            elif "not started" in msg or "stream" in msg:
                logger.error("PySpin stream error (acquisition not started?): %s", exc)
            else:
                logger.error("PySpin error: %s", exc)
            return None, ts

    # -------------------------------------------------------------------------
    # Thermal helpers
    # -------------------------------------------------------------------------

    def _get_colormap(self):
        """
        Return cv2 colormap id, or None for greyscale (default).

        Matches FLIR AcquireAndDisplay.py which uses cmap='gray'.
        Set thermal_colormap in config to use a false-colour palette.
        Options: gray | iron | jet | hot | magma | plasma | rainbow | turbo | inferno
        """
        import cv2
        name = self._cfg.camera.get("thermal_colormap", "gray").lower()
        if name == "gray" or name == "grey":
            return None   # caller handles: cvtColor GRAY->BGR, no colormap
        mapping = {
            "iron":    cv2.COLORMAP_HOT,      # closest to classic iron palette
            "hot":     cv2.COLORMAP_HOT,
            "jet":     cv2.COLORMAP_JET,
            "magma":   cv2.COLORMAP_MAGMA,
            "plasma":  cv2.COLORMAP_PLASMA,
            "rainbow": cv2.COLORMAP_RAINBOW,
            "turbo":   cv2.COLORMAP_TURBO,
            "inferno": cv2.COLORMAP_INFERNO,
            "bone":    cv2.COLORMAP_BONE,
        }
        return mapping.get(name, None)   # unknown name -> greyscale

    # -------------------------------------------------------------------------
    # Info
    # -------------------------------------------------------------------------

    def get_info(self) -> CameraInfo:
        import PySpin
        tl = self._cam.GetTLDeviceNodeMap()

        def _str(name: str) -> str:
            try:
                n = PySpin.CStringPtr(tl.GetNode(name))
                return n.GetValue() if PySpin.IsReadable(n) else ""
            except Exception:
                return ""

        nm  = self._nodemap
        w   = _read_int(nm, "Width")
        h   = _read_int(nm, "Height")
        fps = _read_float(nm, "AcquisitionFrameRate")

        return CameraInfo(
            serial_number = _str("DeviceSerialNumber"),
            model_name    = _str("DeviceModelName"),
            firmware      = _str("DeviceFirmwareVersion"),
            width  = w,
            height = h,
            fps    = fps,
        )