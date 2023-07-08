import os
import asyncio
import json
import base64

from quart import request, jsonify, url_for, session, render_template
from quart_session import Session
from hypercorn.config import Config
from hypercorn.asyncio import serve
import stripe
import secrets
from random_word import RandomWords

from appHandler import app, websocket
from sessionHandler import novaSession, novaConvo,current_loadout
from nova import initialise_conversation, initialiseCartridges, loadCartridges, runCartridges
from chat import handle_message, user_input
from cartridges import addCartridgePrompt,update_cartridge_field, updateContentField,get_cartridge_list, add_existing_cartridge
from gptindex import indexDocument, handleIndexQuery
from googleAuth import logout, check_credentials,requestPermissions
from prismaHandler import prismaConnect, prismaDisconnect
from debug import eZprint
from memory import summariseChatBlocks,get_summary_children_by_key
from keywords import get_summary_from_keyword, get_summary_from_insight
from loadout import add_loadout, get_loadouts, set_loadout, delete_loadout, set_read_only,set_loadout_title, update_loadout_field,clear_loadout, add_loadout_to_session
from tokens import update_coin_count
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
    novaConvo[convoID]['userName'] = novaSession[sessionID]['userName']
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

stripe.api_key = os.getenv('STRIPE_API')
endpoint_secret = 'whsec_...'

payment_requests = {}

@app.route('/createCheckoutSession', methods=['GET'])
def createCheckoutSession():
    print('create-checkout-session route hit')
    # quantity = request.form.get('quantity', 1)
    domain_url = os.getenv('NOVA_SERVER')

    try:
        # Create new Checkout Session for the order
        # Other optional params include:
        # [billing_address_collection] - to display billing address details on the page
        # [customer] - if you have an existing Stripe Customer ID
        # [payment_intent_data] - lets capture the payment later
        # [customer_email] - lets you prefill the email input in the form
        # [automatic_tax] - to automatically calculate sales tax, VAT and GST in the checkout page
        # For full details see https://stripe.com/docs/api/checkout/sessions/create

        # ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param
        checkout_session = stripe.checkout.Session.create(
            success_url=domain_url + '/paymentSuccess?session_id={CHECKOUT_SESSION_ID}',
            # cancel_url=domain_url + '/canceled.html',
            mode='payment',
            # automatic_tax={'enabled': True},
            line_items=[{
                'price': os.getenv('250_NOVA'),
                'quantity': 1,
            }]
        )
        print(checkout_session)
        sessionID = app.session.get('sessionID')    
        userID = novaSession[sessionID]['userID']
        payment_requests[checkout_session.id] = {'status': 'pending', 'userID': userID}

        # return redirect(checkout_session.url, code=303)
        print(checkout_session.url)

        return jsonify({'checkout_url': checkout_session.url})
    
    except Exception as e:
        return jsonify(error=str(e)), 403

@app.route('/paymentSuccess', methods=['GET'])
async def paymentSuccess():
    print('paymentSuccess route hit')
    sessionID = app.session.get('sessionID')    
    userID = novaSession[sessionID]['userID']
    payment_request = payment_requests[request.args.get('session_id')]
    payment_request['status'] = 'success'
    app.session.modified = True
    return await render_template('close_complete.html')


