import os


class Config:
    DEBUG=True
    PORT=5000
    BACKEND_DIR=os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR=os.path.dirname(BACKEND_DIR)
    CSV_PATH=os.path.join(BACKEND_DIR,'data','recognition.csv')
    IMAGE_FOLDER=os.path.join(BACKEND_DIR,'images')
    PROCESSED_FOLDER=os.path.join(BACKEND_DIR,'processed_images')
    COL_TIMESTAMP='timestamp'
    COL_ITEM='class_name'
    COL_LOCATION='location'
    COL_IMAGE='image_id'
