"""
Connects to the Keyence LJS-8000 controller.
This controller is used for height-map style scanners.
"""

import logging
import socket

from .cameras import CameraHeightMap
from .ftp_reciever import LJS_FTP_Receiver

logger = logging.getLogger(__name__)

class LJSError(Exception):
    """Raised when the controller replies ER,<cmd>,<code>."""

class LJSCamera(CameraHeightMap):
    """
    LJ-S8000 3D scanner, compatible with the CameraHeightMap interface.

    Usage:
        ljs = LJSCamera(host="192.168.10.10")
        ljs.connect_to_camera()
        height_mm = ljs.capture_image()   # 2D float32 array in mm, NaN = no data
        ljs.close()

    Any extra kwargs are forwarded to LJS_FTP_Receiver (host, port, user,
    password, landing_dir, head_model, passive_ports).
    """

    def __init__(self, host:str="192.168.10.10", port:int=8500, cmd_timeout:float=3.0, **ftp_kwargs):
        super().__init__()
        self.host = host
        self.port = port
        self._cmd_timeout = cmd_timeout
        self._sock = None
        self._ftp = LJS_FTP_Receiver(**ftp_kwargs)

    def connect_to_camera(self, timeout=30):
        "starts an ftp port to recieve images and sets camera into run mode"
        logger.info("Connecting to LJS controller at %s:%s", self.host, self.port)
        self._sock = socket.create_connection((self.host, self.port), timeout)
        self._sock.settimeout(self._cmd_timeout)
        self._ftp.start()
        self.run_mode()
        logger.info("LJS controller connected and in Run mode")
        return self

    def capture_image(self, image_timeout=15.0):
        """Trigger a scan and return a 2D float32 height map in mm (NaN = no data)."""
        self.trigger()
        return self._ftp.wait_for_image(timeout=image_timeout)

    def close(self):
        logger.info("Closing LJS controller connection")
        self._ftp.stop()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as e:
                logger.error("Failed to close socket: %s", e)
                raise e
            finally:
                self._sock = None

    # -- LJS command protocol --------------------------------------------------

    def command(self, text):
        """Send one command and return the reply (CR stripped). Raises LJSError on ER,..."""
        CR = b"\r"
        logger.debug("LJS >> %s", text)
        self._sock.sendall(text.encode("ascii") + CR)
        buf = bytearray()
        while CR not in buf:
            chunk = self._sock.recv(256)
            if not chunk:
                raise ConnectionError("controller closed the connection")
            buf += chunk
        reply = bytes(buf).split(CR, 1)[0].decode("ascii").strip()
        logger.debug("LJS << %s", reply)
        if reply.startswith("ER,"):
            logger.error("LJS command error: %s", reply)
            raise LJSError(reply)
        return reply

    def run_mode(self):
        """R0 — switch to Run mode. Required before triggering."""
        return self.command("R0")

    def read_mode(self):
        """RM — returns the current camera mode; 'Run' or 'Setup'."""
        return "Run" if self.command("RM").endswith("1") else "Setup"

    def trigger(self):
        """T1 — take one scan. Requires Run mode and head READY."""
        return self.command("T1")
