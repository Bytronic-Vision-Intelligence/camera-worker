import cv2
from PIL import Image
import time
import numpy as np
import logging
class Camera:
    def connect_to_camera(self):        
        """ Connect to the camera based on the specified camera type.
        Raises:
            Exception: If the camera type is unsupported or if connection fails."""
        # Open the default OpenCV camera and store on the instance so
        # subsequent calls to `capture_image` can use the same handle.
        self.camera = cv2.VideoCapture(0)
        if not getattr(self.camera, "isOpened", lambda: False)():
            # Ensure camera resources are released if open failed
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None
            raise Exception("Failed to open OpenCV camera.")
        return self.camera
    
    def capture_image(self):
        """Capture an image from the camera and return it as a numpy array.
        Returns:
            numpy.ndarray: The captured image.
        Raises:
            Exception: If the camera type is unsupported or if image capture fails."""
        
        ret, frame = self.camera.read()
        if not ret:
            raise Exception("Failed to capture image from OpenCV camera.")
        return frame