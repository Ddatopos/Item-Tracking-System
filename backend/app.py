from flask import Flask,jsonify,request,send_from_directory
from flask_cors import CORS
from data.processor import Processor
from config import Config
import os
app=Flask(__name__)
CORS(app)

processor=Processor()

@app.route('/api/items',methods=['GET'])
def get_items():
    """返回物品类别列表，前端直接当数组用"""
    items=processor.get_all_items()
    return jsonify(items)

@app.route('/api/items/<path:category>',methods=['GET'])
def get_item_last(category):
    """查询某物品最后一次出现，返回 category / image_path / timestamp，与前端约定一致"""
    result=processor.get_last_appearance(category)
    if result is None:
        return jsonify({"message":"未找到该物品记录"}),404
    return jsonify({
        "category": result["item_name"],
        "image_path": result["image_url"],
        "timestamp": result["timestamp"],
    })

@app.route('/api/search',methods=['GET'])
def search():
    """兼容旧接口：?item_name=xxx"""
    item_name=request.args.get('item_name')
    if not item_name:
        return jsonify({"message":"item name not exist"}),400
    result=processor.get_last_appearance(item_name)
    if result:
        return jsonify({"success":True,"items:":result})
    return jsonify({"success":False,"message":"item not exist"}),404

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(Config.IMAGE_FOLDER,filename)

if __name__ == '__main__':
    print(f"Server is running on port {Config.PORT}")
    print(f"Tracking CSV: {Config.CSV_PATH}")
    app.run(host='0.0.0.0',port=Config.PORT,debug=Config.DEBUG)
