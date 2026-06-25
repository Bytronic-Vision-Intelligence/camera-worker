"""FTP server for receiving and decoding LJ-S8000 height-image PNGs."""

import logging
import os
import queue
import threading

logger = logging.getLogger(__name__)
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from PIL import Image


class LJS_FTP_Receiver:
    """
    FTP server that catches height-image PNGs from the controller.

    Controller setup (one-time): Image Output → Height image, PNG, FTP;
    FTP Client -> this PC's IP, this port, this user/password.
    """

    # Z pitch per head model (mm), from Communication Library dwPitchZ table.
    Z_PITCH_MM = {
        "LJ-S015": 0.0004, "LJ-S025": 0.0010, "LJ-S040": 0.0012,
        "LJ-S080": 0.0020, "LJ-S160": 0.0024, "LJ-S320": 0.0046,
        "LJ-S640": 0.0102,
    }

    def __init__(self, host="0.0.0.0", port=21, user="ljs", password="ljs",
                 landing_dir="./ljs_images", head_model="LJ-S640",
                 passive_ports=range(60000, 60020)):
        # passive_ports: open these in any firewall between controller and PC.
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.landing_dir = os.path.abspath(landing_dir)
        self.head_model = head_model
        self.passive_ports = passive_ports
        self.last_path = None
        self._queue = queue.Queue()
        self._server = None
        self._thread = None

    def start(self):
        """Start the FTP server on a background thread. Returns self."""
        os.makedirs(self.landing_dir, exist_ok=True)

        authorizer = DummyAuthorizer()
        authorizer.add_user(self.user, self.password, self.landing_dir, perm="elradfmw")

        completed = self._queue

        class _Handler(FTPHandler):
            def on_file_received(self, file):
                # Fires only after upload fully completes.
                logger.debug("FTP received file: %s", file)
                completed.put(file)

        _Handler.authorizer = authorizer
        _Handler.passive_ports = self.passive_ports

        self._server = FTPServer((self.host, self.port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("LJS FTP server listening on %s:%s (landing dir: %s)", self.host, self.port, self.landing_dir)
        return self

    def stop(self):
        if self._server is not None:
            logger.info("Stopping LJS FTP server")
            self._server.close_all()
            self._server = None
            self._thread = None

    def wait_for_image(self, timeout=15.0):
        """
        Block until the next image arrives. Returns a 2D float32 height map in mm
        (NaN where there's no data). Raises TimeoutError if nothing arrives in time.
        """
        logger.debug("Waiting up to %.1fs for height image", timeout)
        try:
            path = self._queue.get(timeout=timeout)
        except queue.Empty:
            logger.error("Timed out waiting for height image after %.1fs", timeout)
            raise TimeoutError(
                "no image received within %.1fs — check the controller's Image "
                "Output and FTP Client settings point at this server" % timeout)
        logger.info("Height image received: %s", path)
        self.last_path = path
        return self.decode_height_mm(path, self.head_model)

    @classmethod
    def decode_height_mm(cls, source, head_model="LJ-S640"):
        """
        Convert a controller height PNG to a 2D float32 height map in mm.

        Encoding: 16-bit single-channel, pixel 0 = no data (NaN), otherwise:
            height_mm = (pixel - 32768) * Z_pitch_mm

        `source` may be a file path or a numpy array.
        """
        import numpy as np

        z = cls.Z_PITCH_MM.get(head_model)
        if z is None:
            raise ValueError("no Z pitch known for head model %r" % head_model)

        if isinstance(source, str):
            img = Image.open(source)
            img.load()
            arr = np.asarray(img)
        else:
            arr = np.asarray(source)

        if arr.ndim != 2:
            raise ValueError(
                "expected a 16-bit single-channel height image, got shape %s; "
                "check Image to Output = Height image and Format = PNG" % (arr.shape,))

        a = arr.astype(np.float32)
        return np.where(a == 0, np.nan, (a - 32768.0) * z)
