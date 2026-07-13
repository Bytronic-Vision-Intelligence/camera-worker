from numpy import ndarray, uint8
from cv2 import imencode, normalize, NORM_MINMAX, CV_8U
from time import localtime, strftime


def prepare_image_for_jpeg(image: ndarray) -> ndarray:
    """Return an 8-bit image suitable for JPEG (keeps mono HxW raw layout)."""
    if image is None:
        raise ValueError("Input image is None.")
    if not isinstance(image, ndarray):
        raise ValueError("Input image must be a numpy array.")

    img = image
    if img.ndim == 3 and img.shape[2] == 1:
        img = img[:, :, 0]

    if img.dtype != uint8:
        # Mono16 / float etc. → uint8 without expanding to BGR
        img = normalize(img, None, 0, 255, NORM_MINMAX, dtype=CV_8U)
    return img


def encode_image_to_bytes(image: ndarray) -> bytes:
    """Encode the image as JPEG and return the bytes."""
    img = prepare_image_for_jpeg(image)

    success, encoded_image = imencode(".jpg", img)

    if not success:
        raise RuntimeError("Failed to encode image to JPEG format.")
    return encoded_image.tobytes()


def encode_date_time_to_bytes() -> bytes:
    """Encode the current date and time into bytes."""
    date_time = strftime("%Y-%m-%d %H:%M:%S", localtime())
    return date_time.encode("utf-8")
