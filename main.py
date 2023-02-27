import json
from nova import parseInput, runningPrompts, logs, functionsRunning

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


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
