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
    items=processor.get_all_items()
    return jsonify({"items:":items})

@app.route('/api/search',methods=['GET'])
def search():
    item_name=request.args.get('item_name')
    if not item_name:
        return jsonify({"message":"item name not exist"}),400

    result=processor.get_last_appearance(item_name)

    if result:
        return jsonify({"success":True,"items:":result})
    else:
        return jsonify({"success":False,"message":"item not exist"}),404

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(Config.IMAGE_FOLDER,filename)

if __name__ == '__main__':
    print(f"Server is running on port {Config.PORT}")
    print(f"Tracking CSV: {Config.CSV_PATH}")
    app.run(host='0.0.0.0',port=Config.PORT,debug=Config.DEBUG)
