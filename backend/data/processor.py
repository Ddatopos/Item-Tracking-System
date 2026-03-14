import pandas as pd
import os
import sys
import ast
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
class Processor:
    def __init__(self):
        self.csv_path=Config.CSV_PATH
        self.backend_dir=Config.BACKEND_DIR
        self.processed_folder=Config.PROCESSED_FOLDER
        if not os.path.exists(self.processed_folder):
            os.makedirs(self.processed_folder)
    def load_data(self):
        if not os.path.exists(self.csv_path):
            return None
        try:
            df=pd.read_csv(self.csv_path)
            df[Config.COL_TIMESTAMP]=pd.to_datetime(df[Config.COL_TIMESTAMP])
            return df
        except Exception as e:
            print(f"读取出错:{e}")
            return None
    def get_all_items(self):
        df=self.load_data()
        if df is None or df.empty:
            return []
        return df[Config.COL_ITEM].unique().tolist()
    def get_last_appearance(self,item_name):
        df=self.load_data()
        if df is None or df.empty:
            return None

        target_rows=df[df[Config.COL_ITEM]==item_name]
        if target_rows.empty:
            return None

        sorted_rows=target_rows.sort_values(by=Config.COL_TIMESTAMP,ascending=False)

        last_record=sorted_rows.iloc[0]


        #========画图开始========

        image_filename=last_record[Config.COL_IMAGE]
        original_image_path=os.path.join(Config.IMAGE_FOLDER,image_filename)

        processed_filename=f"boxed_{image_filename}"
        processed_image_path=os.path.join(self.processed_folder,processed_filename)
        if not os.path.exists(processed_image_path):
            try:
                location_str=str(last_record[Config.COL_LOCATION])
                bbox=ast.literal_eval(location_str)
                if isinstance(bbox,list) and len(bbox)==4:
                    xmin,ymin,xmax,ymax=int(bbox[0]),int(bbox[1]),int(bbox[2]),int(bbox[3])
                    img=cv2.imread(original_image_path)
                    if img is not None:
                        cv2.rectangle(img,(xmin,ymin),(xmax,ymax),(0,0,255),3)
                        cv2.imwrite(processed_image_path,img)
                    else:
                        print(f"警告：找不到原图，无法画框->{original_image_path}")

                else:
                    print(f"警告：坐标格式不对，跳过画框->{location_str}")

            except Exception as e:
                print(f"画框失败(坐标解析错误):{e}")










        return {
            "item_name":last_record[Config.COL_ITEM],
            "timestamp":last_record[Config.COL_TIMESTAMP].strftime("%Y-%m-%d %H:%M:%S"),
            "location":last_record[Config.COL_LOCATION],

            "image_url":f"/images/{image_filename}"
             ,
            "processed_image_url":f"/processed/{processed_filename}"


        }


