import os
from quart import request, jsonify, url_for, session
from quart_session import Session
from hypercorn.config import Config
from hypercorn.asyncio import serve
from appHandler import app, websocket
import asyncio
import json
import base64
from nova import initialiseCartridges, prismaConnect, prismaDisconnect, addCartridgePrompt, handleChatInput, handleIndexQuery, updateCartridgeField, eZprint, summariseChatBlocks, updateContentField
from gptindex import indexDocument
from googleAuth import login, silent_check_login, logout
from quart_redis import RedisHandler, get_redis

app.session = session
redis_handler = RedisHandler(app)
Session(app)
# redis = get_redis()

@app.route("/")
async def index():
    return "welcome to the inne (dex)!"

@app.route("/hello")
async def hello():

    return "Hello, World!"

@app.before_serving
async def startup():
    await prismaConnect()
    app.redis = get_redis()

    # await googleAuthHandler()

@app.after_serving
async def shutdown():
    await prismaDisconnect()
    
    print("Disconnected from Prisma")

@app.route("/startsession")
async def startsession():
    print('start-session route hit')
    sessionID = await app.redis.get('sessionID')
    if sessionID == None:
        sessionID = os.urandom(24).hex()
        await app.redis.set('sessionID', sessionID) 
    else:
        sessionID = sessionID.decode('utf-8')
    payload = {
        'sessionID': sessionID
    }
    print('sessionID: ' + sessionID)
    authorised = await silent_check_login()
    userName = None
    if authorised:
        await app.redis.set('authorised', 1)
        userName = await app.redis.get('userName')
        if userName:
            payload['authorised'] = authorised
            userName = userName.decode('utf-8')
            payload['userName'] = userName
    # else:
    #     loginURL= await login()
    #     payload['loginURL']= loginURL
    return jsonify(payload)

@app.route('/SSO', methods=['GET'])
async def SSO():
    print('SSO route hit')
    loginURL = await login()
    return jsonify({'loginURL': loginURL})

@app.route('/awaitSSO', methods=['GET']) 
async def awaitSSO():
    print('awaitSSO route hit')
    print(await app.redis.get('userID'))
    while(await app.redis.get('userID') == None):
        await asyncio.sleep(1)
    print('SSO complete')
    userID = await app.redis.get('userID')
    userName = await app.redis.get('userName')
    authorised = await app.redis.get('authorised')
    sessionID = await app.redis.get('sessionID')
    userID = userID.decode('utf-8')
    userName = userName.decode('utf-8')
    authorised = authorised.decode('utf-8')
    sessionID = sessionID.decode('utf-8')

    payload = {
        'userID': userID,
        'userName': userName,
        'authorised': authorised,
        'sessionID': sessionID
    }

    return jsonify({'event':'ssoComplete', 'payload':payload})

@app.route('/requestLogout', methods=['GET'])
async def requestLogout():
    print('requestLogout route hit')
    logoutStatus = await logout()    
    return jsonify({'logout': logoutStatus})


@app.websocket('/ws')
async def ws():
    eZprint('socket route hit')
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):
    if(parsed_data['type'] == 'requestCartridges'):
        authorised = await app.redis.get('authorised')
        if authorised:
            userID = await app.redis.get('userID')
            userName = await app.redis.get('userName')
            sessionID = await app.redis.get('sessionID')
            userID = userID.decode('utf-8')
            userName = userName.decode('utf-8')
            sessionID = sessionID.decode('utf-8')
            userInfo = {
                'userID': userID,
                'userName': userName,
                'sessionID' : sessionID
            }
        else:
            sessionID = await app.redis.get('sessionID')
            sessionID = sessionID.decode('utf-8')
            userID = await app.redis.set('userID', 'Guest')
            userName = await app.redis.set('userName', 'Guest')

            userInfo = {
                'userID': 'Guest',
                'userName': 'Guest',
                'sessionID' : sessionID
            }

        await initialiseCartridges(userInfo)

    if(parsed_data['type'] == 'requestCartridgesAuthed'):
        userID = await app.redis.get('userID')
        userName = await app.redis.get('userName')
        sessionID = await app.redis.get('sessionID')
        userID = userID.decode('utf-8')
        userName = userName.decode('utf-8')
        sessionID = sessionID.decode('utf-8')
        userInfo = {
            'userID': userID,
            'userName': userName,
            'sessionID' : sessionID
        }
        print('requestCartridgesAuthed route hit')
        print(userInfo)

        await initialiseCartridges(userInfo)
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
            print(data)
            indexRecord = await asyncio.create_task(indexDocument(data))
            # indexRecord = await indexGoogleDoc(data['userID'], data['sessionID'], data['gDocID'], data['tempKey'], data['indexType'])
            if indexRecord:
                request = {
                    'tempKey': data['tempKey'],
                    'newCartridge': indexRecord.blob,
                }
            await websocket.send(json.dumps({'event':'updateTempCart', 'payload':request}))
            await asyncio.create_task(handleIndexQuery(indexRecord.key, 'Give this document a short summary.'))

    # parse index query
    if(parsed_data['type']== 'queryIndex'):
        data = parsed_data['data']
        await asyncio.create_task(handleIndexQuery( data['cartKey'], data['query']))
    if(parsed_data['type']== 'summarizeContent'):
        data = parsed_data['data']
        print(data)
        await summariseChatBlocks(data['messageIDs'], data['summaryID'])
    elif parsed_data["type"] == "indexdoc_start":
        await handle_indexdoc_start(parsed_data["data"])
    elif parsed_data["type"] == "indexdoc_chunk":
        await handle_indexdoc_chunk(parsed_data["data"])
    elif parsed_data["type"] == "indexdoc_end":
        await handle_indexdoc_end(parsed_data["data"])
    
    if(parsed_data["type"] == '__ping__'):
        # print('pong')
        await websocket.send(json.dumps({'event':'__pong__'}))
    if(parsed_data["type"] == 'ssoComplete'):
        print('ssoComplete called by html template.')
        print(parsed_data['payload'])
        await app.redis.set('userID', parsed_data['payload']['userID'])
        await app.redis.set('userName', parsed_data['payload']['userName'])
        await app.redis.set('authorised', parsed_data['payload']['authorised'])

        
        await websocket.send(json.dumps({'event':'ssoComplete', 'payload': {
            'userID': parsed_data['payload']['userID'],
            'userName': parsed_data['payload']['userName'],
            'authorised': parsed_data['payload']['authorised']
            }}))
        


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
    data = {
        'userID': file_metadata['userID'],
        'file_content': file_content,
        'file_name': file_metadata['file_name'],
        'file_type': file_metadata['file_type'],
        'sessionID': file_metadata['sessionID'],
        'tempKey': file_metadata['tempKey'],
        'indexType': file_metadata['indexType'],
        'document_type': file_metadata['document_type'],
    }

    indexRecord = await indexDocument(data)
    if indexRecord:
        payload = {
            'tempKey': data['tempKey'],
            'newCartridge': indexRecord.blob,
        }
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    await asyncio.create_task(handleIndexQuery(indexRecord.key, 'Give this document a short summary.'))

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
    os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'
    asyncio.run(serve(app, config))

    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    # app.run(host="127.0.0.1", port=5500) 
