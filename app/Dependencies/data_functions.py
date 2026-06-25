from numpy import ndarray
from cv2 import imencode
from time import localtime, strftime
def encode_image_to_bytes(image: ndarray) -> bytes:
    """ Encode the image as JPEG and return the bytes """
    if image is None:
        raise ValueError("Input image is None.")
    if not isinstance(image, ndarray):
        raise ValueError("Input image must be a numpy array.")
    
    success, encoded_image = imencode('.jpg', image)

    if not success:
        raise RuntimeError("Failed to encode image to JPEG format.")
    return encoded_image.tobytes()

def encode_date_time_to_bytes() -> bytes:
    """encodes the current date and time into bytes"""
    date_time = strftime("%Y-%m-%d %H:%M:%S", localtime())
    return date_time.encode("utf-8")