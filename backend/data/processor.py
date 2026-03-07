import pandas as pd
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
class Processor:
    def __init__(self):
        self.csv_path=Config.CSV_PATH
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

        return {
            "item_name":last_record[Config.COL_ITEM],
            "timestamp":last_record[Config.COL_TIMESTAMP].strftime("%Y-%m-%d %H:%M:%S"),
            "location":last_record[Config.COL_LOCATION],

            "image_url":f"/iamges/{last_record[Config.COL_IMAGE]}"


        }


