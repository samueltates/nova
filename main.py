import json
from nova import parseInput, runningPrompts, logs, functionsRunning
from gptindex import indexDocument
from flask import Flask, jsonify, request
from flask_cors import CORS

import os

app = Flask(__name__)
CORS(app)

print('main running')

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/message', methods=['POST','GET'])
def message():
    print('message route hit   ')
    if request.method == 'GET':
        return jsonify({"ok this is working"})
    if request.method == 'POST':
        print('post hit')
        post_body_py = request.get_json()
        print(post_body_py["sessionID"])
        parseInput(post_body_py)
        while functionsRunning > 0:
                    print('waiting for functions to finish')
                    print(functionsRunning)
                    pass
        if (post_body_py["action"] == "getPrompts"):
            responseJson = json.dumps(
                runningPrompts[post_body_py["sessionID"]])
        if (post_body_py["action"] == "sendInput"):
            responseJson = json.dumps(logs[post_body_py["sessionID"]])
            # case "addCartridge":
        print('printing prompts pulled from running??')

        return responseJson
    

@app.route('/indexdoc', methods=['POST','GET'])
def indexdoc():
    print('indexdoc route hit   ')
    userID = request.json["userID"]
    file_content = request.json["file_content"]
    file_name = request.json["file_name"]
    indexRecord = indexDocument(userID, file_content, file_name)

    for indexKey, indexVal in indexRecord.items():
        indexCartridge = {
             indexKey: {
                'label' : indexVal['label'],
                'type' : indexVal['type'],
                'enabled' : indexVal['enabled'],
             }
        }

    response = {
        "success": True,
        "message":"File indexed successfully.",
        "data": indexCartridge

    }
    return jsonify(response)

if __name__ == '__main__':
    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    app.run(host=os.getenv("HOST", default='0.0.0.0'), port=os.getenv("PORT", default='3000'))

