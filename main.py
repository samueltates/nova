import os
import asyncio
import json
import base64

from quart import request, jsonify, url_for, session, render_template, redirect, send_file
from quart_session import Session
from hypercorn.config import Config
from hypercorn.asyncio import serve
from datetime import datetime
import stripe
import secrets
from random_word import RandomWords

from appHandler import app, websocket
from sessionHandler import novaSession, novaConvo,current_loadout, current_config
from nova import initialise_conversation, initialiseCartridges, loadCartridges, runCartridges
from chat import handle_message, user_input
from convos import get_loadout_logs,  start_new_convo, get_loadout_logs, set_convo, handle_convo_switch
from cartridges import addCartridgePrompt,update_cartridge_field, updateContentField,get_cartridge_list, add_existing_cartridge, search_cartridges, available_cartridges
from gptindex import indexDocument, handleIndexQuery
from googleAuth import logout, check_credentials,requestPermissions
from prismaHandler import prismaConnect, prismaDisconnect
from debug import eZprint
from user import set_subscribed, get_subscribed
from memory import summariseChatBlocks,get_summary_children_by_key
from keywords import get_summary_from_keyword, get_summary_from_insight
from loadout import add_loadout, get_loadouts, set_loadout, delete_loadout, set_read_only,set_loadout_title, update_loadout_field,clear_loadout, add_loadout_to_session
from tokens import update_coin_count
from file_handling.fileHandler import handle_file_start, handle_file_chunk, handle_file_end
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
    print(app.config)
    eZprint("Connected to Prisma")

@app.after_serving
async def shutdown():
    await prismaDisconnect()
    eZprint("Disconnected to Prisma")

@app.before_request
def make_session_permanent():

    app.session.permanent = True
    # eZprint("Make session permanent")


@app.route('/download_video', methods=['GET'])
async def download_video():
    video_name = request.args.get('video_name')
    return await send_file(video_name, as_attachment=True)

@app.route("/startsession", methods=['POST'])
async def startsession():
    eZprint('start-session route hit')
    # print(app.session)
    # print(app.config)

    # print(request)
    payload = await request.get_json()
    browserSession = payload['sessionID']
    # print(payload)
    show_onboarding = False
    sessionID = None
    sessionID = app.session.get('sessionID')    
    if sessionID is None:
        sessionID = browserSession
    if sessionID is None or sessionID not in novaSession:
        
        eZprint('sessionID not found, creating new session')

        sessionID = secrets.token_bytes(8).hex()
        app.session['sessionID'] = sessionID
        novaSession[sessionID] = {}
        novaSession[sessionID]['profileAuthed'] = False
        novaSession[sessionID]['docsAuthed'] = False
        novaSession[sessionID]['userName'] = 'Guest'
        novaSession[sessionID]['userID'] = 'guest-'+sessionID    
        novaSession[sessionID]['new_login'] = True
        novaSession[sessionID]['subscribed'] = False

        show_onboarding = True
        

    # convoID = secrets.token_bytes(4).hex()
    # setting convo specific vars easier to pass around
    
    # novaConvo[convoID] = {}
    # novaConvo[convoID]['userName'] = novaSession[sessionID]['userName']
    # novaConvo[convoID]['userID'] = novaSession[sessionID]['userID']

    # app.session['convoID'] = convoID

    # means can cross reference back to main session stuff
    # novaSession[sessionID]['convoID'] = convoID
    # novaConvo[convoID]['sessionID'] = sessionID

    await check_credentials(sessionID)
    if novaSession[sessionID]['profileAuthed']:
        if novaSession[sessionID]['new_login'] == True:
            novaSession[sessionID]['new_login'] = False
            show_onboarding = True
        novaSession[sessionID]['subscribed'] = await get_subscribed(novaSession[sessionID]['userID'])

    payload = {
        'sessionID': sessionID,
        # 'convoID': convoID,
        'profileAuthed' : novaSession[sessionID]['profileAuthed'],
        'docsAuthed' : novaSession[sessionID]['docsAuthed'],
        'userID': novaSession[sessionID]['userID'],
        'userName': novaSession[sessionID]['userName'],
        'show_onboarding': show_onboarding,
        'subscribed': novaSession[sessionID]['subscribed'],
    }

    # eZprint('Payload and session updated')
    print(payload)
    # print(app.session)

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

# @app.route('/requestLogout', methods=['GET'])
# async def requestLogout():
#     eZprint('requestLogout route hit')
#     sessionID = app.session.get('sessionID')    

#     logoutStatus = await logout(sessionID)    
#     app.session.modified = True
#     return jsonify({'logout': logoutStatus})

stripe.api_key = os.getenv('STRIPE_API')
endpoint_secret = 'whsec_...'

