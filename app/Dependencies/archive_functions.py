import os
from numpy import ndarray
from cv2 import imwrite
import logging
import threading
import datetime

from Dependencies.data_functions import prepare_image_for_jpeg

def save_image_to_file(image:ndarray, directory:str, filename:str, archive_params:dict, camera_id=None):
    ''' Saves an image to a specified file directory
    
    Args:
        image: a numpy array of pixels
        directory: a directory location
        filename: the name of the image
        params: frequency of saving, when to delete etc.
        camera_id: optional id used as save_dir/date/cam{id}
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
        path_parts = [base_directory]
        if subfolder:
            path_parts.append(subfolder)
        if camera_id is not None:
            path_parts.append(f"cam{camera_id}")
        save_directory = os.path.join(*path_parts)
        os.makedirs(save_directory, exist_ok=True)

        image_path = os.path.join(save_directory, f"{filename}.png")
        # Same min-max → uint8 stretch as the MQTT/UI JPEG path. Raw Mono14
        # counts (~3k–4k) look black in most viewers when saved as 16-bit PNG.
        to_save = prepare_image_for_jpeg(image)
        success = imwrite(image_path, to_save)
        if success:
            logging.info(
                "image successfully written to archive shape=%s dtype=%s path=%s",
                getattr(to_save, "shape", None),
                getattr(to_save, "dtype", None),
                image_path,
            )
        else:
            logging.error(f"failed to write image to archive: {image_path}")
    except Exception as e:
        logging.error(f"failed to write image to archive error: {e}")

def archive_image(image:ndarray, directory:str, filename:str, archive_params:dict, camera_id=None):
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
            archive_params,
            camera_id,
        ),
        daemon=True
    ).start()