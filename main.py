import os
import asyncio
import json
import base64

from quart import request, jsonify, url_for, session
from quart_session import Session
from hypercorn.config import Config
from hypercorn.asyncio import serve

import secrets
from random_word import RandomWords

from appHandler import app, websocket
from sessionHandler import novaSession, novaConvo
from nova import initialiseCartridges, addCartridgePrompt, handleChatInput, handleIndexQuery, updateCartridgeField, summariseChatBlocks, updateContentField
from gptindex import indexDocument
from googleAuth import logout, check_credentials,requestPermissions
from prismaHandler import prismaConnect, prismaDisconnect
from debug import eZprint

app.session = session
Session(app)
r = RandomWords()

@app.route("/")
async def index():
    return "welcome to the inne (dex)!"

@app.route("/hello")
async def hello():
    return "Hello, World!"

@app.before_serving
async def startup():
    await prismaConnect()
    eZprint("Connected to Prisma")

@app.after_serving
async def shutdown():
    await prismaDisconnect()
    eZprint("Disconnected to Prisma")

@app.before_request
def make_session_permanent():

    app.session.permanent = True
    eZprint("Make session permanent")

@app.route("/startsession", methods=['POST'])
async def startsession():

    eZprint('start-session route hit')
    print(app.session)

    payload = await request.get_json()

    if app.session.get('sessionID') is None:
        
        eZprint('sessionID not found, creating new session')

        sessionID = secrets.token_bytes(8).hex()
        app.session['sessionID'] = sessionID
        novaSession[sessionID] = {}
        novaSession[sessionID]['profileAuthed'] = False
        novaSession[sessionID]['docsAuthed'] = False
        novaSession[sessionID]['userName'] = 'Guest'
        novaSession[sessionID]['userID'] = 'guest-'+sessionID    

    sessionID = app.session.get('sessionID')    
    convoID = secrets.token_bytes(4).hex()
    # setting convo specific vars easier to pass around
    novaConvo[convoID] = {}
    novaConvo[convoID]['userID'] = novaSession[sessionID]['userID']

    app.session['convoID'] = convoID

    # means can cross reference back to main session stuff
    novaSession[sessionID]['convoID'] = convoID
    novaConvo[convoID]['sessionID'] = sessionID

    await check_credentials(sessionID)

    payload = {
        'sessionID': sessionID,
        'convoID': convoID,
        'profileAuthed' : novaSession[sessionID]['profileAuthed'],
        'docsAuthed' : novaSession[sessionID]['docsAuthed'],
        'userID': novaSession[sessionID]['userID'],
        'userName': novaSession[sessionID]['userName'],
    }

    eZprint('Payload and session updated')
    print(payload)
    print(app.session)

    app.session.modified = True
    return jsonify(payload)

@app.route('/login', methods=['GET'])
async def login():

    eZprint('login route hit')
    print(app.session)
    
    sessionID = app.session.get('sessionID')
    requestedScopes = ['https://www.googleapis.com/auth/userinfo.profile']
    loginURL = await requestPermissions( requestedScopes, sessionID )

    app.session.modified = True
    return jsonify({'loginURL': loginURL})

@app.route('/authRequest', methods=['GET'])
async def authRequest():
    eZprint('googleAuth')
    sessionID = app.session.get('sessionID')    
    authUrl = await requestPermissions( ['https://www.googleapis.com/auth/documents.readonly'], sessionID )
    app.session.modified = True
    return jsonify({'loginURL': authUrl})

@app.route('/awaitCredentialRequest', methods=['GET'])
async def awaitCredentialRequest():
    app.session.modified = True
    sessionID = app.session.get('sessionID')    
    requesting = novaSession[sessionID]['requesting']
    while requesting:
        print('awaiting credential request status ' + str(requesting))
        await asyncio.sleep(1)
        requesting = novaSession[sessionID]['requesting']
        credentialState = {
            'requesting': requesting,
        }
    else:
        credentialState = {
        'requesting': requesting,
        'docsAuthed': novaSession[sessionID]['docsAuthed'],
        'profileAuthed': novaSession[sessionID]['profileAuthed'],
    }
    return jsonify(credentialState)

@app.route('/requestLogout', methods=['GET'])
async def requestLogout():
    eZprint('requestLogout route hit')
    sessionID = app.session.get('sessionID')    

    logoutStatus = await logout(sessionID)    
    app.session.modified = True
    return jsonify({'logout': logoutStatus})

@app.websocket('/ws')
async def ws():
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):
    if(parsed_data['type'] == 'requestCartridges'):
        convoID = parsed_data['data']['convoID']
        eZprint('requestCartridges route hit')
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
            queryPackage = {
                'query': 'Give this document a short summary.',
                'cartKey': indexRecord.key,
                'convoID': data['convoID'],
                'userID': data['userID'],
            }
            await asyncio.create_task(handleIndexQuery(queryPackage))
    if(parsed_data['type']== 'queryIndex'):
        data = parsed_data['data']
        await asyncio.create_task(handleIndexQuery(data))
    if(parsed_data['type']== 'summarizeContent'):
        data = parsed_data['data']
        await summariseChatBlocks(parsed_data['data'])
    elif parsed_data["type"] == "indexdoc_start":
        print('indexdoc_start')
        print(parsed_data["data"])
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
    queryPackage = {
        'query': 'Give this document a short summary.',
        'cartKey': indexRecord.key,
        'convoID': data['convoID'],
        'userID': data['userID'],
    }
    await asyncio.create_task(handleIndexQuery(queryPackage))

    # Remove the stored file chunks upon completion
    del file_chunks[tempKey]

if __name__ == '__main__':

    host=os.getenv("HOST", default='0.0.0.0')
    port=int(os.getenv("PORT", default=5000))
    config = Config()
    config.bind = [str(host)+":"+str(port)]  # As an example configuration setting
    os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'
    asyncio.run(serve(app, config))
    

    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    # app.run(host="127.0.0.1", port=5500) 
