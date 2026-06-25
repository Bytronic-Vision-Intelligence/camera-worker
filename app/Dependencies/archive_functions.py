import os
from numpy import ndarray
from cv2 import imwrite
import logging
import threading

def save_image_to_file(image:ndarray, directory:str, filename:str):
    ''' Saves an image to a specified file directory
    
    Args:
        image: a numpy array of pixels
        directory: a directory location
        filename: the name of the image
    '''

    if image is None:
        logging.error("Image cannot be none")
    if directory == "":
        logging.error("no directory specified")
    if not os.path.exists(directory):
        logging.error(f"the provided directory {directory} could not be found")
    if filename == "":
        logging.error("Filename cannot be empty, please provide a valid file name")
    try:
        imwrite(directory+"/"+filename+".png", image)
        logging.info("image successfully written to archive")
    except Exception as e:
        logging.error(f"failed to write image to archive error: {e}")

def archive_image(image:ndarray, directory:str, filename:str):
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
            filename
        ),
        daemon=True
    ).start()