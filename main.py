import os
import json

# import json
from nova import initialiseCartridges, availableCartridges, prismaConnect, prismaDisconnect, addCartridgePrompt, loadCartridges, runCartridges, handleChatInput, updateCartridgeField, runningPrompts, logs, functionsRunning, eZprint
from gptindex import indexDocument, indexGoogleDoc
import logging
import asyncio

from hypercorn.config import Config
from hypercorn.asyncio import serve

from appHandler import app, websocket
from quart import request

@app.route("/hello")
async def hello():
    return "Hello, World!"

@app.before_serving
async def startup():
    await prismaConnect()

@app.after_serving
async def shutdown():
    await prismaDisconnect()
    print("Disconnected from Prisma")

@app.websocket('/ws')
async def ws():
    eZprint('socket route hit')
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        if(parsed_data['type'] == 'requestCartridges'):
            await initialiseCartridges(parsed_data['data'])
        # print(parsed_data['type']) # Will print 'requestCartridges'
        # print(parsed_data['data']) # Will print the data sent by the client
        if(parsed_data['type'] == 'sendMessage'):
            cartridges = await asyncio.ensure_future( initialiseCartridges(parsed_data['data'])  )
            eZprint('handleInput called')
            await handleChatInput(parsed_data['data'])
        if(parsed_data['type']== 'updateCartridgeField'):
            # print('updateCartridgeField route hit')
            # print(parsed_data['data']['fields'])
            await updateCartridgeField(parsed_data['data'])
        if(parsed_data['type']== 'newPrompt'):
            await addCartridgePrompt(parsed_data['data'])
        if(parsed_data['type']== 'requestDocIndex'):
             data = parsed_data['data']
             if 'gDocID' in data:
                eZprint('indexing gDoc')
                indexRecord = await indexGoogleDoc(data['userID'], data['sessionID'], data['gDocID'], data['tempKey'])
                if indexRecord:
                    payload = {
                        'tempKey': data['tempKey'],
                        'newCartridge': indexRecord,
                    }
                await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

@app.route('/indexdoc', methods=['POST'])
async def http():
    eZprint('indexdoc route hit   ')
    data = await request.get_json()
    # print(data)
    userID = data["userID"]
    file_content = data["file_content"]
    file_name = data["file_name"]
    file_type = data["file_type"]
    sessionID = data["sessionID"]
    tempKey = data["tempKey"]
    indexRecord = await indexDocument(userID, sessionID, file_content, file_name, file_type, tempKey)

    for indexKey, indexVal in indexRecord.items():
        indexCartridge = {
            indexKey: {
                'label' : indexVal['label'],
                'type' : indexVal['type'],
                'enabled' : indexVal['enabled'],
                'description' : indexVal['description'],
            }
        }

    # response = {
    #     "success": True,
    #     "message":"File indexed successfully.",
    #     "tempKey": tempKey,
    #     # "data": indexCartridge
    # }
    payload = {
        'tempKey': tempKey,
        'newCartridge': indexCartridge,
    }
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

if __name__ == '__main__':

    host=os.getenv("HOST", default='0.0.0.0')
    port=int(os.getenv("PORT", default=5000))
    config = Config()
    config.bind = [str(host)+":"+str(port)]  # As an example configuration setting

    asyncio.run(serve(app, config))

    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    # app.run(host="127.0.0.1", port=5500) 
