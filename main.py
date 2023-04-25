import os
import eventlet
eventlet.monkey_patch()
import asyncio

import json
from nova import initialiseCartridges, availableCartridges, loadCartridges, runCartridges, handleChatInput, runningPrompts, logs, functionsRunning, eZprint
from gptindex import indexDocument, indexGoogleDoc
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from socketHandler import socketio

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') 
CORS(app)
socketio.init_app(app, cors_allowed_origins=os.environ.get('CORS_ALLOWED_ORIGINS'))


# eZprint('main running')

# @app.route('/')
# def index():
#     # return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})
#     return render_template('index.html')

@socketio.on('requestCartridges')
def requestCartridges(data):
    socketio.emit('sendCartridgeStatus', 'loading cartridges')
    initialiseCartridges(data)
    socketio.emit('sendCartridgeStatus', 'cartridgesLoaded')
    # socketio.emit('sendCartridges', availableCartridges[data["sessionID"]])

@socketio.on('sendMessage')
def messageRecieved(data):
    eZprint('handleInput called')
    handleChatInput(data)

    
    # responseJson = json.dumps(logs[post_body_py["sessionID"]])
    # return responseJson

# @app.route('/initialise', methods=['POST','GET'])
# def initialise():
#     if request.method == 'POST':
#         eZprint('initialise called')
#         post_body_py = request.get_json()
#         initialiseCartridges(post_body_py)
#         responseJson = json.dumps(
#             runningPrompts[post_body_py["sessionID"]])
#         return responseJson
    

# @app.route('/handleInput', methods=['POST','GET'])
# def handleInput():
#     if request.method == 'POST':
#         eZprint('handleInput called')
#         post_body_py = request.get_json()
#         handleChatInput(post_body_py)
#         responseJson = json.dumps(logs[post_body_py["sessionID"]])
#         return responseJson
    

# @app.route('/indexdoc', methods=['POST','GET'])
# def indexdoc():
#     eZprint('indexdoc route hit   ')
#     userID = request.json["userID"]
#     file_content = request.json["file_content"]
#     file_name = request.json["file_name"]
#     file_type = request.json["file_type"]
#     indexRecord = indexDocument(userID, file_content, file_name, file_type)

#     for indexKey, indexVal in indexRecord.items():
#         indexCartridge = {
#              indexKey: {
#                 'label' : indexVal['label'],
#                 'type' : indexVal['type'],
#                 'enabled' : indexVal['enabled'],
#                 'description' : indexVal['description'],


#              }
#         }

#     response = {
#         "success": True,
#         "message":"File indexed successfully.",
#         "data": indexCartridge

#     }
#     return jsonify(response)

# @app.route('/indexGDoc', methods=['POST','GET'])
# def indexGDoc():
#     eZprint('indexGDoc route hit   ')
#     userID = request.json["userID"]
#     gDocID = request.json["gDocID"]

#     indexRecord = indexGoogleDoc(userID, gDocID )

#     for indexKey, indexVal in indexRecord.items():
#         indexCartridge = {
#              indexKey: {
#                 'label' : indexVal['label'],
#                 'description' : indexVal['description'],
#                 'type' : indexVal['type'],
#                 'enabled' : indexVal['enabled'],
#              }
#         }
        
#     eZprint('printing index cartridge')
#     print (indexCartridge)
#     response = {
#         "success": True,
#         "message":"File indexed successfully.",
#         "data": indexCartridge

#     }
#     return jsonify(response)

if __name__ == '__main__':
    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    socketio.run(app, host=os.getenv("HOST", default='0.0.0.0'), port=int(os.getenv("PORT", default=5000)))

