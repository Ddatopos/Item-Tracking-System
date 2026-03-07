import os
BACKEND_DIR=os.path.dirname(os.path.abspath(__file__))
ROOT_DIR=os.path.dirname(BACKEND_DIR)
class Config:
    DEBUG=True
    PORT=5000
    CSV_PATH=os.path.join(BACKEND_DIR,'data','recognition.csv')
    IMAGE_FOLDER=os.path.join(BACKEND_DIR,'images')

    COL_TIMESTAMP='timestamp'
    COL_ITEM='item_name'
    COL_LOCATION='location'
    COL_IMAGE='image_filename'
