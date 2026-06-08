import cv2

class Camera:
    def __init__(self, camera_type: str):
        self.camera = self.set_camera_class(camera_type)

    def connect_to_camera(self):        
        """ Connect to the camera based on the specified camera type.
        Raises:
            Exception: If the camera type is unsupported or if connection fails."""
        camera =  cv2.VideoCapture(0)
        if not camera is None:
            raise Exception("Failed to open OpenCV camera.")
        return camera
    
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