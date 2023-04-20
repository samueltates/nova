import json
from nova import initialiseCartridges, handleChatInput, runningPrompts, logs, functionsRunning, eZprint
from gptindex import indexDocument, indexGoogleDoc
from flask import Flask, jsonify, request
from flask_cors import CORS

import os

app = Flask(__name__)
CORS(app)

eZprint('main running')

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/message', methods=['POST','GET'])
def message():
    eZprint('message route hit   ')
    if request.method == 'GET':
        return jsonify({"ok this is working"})
    if request.method == 'POST':
        eZprint('post hit')
        post_body_py = request.get_json()
        eZprint(post_body_py["sessionID"])
        parseInput(post_body_py)
        while functionsRunning > 0:
                    eZprint('waiting for functions to finish')
                    eZprint(functionsRunning)
                    pass
        if (post_body_py["action"] == "getPrompts"):
            responseJson = json.dumps(
                runningPrompts[post_body_py["sessionID"]])
        if (post_body_py["action"] == "sendInput"):
            responseJson = json.dumps(logs[post_body_py["sessionID"]])
            # case "addCartridge":
        eZprint('printing prompts pulled from running??')

        return responseJson
    

@app.route('/initialise', methods=['POST','GET'])
def initialise():
    if request.method == 'POST':
        eZprint('initialise called')
        post_body_py = request.get_json()
        initialiseCartridges(post_body_py)
        responseJson = json.dumps(
            runningPrompts[post_body_py["sessionID"]])
        return responseJson
    

@app.route('/handleInput', methods=['POST','GET'])
def handleInput():
    if request.method == 'POST':
        eZprint('handleInput called')
        post_body_py = request.get_json()
        handleChatInput(post_body_py)
        responseJson = json.dumps(logs[post_body_py["sessionID"]])
        return responseJson
    

@app.route('/indexdoc', methods=['POST','GET'])
def indexdoc():
    eZprint('indexdoc route hit   ')
    userID = request.json["userID"]
    file_content = request.json["file_content"]
    file_name = request.json["file_name"]
    file_type = request.json["file_type"]
    indexRecord = indexDocument(userID, file_content, file_name, file_type)

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
        "data": indexCartridge

    }
    return jsonify(response)

@app.route('/indexGDoc', methods=['POST','GET'])
def indexGDoc():
    eZprint('indexGDoc route hit   ')
    userID = request.json["userID"]
    gDocID = request.json["gDocID"]

    indexRecord = indexGoogleDoc(userID, gDocID )

    for indexKey, indexVal in indexRecord.items():
        indexCartridge = {
             indexKey: {
                'label' : indexVal['label'],
                'description' : indexVal['description'],
                'type' : indexVal['type'],
                'enabled' : indexVal['enabled'],
             }
        }
        
    eZprint('printing index cartridge')
    print (indexCartridge)
    response = {
        "success": True,
        "message":"File indexed successfully.",
        "data": indexCartridge

    }
    return jsonify(response)

if __name__ == '__main__':
    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    app.run(host=os.getenv("HOST", default='0.0.0.0'), port=os.getenv("PORT", default='3000'))