payment_requests = {}


@app.route('/paymentSuccess', methods=['GET'])
async def paymentSuccess():
    print('paymentSuccess route hit')
    checkout_session = request.args.get('session_id')
    sessionID = payment_requests[checkout_session]['sessionID']
    payment_request = payment_requests[request.args.get('session_id')]
    payment_request['status'] = 'success'
    app.session.modified = True
    return redirect(os.environ.get('NOVAHOME'))


@app.websocket('/ws')
async def ws():
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):

    if(parsed_data['type'] == 'login'):
        eZprint('login route hit')
        # print(app.session)
        
        sessionID = parsed_data['sessionID']
        requestedScopes = ['https://www.googleapis.com/auth/userinfo.profile']
        loginURL = await requestPermissions( requestedScopes, sessionID )
        await websocket.send(json.dumps({'event':'open_auth_url', 'loginURL': loginURL}))

    if(parsed_data['type'] == 'docAuthRequest'):
        eZprint('googleAuth')
        sessionID = parsed_data['sessionID']    
        authUrl = await requestPermissions( ['https://www.googleapis.com/auth/documents.readonly'], sessionID )
        await websocket.send(json.dumps({'event':'open_doc_url', 'loginURL': authUrl}))

    if(parsed_data['type'] == 'awaitCredentialRequest'):

        app.session.modified = True
        sessionID = parsed_data['sessionID']    
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
        await websocket.send(json.dumps({'event':'credentialState', 'payload': credentialState}))

    if(parsed_data['type']== 'requestLogout'):
        eZprint('requestLogout route hit')
        sessionID = parsed_data['sessionID']    

        app.session.pop('sessionID') 
        logoutStatus = await logout(sessionID)    
        app.session.modified = True
        await websocket.send(json.dumps({'event':'logout', 'payload': logoutStatus}))

    if(parsed_data['type']=='createCheckoutSession'):
        domain_url = os.getenv('NOVA_SERVER')
        amount = parsed_data['amount']
        if 'subscribe' in parsed_data and parsed_data['subscribe']:
            print(parsed_data)

            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/paymentSuccess?session_id={CHECKOUT_SESSION_ID}',
                # cancel_url=domain_url + '/canceled.html',
                mode='subscription',
                # automatic_tax={'enabled': True},
                line_items=[{
                    'price': os.getenv('NC_SUB'+str(amount)),
                    'quantity': 1,
                }]
            )
        else:
                
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/paymentSuccess?session_id={CHECKOUT_SESSION_ID}',
                # cancel_url=domain_url + '/canceled.html',
                mode='payment',
                # automatic_tax={'enabled': True},
                line_items=[{
                    'price': os.getenv('NC'+str(amount)),
                    'quantity': 1,
                }]
            )
            # print(checkout_session)
        sessionID = parsed_data['sessionID']
        userID = novaSession[sessionID]['userID']
        payment_requests[checkout_session.id] = {'status': 'pending', 'userID': userID, 'sessionID': sessionID}
        # return redirect(checkout_session.url, code=303)
        # print(checkout_session.url)
        await websocket.send(json.dumps({'event':'checkout_url', 'payload': checkout_session.url}))
        while payment_requests[checkout_session.id]['status'] == 'pending':
            await asyncio.sleep(1)
        await websocket.send(json.dumps({'event':'paymentSuccess', 'payload': True}))
        await update_coin_count(userID, -amount)
        await set_subscribed(userID, True)

    if(parsed_data['type']== 'add_convo'):
        convoID = secrets.token_bytes(4).hex()
        sessionID = parsed_data['sessionID']
        loadout = current_loadout[sessionID]
        # await initialise_conversation(sessionID, convoID, params)
        convoID_full = sessionID +'-'+convoID +'-'+ str(loadout)
        novaSession[sessionID]['convoID'] = convoID_full
        novaConvo[convoID_full] = {}
        novaConvo[convoID_full]['sessionID'] = sessionID
        session ={
            'sessionID' : convoID_full,
            'convoID' : convoID_full,
            'date' : datetime.now().strftime("%Y%m%d%H%M%S"),
            'summary': "new conversation",
        }
        await initialise_conversation(sessionID, convoID_full)
        await websocket.send(json.dumps({'event':'add_convo', 'payload': session}))    

    if(parsed_data['type'] == 'request_loadouts'):
        eZprint('request_loadouts route hit')
        sessionID = parsed_data['data']['sessionID']
        await get_loadouts(sessionID)
        await get_loadout_logs(sessionID)
        params = {}
        convoID = None      
        current_config[sessionID] = {}
        print( 'current loadout is ' + str(current_loadout[sessionID]))
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']

        # if 'fake-user' in params:
        #     if 'userID' in novaSession[sessionID]:
        #         if novaSession[sessionID]['userID'] != params['fake-user']:
        #             current_config[sessionID] = {}
        #             available_cartridges[sessionID] = {}
        #     userID = params['fake-user']
        #     novaSession[sessionID]['userID'] = userID
        #     novaSession[sessionID]['fake-user'] = True
        #     novaSession[sessionID]['profileAuthed'] = True

        convoID_full = await handle_convo_switch(sessionID)
        if not convoID_full:
            convoID_full = await start_new_convo(sessionID)
        await initialise_conversation(sessionID, convoID, params)
        await initialiseCartridges(sessionID)

    if(parsed_data['type'] == 'set_loadout'):
        eZprint('set_loadout route hit')
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        await set_loadout(loadout, sessionID)
        await get_loadout_logs(sessionID)

        convoID_full = await handle_convo_switch(sessionID)
        if not convoID_full:
            convoID_full = await start_new_convo(sessionID)

        await runCartridges(sessionID, loadout)

    if(parsed_data['type'] == 'loadout_referal'):
        eZprint('loadout_referal route hit')
        sessionID = parsed_data['data']['sessionID']
        # convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']    
        params = parsed_data['data']['params']
        await set_loadout(loadout, sessionID, True)
        await add_loadout_to_session(loadout, sessionID)
        await get_loadout_logs(sessionID)

        if sessionID in current_config and 'shared' in current_config[sessionID] and current_config[sessionID]['shared']:
            convoID_full = await handle_convo_switch(sessionID)
            if not convoID_full:
                convoID_full = await start_new_convo(sessionID)
        else:
            convoID_full = await start_new_convo(sessionID)
        await initialise_conversation(sessionID,convoID_full, params)
        await runCartridges(sessionID, loadout)
        
        
    if(parsed_data['type'] == 'requestCartridges'):
        convoID = parsed_data['data']['convoID']
        eZprint('requestCartridges route hit')
        params = {}
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']
        print(parsed_data['data'])
        await initialise_conversation(sessionID, convoID, params)
        await initialiseCartridges(sessionID)

    if(parsed_data['type'] == 'set_convo'):
        print('set convo called')
        # print(parsed_data['data'])
        requested_convoID = parsed_data['data']['requestedConvoID']
        sessionID = parsed_data['data']['sessionID']
        await set_convo(requested_convoID, sessionID)

    if(parsed_data['type'] == 'sendMessage'):
        eZprint('handleInput called')
        await user_input(parsed_data['data'])
    if(parsed_data['type']== 'updateCartridgeField'):
        # print(parsed_data['data']['fields'])
        sessionID = parsed_data['data']['sessionID']
        loadout = None
        if sessionID in current_loadout:
            loadout = current_loadout[sessionID]
        await update_cartridge_field(parsed_data['data'], loadout)
    if(parsed_data['type']== 'updateContentField'):
        await updateContentField(parsed_data['data'])
    if(parsed_data['type']== 'newPrompt'):
        loadout = None
        sessionID = parsed_data['data']['sessionID']
        if sessionID in current_loadout:
            loadout = current_loadout[sessionID]
        await addCartridgePrompt(parsed_data['data'], loadout)
    if(parsed_data['type']== 'requestDocIndex'):
        data = parsed_data['data']
        sessionID = data['sessionID']
        loadout = None
        if sessionID in current_loadout:
            loadout = current_loadout[sessionID]

            # print(data)
            indexRecord = await asyncio.create_task(indexDocument(data, loadout))
            if indexRecord:
                request = {
                    'tempKey': data['tempKey'],
                    'newCartridge': indexRecord.blob,
                }
            await websocket.send(json.dumps({'event':'updateTempCart', 'payload':request}))
            queryPackage = {
                'query': 'Give this document a short summary.',
                'cartKey': indexRecord.key,
                'sessionID': data['sessionID'],
                'userID': data['userID'],
            }
            await asyncio.create_task(handleIndexQuery(queryPackage,loadout))
    if(parsed_data['type']== 'queryIndex'):
        data = parsed_data['data']
        sessionID = data['sessionID']
        loadout = None
        if sessionID in current_loadout:
            loadout = current_loadout[sessionID]
        await asyncio.create_task(handleIndexQuery(data,loadout))
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
    elif parsed_data["type"] == "file_start":
        print('indexdoc_start')
        print(parsed_data["data"])
        await handle_file_start(parsed_data["data"])
    elif parsed_data["type"] == "file_chunk":
        await handle_file_chunk(parsed_data["data"])
    elif parsed_data["type"] == "file_end":
        await handle_file_end(parsed_data["data"])




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

    if(parsed_data['type'] == 'add_loadout'):
        eZprint('add_loadout route hit')
        print(parsed_data['data'])
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        await add_loadout(loadout, sessionID)
        convoID_full = await handle_convo_switch(sessionID)
        if not convoID_full:
            convoID_full = await start_new_convo(sessionID)



    if(parsed_data['type']=='delete_loadout'):
        eZprint('delete_loadout route hit')
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        await delete_loadout(loadout, sessionID)

    if(parsed_data['type']=='clear_loadout'):
        eZprint('clear_loadout route hit')
        sessionID = parsed_data['data']['sessionID']
        await clear_loadout(sessionID)
        await get_loadout_logs(sessionID)

        convoID_full = await handle_convo_switch(sessionID)
        if not convoID_full:
            convoID_full = await start_new_convo(sessionID)

        await loadCartridges(sessionID)
        await runCartridges(sessionID)

    if(parsed_data['type'] == 'set_read_only'):
        eZprint('read_only route hit')
        loadout = parsed_data['data']['loadout']
        sessionID = parsed_data['data']['sessionID']
        read_only = parsed_data['data']['read_only']
        await set_read_only(loadout, read_only)

    if(parsed_data['type'] == 'set_title'):
        eZprint('update_title route hit')
        loadout = parsed_data['data']['loadout']
        title = parsed_data['data']['title']
        await set_loadout_title(loadout, title)
        

    if(parsed_data['type']=='update_loadout_field'):
        eZprint('update_loadout_field route hit')
        loadout = parsed_data['data']['loadout']
        field = parsed_data['data']['field']
        value = parsed_data['data']['value']
        await update_loadout_field(loadout, field, value)

    if(parsed_data['type']=='request_cartridge_list'):
        eZprint('request_cartridge_list route hit')
        sessionID = parsed_data['data']['sessionID']
        await get_cartridge_list(sessionID)

    if(parsed_data['type']=='addExistingCartridge'):
        eZprint('addExistingCartridge route hit')
        sessionID = parsed_data['data']['sessionID']
        # cartridge = parsed_data['data']['cartridge']
        loadout = None
        if sessionID in current_loadout:
            loadout = current_loadout[sessionID]
        await add_existing_cartridge(parsed_data['data'],loadout)

    if(parsed_data['type']=='search_cartridges'):
        eZprint('search_cartridges route hit')
        print(parsed_data['data'])
        convoID = parsed_data['data']['convoID']
        sessionID = novaConvo[convoID]['sessionID']
        query = parsed_data['data']['query']
        await search_cartridges(query, sessionID)
    if(parsed_data['type']=='request_content_children'):
        eZprint('request content route hit')
        print(parsed_data['data'])
        sessionID = parsed_data['data']['sessionID']
        key = parsed_data['data']['key']
        cartKey = parsed_data['data']['cartKey']
        type = parsed_data['data']['type']
        if 'client-loadout' in parsed_data['data']:
            client_loadout = parsed_data['data']['client-loadout']
        else:
            client_loadout = None
        if 'target-loadout' in parsed_data['data']:
            target_loadout = parsed_data['data']['target-loadout']
        else:
            target_loadout = None

        if sessionID in current_loadout:
            loadout = current_loadout[sessionID]

        if type == 'summary':
            await get_summary_children_by_key(key, sessionID, cartKey, client_loadout)
        elif type == 'keyword':
            await get_summary_from_keyword(key, sessionID, cartKey, client_loadout, target_loadout, True)
        elif type == 'insight':
            await get_summary_from_insight(key, sessionID, cartKey, client_loadout, target_loadout, True)



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
        'sessionID': file_metadata['sessionID'],
        'userID': file_metadata['userID'],
        'file_content': file_content,
        'file_name': file_metadata['file_name'],
        'file_type': file_metadata['file_type'],
        'sessionID': file_metadata['sessionID'],
        'tempKey': file_metadata['tempKey'],
        'indexType': file_metadata['indexType'],
        'document_type': file_metadata['document_type'],
    }

    sessionID = data['sessionID']
    client_loadout = None
    if sessionID in current_loadout:
        client_loadout = current_loadout[sessionID]
    indexRecord = await indexDocument(data, client_loadout)
    # if indexRecord:
    #     payload = {
    #         'tempKey': data['tempKey'],
    #         'newCartridge': indexRecord.blob,
    #     }
    # await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    queryPackage = {
        'query': 'Give this document a short summary.',
        'cartKey': indexRecord.key,
        'sessionID': data['sessionID'],
        'userID': data['userID'],
    }
    sessionID = data['sessionID']

    await asyncio.create_task(handleIndexQuery(queryPackage, client_loadout))

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
