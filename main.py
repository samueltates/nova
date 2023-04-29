import os
import eventlet
eventlet.monkey_patch()
import asyncio
import logging

import json
from nova import initialiseCartridges, availableCartridges, addCartridgePrompt, loadCartridges, runCartridges, handleChatInput, updateCartridgeField, runningPrompts, logs, functionsRunning, eZprint
from gptindex import indexDocument, indexGoogleDoc
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from socketHandler import socketio

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') 
CORS(app)
socketio.init_app(app,log_output=True, cors_allowed_origins=os.environ.get('CORS_ALLOWED_ORIGINS'))


@socketio.on('requestCartridges')
def requestCartridges(data):
    eZprint('requestCartridges called')
    socketio.emit('sendCartridgeStatus', 'loading cartridges')
    initialiseCartridges(data)
    socketio.emit('sendCartridgeStatus', 'cartridgesLoaded')
    # socketio.emit('sendCartridges', availableCartridges[data["sessionID"]])

@socketio.on('sendMessage')
def messageRecieved(data):
    eZprint('handleInput called')
    handleChatInput(data)


@app.route('/indexdoc', methods=['POST','GET'])
def indexdoc():
    eZprint('indexdoc route hit   ')
    userID = request.json["userID"]
    file_content = request.json["file_content"]
    file_name = request.json["file_name"]
    file_type = request.json["file_type"]
    tempKey = request.json["tempKey"]
    indexRecord = indexDocument(userID, file_content, file_name, file_type, tempKey)

    for indexKey, indexVal in indexRecord.items():
        indexCartridge = {
             indexKey: {
                'label' : indexVal['label'],
                'type' : indexVal['type'],
                'enabled' : indexVal['enabled'],
                'description' : indexVal['description'],
             }
        }

    response = {
        "success": True,
        "message":"File indexed successfully.",
        "tempKey": tempKey,
        # "data": indexCartridge
    }
    payload = {
        'tempKey': tempKey,
        'newCartridge': indexCartridge,
    }
    socketio.emit('updateTempCart', payload)
    return jsonify(response)


@socketio.on('newPrompt')
def requestNewPrompt(data):
    asyncio.run(addCartridgePrompt(data))


@socketio.on('requestFileIndex')
def requestFileIndex(file, callback):
    eZprint('requestFileIndex called')
    # callback({ 'message':' err ?' "failure" : "success" })


@socketio.on('requestDocIndex')
def requestDocIndex(data):
    eZprint('requestDocIndex called')
    eZprint(data)
    if 'gDocID' in data:
        eZprint('indexing gDoc')
        indexRecord = indexGoogleDoc(data['userID'], data['sessionID'], data['gDocID'], data['tempKey'])
        if indexRecord:
            # for indexKey, indexVal in indexRecord.items():
            #     indexCartridge = {
            #         indexKey: indexVal
            #     }
            payload = {
                'tempKey': data['tempKey'],
                'newCartridge': indexRecord,
            }
        # asyncio.run(fakeWait())
        # ## fake index cartridge
        # indexCartridge = {  
        #     'index': {
        #         'label': 'Index',
        #         'description': 'fake index for testing purposes',
        #         'type': 'index',
        #         'enabled': True,
        #     }
        # }
        # ##fake payload
        # payload = { 
        #     'tempKey': data['tempKey'],
        #     'newCartridge': indexCartridge,
        # }
        socketio.emit('updateTempCart', payload)
        # socketio.emit('sendCartridgeStatus', 'cartridgesLoaded')
 
@socketio.on('updateCartridgeField')
def requestUpdateCartridgeField(data):
    eZprint('softDeleteCartridge called')
    asyncio.run(updateCartridgeField(data))
    
async def fakeWait():
    await asyncio.sleep(2)
    
    
    
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
    # logging.getLogger('prisma').setLevel(logging.DEBUG)
