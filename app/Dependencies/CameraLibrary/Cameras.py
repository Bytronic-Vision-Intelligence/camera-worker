import cv2
from numpy import ndarray

class Camera:
    def __init__(self):
        self.camera = None

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

class CameraHeightMap(Camera):
    "Used for height map cameras"
    "As of now not useful, but be aware that you are using height map images with this class."
    
    def __init__(self):
        super().__init__()
    def connect_to_camera(self, timeout=30) -> CameraHeightMap: pass
    def capture_image(self) -> ndarray: pass