@app.websocket('/ws')
async def ws():
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):

    if(parsed_data['type'] == 'login'):
        eZprint('login route hit')
        print(app.session)
        
        sessionID = parsed_data['sessionID']
        requestedScopes = ['https://www.googleapis.com/auth/userinfo.profile']
        loginURL = await requestPermissions( requestedScopes, sessionID )
        await websocket.send(json.dumps({'event':'open_auth_url', 'loginURL': loginURL}))

    if(parsed_data['type'] == 'docAuthRequest'):
        eZprint('googleAuth')
        sessionID = parsed_data['sessionID']    
        authUrl = await requestPermissions( ['https://www.googleapis.com/auth/documents.readonly'], sessionID )
        await websocket.send(json.dumps({'event':'open_doc_url', 'loginURL': authUrl}))


    if(parsed_data['type']=='createCheckoutSession'):
        domain_url = os.getenv('NOVA_SERVER')
        checkout_session = stripe.checkout.Session.create(
            success_url=domain_url + '/paymentSuccess?session_id={CHECKOUT_SESSION_ID}',
            # cancel_url=domain_url + '/canceled.html',
            mode='payment',
            # automatic_tax={'enabled': True},
            line_items=[{
                'price': os.getenv('250_NOVA'),
                'quantity': 1,
            }]
        )
        print(checkout_session)
        sessionID = app.session.get('sessionID')    
        userID = novaSession[sessionID]['userID']
        payment_requests[checkout_session.id] = {'status': 'pending', 'userID': userID}

        # return redirect(checkout_session.url, code=303)
        print(checkout_session.url)
        await websocket.send(json.dumps({'event':'checkout_url', 'payload': checkout_session.url}))
        while payment_requests[checkout_session.id]['status'] == 'pending':
            await asyncio.sleep(1)
        await websocket.send(json.dumps({'event':'paymentSuccess', 'payload': True}))
        await update_coin_count(userID, -250)

    if(parsed_data['type'] == 'request_loadouts'):
        eZprint('request_loadouts route hit')
        convoID = parsed_data['data']['convoID']
        await get_loadouts(convoID)
        params = {}
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']
        print(parsed_data['data'])

        await initialise_conversation(convoID, params)
        await initialiseCartridges(convoID)
        
    if(parsed_data['type'] == 'requestCartridges'):
        convoID = parsed_data['data']['convoID']
        eZprint('requestCartridges route hit')
        params = {}
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']
        print(parsed_data['data'])
        await initialise_conversation(convoID, params)
        await initialiseCartridges(convoID)

    if(parsed_data['type'] == 'sendMessage'):
        eZprint('handleInput called')
        await user_input(parsed_data['data'])
    if(parsed_data['type']== 'updateCartridgeField'):
        # print(parsed_data['data']['fields'])
        convoID = parsed_data['data']['convoID']
        loadout = None
        if convoID in current_loadout:
            loadout = current_loadout[convoID]
        await update_cartridge_field(parsed_data['data'], loadout)
    if(parsed_data['type']== 'updateContentField'):
        await updateContentField(parsed_data['data'])
    if(parsed_data['type']== 'newPrompt'):
        loadout = None
        convoID = parsed_data['data']['convoID']
        if convoID in current_loadout:
            loadout = current_loadout[convoID]
        await addCartridgePrompt(parsed_data['data'], loadout)
    if(parsed_data['type']== 'requestDocIndex'):
        data = parsed_data['data']
        convoID = data['convoID']
        loadout = None
        if convoID in current_loadout:
            loadout = current_loadout[convoID]
        if 'gDocID' in data:
            eZprint('indexing gDoc')
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
                'convoID': data['convoID'],
                'userID': data['userID'],
            }
            await asyncio.create_task(handleIndexQuery(queryPackage,loadout))
    if(parsed_data['type']== 'queryIndex'):
        data = parsed_data['data']
        convoID = data['convoID']
        loadout = None
        if convoID in current_loadout:
            loadout = current_loadout[convoID]
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
        convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']
        await add_loadout(loadout, convoID)


    if(parsed_data['type'] == 'set_loadout'):
        eZprint('set_loadout route hit')
        convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']
        await set_loadout(loadout, convoID)
        await runCartridges(convoID, loadout)

    if(parsed_data['type'] == 'loadout_referal'):
        eZprint('loadout_referal route hit')
        convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']    
        params = parsed_data['data']['params']
        await initialise_conversation(convoID, params)
        await set_loadout(loadout, convoID, True)
        await add_loadout_to_session(loadout, convoID)
        await runCartridges(convoID, loadout)
        
    if(parsed_data['type']=='delete_loadout'):
        eZprint('delete_loadout route hit')
        convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']
        await delete_loadout(loadout, convoID)

    if(parsed_data['type']=='clear_loadout'):
        eZprint('clear_loadout route hit')
        convoID = parsed_data['data']['convoID']
        await clear_loadout(convoID)
        await loadCartridges(convoID)
        await runCartridges(convoID)

    if(parsed_data['type'] == 'set_read_only'):
        eZprint('read_only route hit')
        loadout = parsed_data['data']['loadout']
        convoID = parsed_data['data']['convoID']
        read_only = parsed_data['data']['read_only']
        await set_read_only(loadout, read_only)

    if(parsed_data['type'] == 'set_title'):
        eZprint('update_title route hit')
        loadout = parsed_data['data']['loadout']
        convoID = parsed_data['data']['convoID']
        title = parsed_data['data']['title']
        await set_loadout_title(loadout, title)
        

    if(parsed_data['type']=='update_loadout_field'):
        eZprint('update_loadout_field route hit')
        loadout = parsed_data['data']['loadout']
        convoID = parsed_data['data']['convoID']
        field = parsed_data['data']['field']
        value = parsed_data['data']['value']
        await update_loadout_field(loadout, field, value)

    if(parsed_data['type']=='request_cartridge_list'):
        eZprint('request_cartridge_list route hit')
        convoID = parsed_data['data']['convoID']
        await get_cartridge_list(convoID)

    if(parsed_data['type']=='addExistingCartridge'):
        eZprint('addExistingCartridge route hit')
        convoID = parsed_data['data']['convoID']
        # cartridge = parsed_data['data']['cartridge']
        loadout = None
        if convoID in current_loadout:
            loadout = current_loadout[convoID]
        await add_existing_cartridge(parsed_data['data'],loadout)

    if(parsed_data['type']=='request_content_children'):
        eZprint('request content route hit')
        print(parsed_data['data'])
        convoID = parsed_data['data']['convoID']
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

        if convoID in current_loadout:
            loadout = current_loadout[convoID]

        if type == 'summary':
            await get_summary_children_by_key(key, convoID, cartKey, client_loadout)
        elif type == 'keyword':
            await get_summary_from_keyword(key, convoID, cartKey, client_loadout, target_loadout, True)
        elif type == 'insight':
            await get_summary_from_insight(key, convoID, cartKey, client_loadout, target_loadout, True)


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

    convoID = data['convoID']
    client_loadout = None
    if convoID in current_loadout:
        client_loadout = current_loadout[convoID]
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
        'convoID': data['convoID'],
        'userID': data['userID'],
    }
    convoID = data['convoID']

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
