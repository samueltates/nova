import os
import json
import base64

# import json
from nova import initialiseCartridges, prismaConnect, prismaDisconnect, addCartridgePrompt, handleChatInput, handleIndexQuery, updateCartridgeField, eZprint, summariseChatBlocks, updateContentField
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
        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):
    # print(parsed_data['type'])
    if(parsed_data['type'] == 'requestCartridges'):
        await initialiseCartridges(parsed_data['data'])
    # print(parsed_data['type']) # Will print 'requestCartridges'
    # print(parsed_data['data']) # Will print the data sent by the client
    if(parsed_data['type'] == 'sendMessage'):
        eZprint('handleInput called')
        await handleChatInput(parsed_data['data'])
    if(parsed_data['type']== 'updateCartridgeField'):
        # print('updateCartridgeField route hit')
        print(parsed_data['data']['fields'])
        await updateCartridgeField(parsed_data['data'])
    if(parsed_data['type']== 'updateContentField'):
        # print('updateCartridgeField route hit')
        # print(parsed_data['data']['fields'])
        await updateContentField(parsed_data['data'])
    if(parsed_data['type']== 'newPrompt'):
        await addCartridgePrompt(parsed_data['data'])
    if(parsed_data['type']== 'requestDocIndex'):
        data = parsed_data['data']
        if 'gDocID' in data:
            eZprint('indexing gDoc')
            # print(data)
            indexRecord = await indexGoogleDoc(data['userID'], data['sessionID'], data['gDocID'], data['tempKey'], data['indexType'])
            if indexRecord:
                payload = {
                    'tempKey': data['tempKey'],
                    'newCartridge': indexRecord,
                }
            await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    # parse index query
    if(parsed_data['type']== 'queryIndex'):

        data = parsed_data['data']
        await handleIndexQuery(data['userID'], data['cartKey'], data['sessionID'], data['query'])
    if(parsed_data['type']== 'summarizeContent'):
        data = parsed_data['data']
        print(data)
        await summariseChatBlocks(data['userID'], data['sessionID'], data['messageIDs'], data['summaryID'])
    elif parsed_data["type"] == "indexdoc_start":
        await handle_indexdoc_start(parsed_data["data"])
    elif parsed_data["type"] == "indexdoc_chunk":
        await handle_indexdoc_chunk(parsed_data["data"])
    elif parsed_data["type"] == "indexdoc_end":
        await handle_indexdoc_end(parsed_data["data"])
    
    if(parsed_data["type"] == '__ping__'):
        # print('pong')
        await websocket.send(json.dumps({'event':'__pong__'}))

    # if(parsed_data['type']== 'indexFile'):
    #     data = parsed_data['data']
    #     indexRecord = await indexDocument(data["userID"], data["file_content"], data["file_name"], data["file_type"], data["sessionID"], data["tempKey"],data["indexType"])
    
    # Initialize a dictionary to store incoming file chunks
file_chunks = {}

async def handle_indexdoc_start(data):
  tempKey = data["tempKey"]
  file_chunks[tempKey] = {
    "metadata": data,
    "chunks_received": 0,
    "content": [],
  }

async def handle_indexdoc_chunk(data):
  tempKey = data["tempKey"]
  file_chunks[tempKey]["chunks_received"] += 1
  # Decode the base64-encoded chunkContent
  decoded_chunk_content = base64.b64decode(data["chunkContent"])
  file_chunks[tempKey]["content"].append(decoded_chunk_content)


  # You could also process and store the chunk immediately in this step
  # instead of collecting all chunks in `file_chunks` and processing them later

async def handle_indexdoc_end(data):
    tempKey = data["tempKey"]
    file_metadata = file_chunks[tempKey]["metadata"]
    file_content = b''.join(file_chunks[tempKey]["content"])
    # Process the uploaded file
    # You might need to convert the content from a bytearray to the initial format (e.g., base64)
    print(file_metadata)
    indexRecord = await indexDocument(file_metadata["userID"], file_metadata["sessionID"], file_content, file_metadata["file_name"], file_metadata["file_type"], file_metadata["tempKey"],file_metadata["indexType"])
    if indexRecord:
        payload = {
            'tempKey': data['tempKey'],
            'newCartridge': indexRecord,
        }
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    # Remove the stored file chunks upon completion
    del file_chunks[tempKey]

# For example, the process_uploaded_file() function could be like this:


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
    indexType = data["indexType"]
    indexRecord = await indexDocument(userID, sessionID, file_content, file_name, file_type, tempKey, indexType)

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
    return json.dumps(payload)
    # await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

if __name__ == '__main__':

    host=os.getenv("HOST", default='0.0.0.0')
    port=int(os.getenv("PORT", default=5000))
    config = Config()
    config.bind = [str(host)+":"+str(port)]  # As an example configuration setting

    asyncio.run(serve(app, config))

    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    # app.run(host="127.0.0.1", port=5500) 
