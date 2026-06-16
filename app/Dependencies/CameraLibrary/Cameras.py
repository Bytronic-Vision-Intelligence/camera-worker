import cv2
from PIL import Image
import time
import numpy as np
class Camera:
    def __init__(self):
        self.camera = None
        #global buffer variables
        image_buffer = [0]
        newest_buffer = 0

    def define_Buffer(self, width:int = 1920, height:int = 1080, buffer_size:int = 1):
        if width < 1 or height < 1:
            raise ValueError("image size must be larger than 0 on both axis.")

        image = Image.new('RGB', (height, width))
        timeStamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        bufferItem = [image, timeStamp]
        
        image_buffer = [bufferItem]*buffer_size
        if image_buffer.shape > 1:
            return image_buffer
        
        raise ValueError(f"failed to set image buffer")

    def _add_to_buffer(image:np.ndarray, bufferPosition:int = 0):
        if bufferPosition <0:
            raise ValueError("Buffer position must be positiive")
        if bufferPosition > len(image_buffer):
            raise ValueError(f"index {bufferPosition} out of range {len(image_buffer)}")
        
        image_buffer[bufferPosition] = image, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
    def _read_from_buffer(bufferPosition:int=0):
        if bufferPosition <0:
            raise ValueError("Buffer position must be positiive")
        if bufferPosition > len(image_buffer):
            raise ValueError(f"index {bufferPosition} out of range {len(image_buffer)}")
        
        return image_buffer[bufferPosition]

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