import os
from quart import request, jsonify, url_for, session
from quart_session import Session
import secrets
from hypercorn.config import Config
from hypercorn.asyncio import serve
from appHandler import app, websocket
import asyncio
import json
import base64
from nova import initialiseCartridges, prismaConnect, prismaDisconnect, addCartridgePrompt, handleChatInput, handleIndexQuery, updateCartridgeField, eZprint, summariseChatBlocks, updateContentField
from gptindex import indexDocument
from googleAuth import login, silent_check_login, logout, check_credentials,requestPermissions

app.session = session
Session(app)

@app.route("/")
async def index():
    return "welcome to the inne (dex)!"

@app.route("/hello")
async def hello():

    return "Hello, World!"

@app.before_serving
async def startup():
    # session.permanent = True

    await prismaConnect()

    # await googleAuthHandler()

@app.after_serving
async def shutdown():
    await prismaDisconnect()
    eZprint("Disconnected from Prisma")

@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route("/startsession", methods=['POST'])
async def startsession():
    eZprint('start-session route hit')
    payload = await request.get_json()
    if app.session.get('sessionID') is None:
        sessionID = secrets.token_bytes(4).hex()
        app.session['sessionID'] = sessionID
    convoID = secrets.token_bytes(4).hex()
    app.session['convoID'] = convoID
    authorised = await check_credentials()
    payload = {
        'profileAuthed' : app.session.get('profileAuthed'),
        'docsAuthed' : app.session.get('docsAuthed'),
        'userID': app.session.get('userID'),
        'userName': app.session.get('userName'),
        'convoID': convoID,
    }
    print(payload)
    # print(app.session)
    app.session.modified = True
    return jsonify(payload)

@app.route('/SSO', methods=['GET'])
async def SSO():
    eZprint('SSO route hit')
    # print(app.session)
    scopes = ['https://www.googleapis.com/auth/userinfo.profile']
    loginURL = await requestPermissions( scopes )
    app.session.modified = True
    return jsonify({'loginURL': loginURL})

@app.route('/authRequest', methods=['GET'])
async def authRequest():
    eZprint('googleAuth')
    authUrl = await requestPermissions( ['https://www.googleapis.com/auth/documents.readonly'] )
    app.session.modified = True
    return jsonify({'loginURL': authUrl})

@app.route('/awaitCredentialRequest', methods=['GET'])
async def awaitCredentialRequest():
    app.session.modified = True

    print('awaitCredentialRequest called')
    print(app.session.get('requesting'))
    requesting = app.session.get('requesting')
    if requesting:
        print('awaiting credential request status ' + str(requesting))
        await asyncio.sleep(1)
        credentialState = {
            'requesting': requesting,
        }
    else:
        credentialState = {
        'requesting': requesting,
        'docsAuthed': app.session.get('docsAuthed'),
        'profileAuthed': app.session.get('profileAuthed'),
    }
    return jsonify(credentialState)

@app.route('/requestLogout', methods=['GET'])
async def requestLogout():
    eZprint('requestLogout route hit')
    # print(app.session)
    logoutStatus = await logout()    
    app.session.modified = True
    return jsonify({'logout': logoutStatus})


@app.route('/getDebug', methods=['GET'])
async def getDebug():
    print('state is ' + str(app.session.get('state')))
    return jsonify({'debugText': app.session.get('state')})



# @app.route('/requestCartridges', methods=['POST'])
# async def requestCartridges():
#     eZprint('requestCartridges route hit')
#     print(app.session)
#     payload = await request.get_json()
#     convoID = payload['convoID'] 
#     print(payload)
#     await initialiseCartridges(convoID)
#     return jsonify({'status': 'success'})

@app.websocket('/ws')
async def ws():
    eZprint('ws route hit')
    print(app.session.get('sessionID'))
    print(app.session.get('convoID'))
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        print(parsed_data)
        app.session.modified = True

        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):
    if(parsed_data['type'] == 'getDebug'):
        print('state is ' + str(app.session.get('state')))
        await websocket.send_json({'debugText': app.session.get('state')})
    if(parsed_data['type'] == 'requestCartridges'):
        eZprint('requestCartridges route hit')
        # print(app.session)
        print(parsed_data['data'])
        convoID = parsed_data['data']['convoID'] 
        await initialiseCartridges(convoID)
    if(parsed_data['type'] == 'sendMessage'):
        eZprint('handleInput called')
        await handleChatInput(parsed_data['data'])
    if(parsed_data['type']== 'updateCartridgeField'):
        print(parsed_data['data']['fields'])
        await updateCartridgeField(parsed_data['data'])
    if(parsed_data['type']== 'updateContentField'):
        await updateContentField(parsed_data['data'])
    if(parsed_data['type']== 'newPrompt'):
        await addCartridgePrompt(parsed_data['data'])
    if(parsed_data['type']== 'requestDocIndex'):
        data = parsed_data['data']
        convoID = data['convoID']
        if 'gDocID' in data:
            eZprint('indexing gDoc')
            # print(data)
            indexRecord = await asyncio.create_task(indexDocument(data))
            if indexRecord:
                request = {
                    'tempKey': data['tempKey'],
                    'newCartridge': indexRecord.blob,
                }
            await websocket.send(json.dumps({'event':'updateTempCart', 'payload':request}))
            await asyncio.create_task(handleIndexQuery(convoID, indexRecord.key, 'Give this document a short summary.'))
    if(parsed_data['type']== 'queryIndex'):
        data = parsed_data['data']
        await asyncio.create_task(handleIndexQuery(data['convoID'], data['cartKey'], data['query']))
    if(parsed_data['type']== 'summarizeContent'):
        data = parsed_data['data']
        print(data)
        await summariseChatBlocks(data['convoID'], data['messageIDs'], data['summaryID'])
    elif parsed_data["type"] == "indexdoc_start":
        await handle_indexdoc_start(parsed_data["data"])
    elif parsed_data["type"] == "indexdoc_chunk":
        await handle_indexdoc_chunk(parsed_data["data"])
    elif parsed_data["type"] == "indexdoc_end":
        await handle_indexdoc_end(parsed_data["data"])
    if(parsed_data["type"] == '__ping__'):
        # print('pong')
        await websocket.send(json.dumps({'event':'__pong__'}))
    # if(parsed_data["type"] == 'setModel'):
    #     print('setModel called by html template.')
    #     print(parsed_data['payload'])
    #     await app.redis.set('model', parsed_data['payload']['model'])
    #     await websocket.send(json.dumps({'event':'setModel', 'payload': {
    #         'model': parsed_data['payload']['model']
    #         }}))
    if(parsed_data["type"] == 'authCompletePing'):
        print('authCompletePing called by html template.')
        print(parsed_data['payload'])
        app.session['requesting'] = False
     

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
        'convoID': file_metadata['convoID'],
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
    await asyncio.create_task(handleIndexQuery(data['convoID'], indexRecord.key, 'Give this document a short summary.'))

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
