"""Basler / pypylon hardware-trigger configuration."""

from __future__ import annotations

import logging
from typing import Optional

from Dependencies.CameraLibrary.hardware_trigger import HardwareTriggerConfig

logger = logging.getLogger(__name__)


def _set_enum(camera, feature_name: str, value: str) -> bool:
    """Set a GenICam enum feature via pypylon node map / InstantCamera attrs."""
    try:
        node = getattr(camera, feature_name, None)
        if node is None or not node.IsWritable():
            logger.warning("Pylon feature %s is not writable", feature_name)
            return False
        node.SetValue(value)
        return True
    except Exception as e:
        logger.warning("Failed to set Pylon %s=%s: %s", feature_name, value, e)
        return False


class PylonHardwareTrigger:
    """Configure and operate external trigger on a Basler/pylon camera.

    Modes match ``SpinnakerHardwareTrigger``: ``native``, ``gpio_poll``, ``off``.
    """

    def __init__(self, cam, config: Optional[HardwareTriggerConfig] = None):
        self._cam = cam
        self.config = config or HardwareTriggerConfig.from_app_config()
        self.mode = "off"
        self._last_line_status: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    @property
    def uses_gpio_poll(self) -> bool:
        return self.mode == "gpio_poll"

    def configure(self) -> None:
        if not self.config.enabled:
            self.mode = "off"
            _set_enum(self._cam, "TriggerMode", "Off")
            return

        # Prefer native TriggerMode when the camera exposes it.
        try:
            has_trigger = (
                hasattr(self._cam, "TriggerMode")
                and self._cam.TriggerMode.IsWritable()
            )
        except Exception:
            has_trigger = False

        if has_trigger:
            self._configure_native()
        else:
            logger.info(
                "Pylon TriggerMode unavailable — using LineStatus edge detect"
            )
            self._configure_gpio_poll()

    def reset(self) -> None:
        if self.mode == "native":
            _set_enum(self._cam, "TriggerMode", "Off")
        self.mode = "off"

    def read_line(self) -> bool:
        cam = self._cam
        if not _set_enum(cam, "LineSelector", self.config.source):
            raise RuntimeError(f"Failed to select GPIO line {self.config.source}")
        try:
            if hasattr(cam, "LineMode") and cam.LineMode.IsWritable():
                cam.LineMode.SetValue("Input")
        except Exception:
            pass
        if not hasattr(cam, "LineStatus") or not cam.LineStatus.IsReadable():
            raise RuntimeError("LineStatus is not readable on this camera")
        return bool(cam.LineStatus.GetValue())

    def sample_idle_line(self) -> Optional[bool]:
        try:
            self._last_line_status = self.read_line()
            logger.info("GPIO idle LineStatus=%s", self._last_line_status)
            return self._last_line_status
        except Exception:
            logger.debug("Could not read initial LineStatus", exc_info=True)
            return self._last_line_status

    @property
    def last_line_status(self) -> Optional[bool]:
        return self._last_line_status

    def _configure_native(self) -> None:
        cam = self._cam
        source = self.config.source
        activation = self.config.activation

        _set_enum(cam, "TriggerMode", "Off")
        _set_enum(cam, "TriggerSelector", "FrameStart")
        if not _set_enum(cam, "TriggerSource", source):
            raise RuntimeError(f"Failed to set TriggerSource to {source}")
        if not _set_enum(cam, "TriggerActivation", activation):
            raise RuntimeError(f"Failed to set TriggerActivation to {activation}")
        if not _set_enum(cam, "TriggerMode", "On"):
            raise RuntimeError("Failed to enable TriggerMode")

        self.mode = "native"
        logger.info(
            "Hardware trigger armed (Pylon TriggerMode): source=%s activation=%s",
            source,
            activation,
        )

    def _configure_gpio_poll(self) -> None:
        status = self.read_line()
        self.mode = "gpio_poll"
        self._last_line_status = status
        logger.info(
            "GPIO edge trigger armed (Pylon): line=%s activation=%s idle_status=%s",
            self.config.source,
            self.config.activation,
            self._last_line_status,
        )
