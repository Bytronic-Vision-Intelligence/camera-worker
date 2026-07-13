import os
from numpy import ndarray
from cv2 import imwrite
import logging
import threading
import datetime

def save_image_to_file(image:ndarray, directory:str, filename:str, archive_params:dict):
    ''' Saves an image to a specified file directory
    
    Args:
        image: a numpy array of pixels
        directory: a directory location
        filename: the name of the image
        params: frequency of saving, when to delete etc.
    '''

    subfolder = None
    archive_freq = archive_params.get("archive_freq", None)
    if archive_freq:
        save_timestamp = datetime.datetime.now()
        if archive_freq == "daily":
            subfolder = save_timestamp.strftime("%Y%m%d")
        elif archive_freq == "hourly":
            subfolder = save_timestamp.strftime("%Y%m%d_%H")
            
    if image is None:
        logging.error("Image cannot be none")
    if directory == "":
        logging.error("no directory specified")
    base_directory = os.fspath(directory)
    if not os.path.exists(base_directory):
        logging.error(f"the provided directory {directory} could not be found")
    if filename == "":
        logging.error("Filename cannot be empty, please provide a valid file name")
    try:
        save_directory = os.path.join(base_directory, subfolder) if subfolder else base_directory
        os.makedirs(save_directory, exist_ok=True)

        image_path = os.path.join(save_directory, f"{filename}.png")
        # Persist the array as-is (e.g. Mono16 HxW). Do not convert to BGR.
        success = imwrite(image_path, image)
        if success:
            logging.info(
                "image successfully written to archive shape=%s dtype=%s path=%s",
                getattr(image, "shape", None),
                getattr(image, "dtype", None),
                image_path,
            )
        else:
            logging.error(f"failed to write image to archive: {image_path}")
    except Exception as e:
        logging.error(f"failed to write image to archive error: {e}")

def archive_image(image:ndarray, directory:str, filename:str, archive_params:dict):
    '''starts a worker thread that will run the save_image_to_file function on a given image
    
    Args:
        image: a numpy array of pixels
        directory: a directory location
        filename: the name of the image
        '''

    threading.Thread(
        target=save_image_to_file,
        args=(
            image,
            directory,
            filename,
            archive_params
        ),
        daemon=True
    ).start()