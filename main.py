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

from session.appHandler import app, websocket, openai_client
from session.sessionHandler import novaSession, novaConvo,current_loadout, current_config
from session.user import update_user_events, get_user_events, set_user_value,get_user_value
from core.nova import initialise_conversation, initialiseCartridges, loadCartridges, runCartridges
from chat.chat import handle_message, user_input, return_to_GPT
from chat.query import getModels
from core.convos import get_loadout_logs,  start_new_convo, get_loadout_logs, set_convo
from core.cartridges import retrieve_loadout_cartridges, addCartridge, update_cartridge_field, updateContentField,get_cartridge_list, add_existing_cartridge, search_cartridges, active_cartridges
from tools.gptindex import indexDocument, handleIndexQuery
from session.googleAuth import logout, check_credentials,requestPermissions
from session.prismaHandler import prismaConnect, prismaDisconnect
# from session.user import setTextToVoice, getTextToVoice
from tools.debug import eZprint, eZprint_anything
from session.user import set_subscribed, get_subscribed
from tools.memory import summariseChatBlocks,get_summary_children_by_key
from tools.keywords import get_summary_from_keyword, get_summary_from_insight
from core.loadout import add_loadout, get_loadouts, set_loadout, drop_loadout, set_read_only,set_loadout_title, update_loadout_field,clear_loadout, get_latest_loadout_convo, add_loadout_to_profile
from session.tokens import update_coin_count
from file_handling.fileHandler import handle_file_start, handle_file_chunk, handle_file_end
from file_handling.transcribe import handle_transcript_chunk, handle_transcript_end, setup_transcript_chunk
from version import __version__


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
    eZprint_anything(['start-session route hit', request], ['AUTH', 'INITIALISE'], line_break=True)
    payload = await request.get_json()
    browserSession = payload['sessionID']
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
        novaSession[sessionID]['user_name'] = 'Guest'
        novaSession[sessionID]['userID'] = 'guest-'+sessionID    
        novaSession[sessionID]['new_login'] = True
        novaSession[sessionID]['subscribed'] = False
        novaSession[sessionID]['TTV'] = False

        show_onboarding = True

    await check_credentials(sessionID)




    eZprint_anything(novaSession[sessionID], ['AUTH', 'INITIALISE'], message='novaSession[sessionID]')
    #checks each variable and sets default if not available (failsafe)
    if 'profileAuthed' not in novaSession[sessionID]:
        novaSession[sessionID]['profileAuthed'] = False
    if 'docsAuthed' not in novaSession[sessionID]:
        novaSession[sessionID]['docsAuthed'] = False
    if 'user_name' not in novaSession[sessionID]:
        novaSession[sessionID]['user_name'] = 'Guest'
    if 'userID' not in novaSession[sessionID]:
        novaSession[sessionID]['userID'] = 'guest-'+sessionID   
    if 'new_login' not in novaSession[sessionID]:
        novaSession[sessionID]['new_login'] = True
    if 'subscribed' not in novaSession[sessionID]:
        novaSession[sessionID]['subscribed'] = False
    if 'TTV' not in novaSession[sessionID]:
        novaSession[sessionID]['TTV'] = False


    if novaSession[sessionID]['profileAuthed']:
        if novaSession[sessionID]['new_login'] == True:
            novaSession[sessionID]['new_login'] = False
            show_onboarding = True
        
        novaSession[sessionID]['met_nova'] = await get_user_value(novaSession[sessionID]['userID'], 'met_nova')
        novaSession[sessionID]['subscribed'] = await get_subscribed(novaSession[sessionID]['userID'])
        novaSession[sessionID]['met_sam'] = await get_user_value(novaSession[sessionID]['userID'], 'met_sam')

    else :
        # novaSession[sessionID]['met_nova'] = False
        novaSession[sessionID]['met_sam'] = False
        # novaSession[sessionID]['subscribed'] = False
    payload = {
        'sessionID': sessionID,
        # 'convoID': convoID,
        'profileAuthed' : novaSession[sessionID]['profileAuthed'],
        'docsAuthed' : novaSession[sessionID]['docsAuthed'],
        'userID': novaSession[sessionID]['userID'],
        'user_name': novaSession[sessionID]['user_name'],
        'show_onboarding': show_onboarding,
        'subscribed': novaSession[sessionID]['subscribed'],
        'nova_version': __version__
    }

    # eZprint('Payload and session updated')
    eZprint_anything(payload, ['AUTH', 'INITIALISE'])
    # print(app.session)

    app.session.modified = True
    return jsonify(payload)

@app.route('/login', methods=['GET'])
async def login():

    eZprint('login route GET hit', ['AUTH'])
    print(app.session)
    
    sessionID = app.session.get('sessionID')
    requestedScopes = ['https://www.googleapis.com/auth/userinfo.profile']
    loginURL = await requestPermissions( requestedScopes, sessionID )

    app.session.modified = True
    return jsonify({'loginURL': loginURL})

@app.route('/authRequest', methods=['GET'])
async def authRequest():
    eZprint('googleAuth', ['AUTH'])
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
        eZprint('awaiting credential request status ' + str(requesting), ['AUTH'])
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
    eZprint('paymentSuccess route hit', ['PAYMENT'])
    checkout_session = request.args.get('session_id')
    sessionID = payment_requests[checkout_session]['sessionID']
    payment_request = payment_requests[request.args.get('session_id')]
    payment_request['status'] = 'success'
    app.session.modified = True
    return redirect(os.environ.get('NOVAHOME'))

@app.route('/paymentSuccessClient', methods=['GET'])
async def paymentSuccessClient():
    eZprint('paymentSuccessClient route hit', ['PAYMENT'])
    checkout_session = request.args.get('session_id')
    payment_request = payment_requests[request.args.get('session_id')]

    sessionID = payment_requests[checkout_session]['sessionID']
    return_url = request.args.get('return_url')
    file_to_download = request.args.get('file_to_download')
    payment_request['status'] = 'success'
    app.session.modified = True
    return redirect(return_url+'?file_to_download='+file_to_download)

@app.websocket('/ws')
async def ws():
    while True:
        data = await websocket.receive()
        parsed_data = json.loads(data)
        asyncio.create_task(process_message(parsed_data))

async def process_message(parsed_data):
    
    eZprint_anything(parsed_data, ['WEBSOCKET'], message='websocket hit') 
    ###AUTH BASED STUFF######
    if(parsed_data['type'] == 'login'):
        eZprint('login route hit', ['AUTH', 'INITIALISE'])
        # print(app.session)
        
        sessionID = parsed_data['sessionID']
        requestedScopes = ['https://www.googleapis.com/auth/userinfo.profile']
        loginURL = await requestPermissions( requestedScopes, sessionID )
        await websocket.send(json.dumps({'event':'open_auth_url', 'loginURL': loginURL}))

    if(parsed_data['type']== 'requestLogout'):
        eZprint('requestLogout route hit')
        sessionID = parsed_data['sessionID']    
        if app.session.get('sessionID'):
            app.session.pop('sessionID') 
        if sessionID in novaSession:
            novaSession.pop(sessionID)

        if sessionID in current_loadout:
            current_loadout.pop(sessionID)

        if sessionID in current_config:
            current_config.pop(sessionID)
            
        logoutStatus = await logout(sessionID)    
        app.session.modified = True
        await websocket.send(json.dumps({'event':'logout', 'payload': logoutStatus}))

    if(parsed_data['type'] == 'docAuthRequest'):
        eZprint('googleAuth', ['AUTH'])
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

    if(parsed_data['type'] == 'create_checkout_client'):
        domain_url = os.getenv('NOVA_SERVER')
        return_url = parsed_data['return_url']
        payment_type = parsed_data['payment_type']
        eZprint_anything(parsed_data, ['PAYMENT'])
        payment_ID = parsed_data['payment_ID']
        file_to_download = parsed_data['file_to_download']
        if payment_type == 'subscription':
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/paymentSuccessClient?session_id={CHECKOUT_SESSION_ID}&return_url='+return_url+'&file_to_download='+file_to_download,
                # cancel_url=domain_url + '/canceled.html',
                mode='subscription',
                # automatic_tax={'enabled': True},
                line_items=[{
                    'price': os.getenv('NC_SUB'+str(parsed_data['amount'])),
                    'quantity': 1,
                }]
            ) 

        else:
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/paymentSuccessClient?session_id={CHECKOUT_SESSION_ID}&return_url='+return_url+'&file_to_download='+file_to_download,
                # cancel_url=domain_url + '/canceled.html',
                mode='payment',
                # automatic_tax={'enabled': True},
                line_items=[{
                    'price': payment_ID,
                    'quantity': 1,
                }]
            )
        sessionID = parsed_data['sessionID']
        userID = novaSession[sessionID]['userID']
        payment_requests[checkout_session.id] = {'status': 'pending', 'userID': userID, 'sessionID': sessionID}
        
        await websocket.send(json.dumps({'event':'checkout_url', 'payload': checkout_session.url}))
        while payment_requests[checkout_session.id]['status'] == 'pending':
            await asyncio.sleep(1)
        await websocket.send(json.dumps({'event':'checkout_success', 'payload': True}))

            
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
        sessionID = parsed_data['sessionID']
        userID = novaSession[sessionID]['userID']
        payment_requests[checkout_session.id] = {'status': 'pending', 'userID': userID, 'sessionID': sessionID}
        await websocket.send(json.dumps({'event':'checkout_url', 'payload': checkout_session.url}))
        while payment_requests[checkout_session.id]['status'] == 'pending':
            await asyncio.sleep(1)
        await websocket.send(json.dumps({'event':'paymentSuccess', 'payload': True}))
        await update_coin_count(userID, -amount)
        await set_subscribed(userID, True)


    ## ALL LOADOUT CONVERSATION SETUP ####
    if(parsed_data['type'] == 'request_loadouts'):
        # gets loadouts available to user
        eZprint('request_loadouts route hit', ['LOADOUT', 'INITIALISE'], line_break=True)
        sessionID = parsed_data['data']['sessionID']
        params = {}
        # eZprint( 'current loadout is ' + str(current_loadout[sessionID]), ['LOADOUT', 'INITIALISE'])
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']
        userID = None

        latest_loadout = None
        if sessionID in novaSession:
            if 'userID' in novaSession[sessionID]:
                userID = novaSession[sessionID]['userID']
                if not 'met_nova' in novaSession[sessionID] or not novaSession[sessionID]['met_nova']:
                    await add_loadout_to_profile('7531ab40afd82ba4', userID)
                    novaSession[sessionID]['needs_meet_nova'] = False
                    await set_user_value(userID, 'met_nova', True)
                    await set_loadout('7531ab40afd82ba4', sessionID)
                    latest_loadout = '7531ab40afd82ba4'
                    await websocket.send(json.dumps({'event': 'set_loadout', 'payload': latest_loadout}))
                    await get_loadout_logs(latest_loadout, sessionID)

                    
              
        if not latest_loadout:
            latest_loadout = await get_loadouts(sessionID)
            if latest_loadout:
                await set_loadout(latest_loadout, sessionID)
            # else:
                # latest_loadout = '7531ab40afd82ba4'
            await websocket.send(json.dumps({'event': 'set_loadout', 'payload': latest_loadout}))
            await get_loadout_logs(latest_loadout, sessionID)

       
        if not 'met_sam' in novaSession[sessionID] or not novaSession[sessionID]['met_sam'] and latest_loadout == '7531ab40afd82ba4':
            # events = await get_user_events(userID)

            await websocket.send(json.dumps({'event': 'set_met_sam', 'payload':False}))

        # gets or creates conversation - should this pick up last?
        # convoID = await get_latest_loadout_convo(latest_loadout)
        # convoID = await get_latest_convo(userID)
        convoID = None
        if userID:
            convoID = await get_user_value(userID, 'latest_convo-' + latest_loadout)
        if not convoID:
            convoID = await start_new_convo(sessionID, latest_loadout)

        await set_convo(convoID, sessionID, latest_loadout)
        await retrieve_loadout_cartridges(latest_loadout, convoID)

        await initialise_conversation(sessionID, convoID, params)
        await initialiseCartridges(sessionID, convoID, latest_loadout)

        # async def handle_loadout_actions(sessionID, convoID, target_loadout):




    if(parsed_data['type'] == 'set_loadout'):
        eZprint('set_loadout route hit', ['LOADOUT', 'INITIALISE'], line_break=True)
        # sets to client specified loadout ... (or sets as active?)
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        userID = parsed_data['data']['userID']
        params = {}
        # eZprint( 'current loadout is ' + str(current_loadout[sessionID]), ['LOADOUT', 'INITIALISE'])
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']

        await set_loadout(loadout, sessionID)
        await get_loadout_logs(loadout, sessionID)

        # convoID = await get_latest_loadout_convo(loadout)
        convoID = await get_user_value(userID, 'latest_convo-' + loadout)
        if not convoID:
            convoID = await start_new_convo(sessionID, loadout)

        await set_convo(convoID, sessionID, loadout)
        await retrieve_loadout_cartridges(loadout, convoID)

        await initialise_conversation(sessionID, convoID, params)
        await runCartridges(sessionID, convoID, loadout)


    if(parsed_data['type'] == 'loadout_referal'):
        eZprint('loadout_referal route hit', ['LOADOUT'], line_break=True)
        sessionID = parsed_data['data']['sessionID']
        # convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']    
        params = parsed_data['data']['params']

        for key in params:
            if 'DEBUG' in key:
                os.environ[key] = params[key]

        eZprint('params set to ' + str(params), ['INITIALISE'])
        await get_loadouts(sessionID)
        await set_loadout(loadout, sessionID, True)
        # await add_loadout_to_session(loadout, sessionID)
        await get_loadout_logs(loadout, sessionID)
        
        # if sessionID in current_config and 'shared' in current_config[sessionID] and current_config[sessionID]['shared']:
        #     # convoID = await handle_convo_switch(sessionID)
        #     # if not convoID:
        #     convoID = await start_new_convo(sessionID)
        # else:
        convoID = await start_new_convo(sessionID, loadout)

        await retrieve_loadout_cartridges(loadout, convoID)
        await initialise_conversation(sessionID, convoID, params)
        await runCartridges(convoID, loadout)  

    if(parsed_data['type'] == 'add_loadout'):
        eZprint('add_loadout route hit', ['LOADOUT', 'INITIALISE'], line_break=True)
        # print(parsed_data['data'])
        convoID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        sessionID = parsed_data['data']['sessionID']
        await add_loadout(loadout, convoID)
        await get_loadout_logs(loadout, sessionID)
        # convoID = await handle_convo_switch(sessionID)
        # if not convoID:
        convoID = await start_new_convo(sessionID, loadout)
        await retrieve_loadout_cartridges(loadout, convoID)
        await initialise_conversation(sessionID, convoID)
        await runCartridges(convoID, loadout)  

    if(parsed_data['type']=='clear_loadout'):
        eZprint('clear_loadout route hit', ['LOADOUT'], line_break=True)
        params = {}
        # print( 'current loadout is ' + str(current_loadout[sessionID]))
        if 'params' in parsed_data['data']:
            params = parsed_data['data']['params']
        convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']
        sessionID = parsed_data['data']['sessionID']
        await clear_loadout(sessionID, convoID)
        await set_loadout(None, sessionID)
        await get_loadout_logs(None, sessionID)
        # gets or creates conversation - should this pick up last?
        # convoID = await get_latest_loadout_convo(sessionID)
        # if not convoID:
        convoID = await start_new_convo(sessionID, None)

        await initialise_conversation(sessionID, convoID, params)
        await initialiseCartridges(sessionID, convoID, None)


    if(parsed_data['type']== 'add_convo'):
        convoID = secrets.token_bytes(4).hex()
        sessionID = parsed_data['sessionID']
        loadout = current_loadout[sessionID]
        # await initialise_conversation(sessionID, convoID, params)
        convoID_full = sessionID +'-'+convoID +'-'+ str(loadout)
        novaSession[sessionID]['convoID'] = convoID_full
        novaConvo[convoID_full] = {}
        novaConvo[convoID_full]['sessionID'] = sessionID
        novaConvo[convoID_full]['loadout'] = loadout
        session ={
            'sessionID' : convoID_full,
            'convoID' : convoID_full,
            'date' : datetime.now().strftime("%Y%m%d%H%M%S"),
            'summary': "new conversation",
        }
        await websocket.send(json.dumps({'event':'add_convo', 'payload': session}))    
        await retrieve_loadout_cartridges(loadout, convoID_full)
        await initialise_conversation(sessionID, convoID_full)


    if(parsed_data['type'] == 'set_convo'):
        eZprint('set convo called', ['INITIALISE', 'CONVO'], line_break=True)
        # print(parsed_data['data'])
        requestedConvoID = parsed_data['data']['requestedConvoID']
        convoID = parsed_data['data']['convoID']
        loadout = parsed_data['data']['loadout']
        userID = parsed_data['data']['userID']
        sessionID = parsed_data['data']['sessionID']
        if requestedConvoID == 'welcome-message':
            requestedConvoID = await start_new_convo(sessionID, loadout)
            await handle_message(requestedConvoID, 
            """Hey sam here, I'm the (human) developer of nova. Wanted to start a thread where you can ask me questions, give feedback or make requests. There's a lot of different ways to configure agents in nova and if I can help you get the most out of it I'd love to.
            """, 'user', 'sam', None, 0, meta = 'notification')
            if not 'met_sam' in novaSession[sessionID] or not novaSession[sessionID]['met_sam']:
                novaSession[sessionID]['needs_meet_sam'] = False
                await set_user_value(userID, 'met_sam', True)
                await websocket.send(json.dumps({'event': 'set_met_sam', 'payload': {'met_sam':True}}))


        await set_convo(requestedConvoID, sessionID, loadout)
        await set_user_value(userID, 'latest_convo-' + loadout, requestedConvoID)
        await retrieve_loadout_cartridges(loadout, requestedConvoID)

    if(parsed_data['type'] == 'add_loadout_to_profile'):
        eZprint('add_loadout_to_profile route hit', ['LOADOUT'], line_break=True)
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        userID = parsed_data['data']['userID']
        await add_loadout_to_profile(loadout, userID)
        # await get_loadout_logs(loadout, sessionID)

    ## ALL BACK AND FORTH ###

    if(parsed_data['type'] == 'sendMessage'):
        eZprint('handleInput called', ['INPUT'], line_break=True)
        await user_input(parsed_data['data'])

    if(parsed_data['type']== 'updateContentField'):
        await updateContentField(parsed_data['data'])

    if(parsed_data['type']== 'function_response'):
        eZprint(parsed_data, ['FUNCTION'])
        convoID = parsed_data['data']['convoID']
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        role = parsed_data['data']['role']
        function_name = parsed_data['data']['function_name']
        await handle_message(convoID, parsed_data['data']['content'], role, '', None,0, meta = 'terminal', function_name=function_name)
        await return_to_GPT(convoID, 0)
    # if(parsed_data['type']== 'newPrompt'):
    #     loadout = None
    #     convoID = parsed_data['data']['convoID']
    #     sessionID = parsed_data['data']['sessionID']
    #     if sessionID in current_loadout:
    #         loadout = current_loadout[sessionID]
    #     await addCartridgePrompt(parsed_data['data'], convoID, loadout)
        

    if(parsed_data['type']=='add_cartridge'):
        eZprint(parsed_data, ['ADD_CART'])
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']    
        cartVal = parsed_data['data']['cartVal']
        convoID = parsed_data['data']['convoID']
        log = parsed_data['data']['log']
        await addCartridge(cartVal,sessionID, loadout, convoID, False)
        message = 'Cartridge ' + cartVal['label'] + ' added.'
        if log:
            await handle_message(convoID, message, 'function', '', None,0, meta = 'terminal', function_name='add_cartridge')
            await return_to_GPT(convoID, 0)

    if(parsed_data['type']== 'updateCartridgeField'):
        # print(parsed_data['data']['fields'])
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        convoID = parsed_data['data']['convoID']
        await update_cartridge_field(parsed_data['data'], convoID, loadout)


    # ALL GPT INDEX STUFF
    if(parsed_data['type']== 'requestDocIndex'):

        data = parsed_data['data']
        print(data)
        sessionID = data['sessionID']
        loadout = data['loadout']
        convoID = data['convoID']
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
        await asyncio.create_task(handleIndexQuery(queryPackage,convoID, loadout))

    if(parsed_data['type']== 'queryIndex'):
        data = parsed_data['data']
        sessionID = data['sessionID']
        loadout = data['loadout']
        convoID = data['convoID']
        await asyncio.create_task(handleIndexQuery(data, convoID, loadout))

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

        ##REST OF FILE HANDLING STUFF

    elif parsed_data["type"] == "file_start":
        print('indexdoc_start')
        print(parsed_data["data"])
        started = await handle_file_start(parsed_data["data"])
        if started:
            await websocket.send(json.dumps({'event':'file_start'}))
    elif parsed_data["type"] == "file_chunk":
        chunk = await handle_file_chunk(parsed_data["data"])
        if chunk:
            await websocket.send(json.dumps({'event':'file_chunk', 'id': chunk }))
    elif parsed_data["type"] == "file_end":
        await websocket.send(json.dumps({'event':'file_end'}))
        convoID = parsed_data["data"]["convoID"]
        result = await handle_file_end(parsed_data["data"])

        if result:
            convoID = parsed_data["data"]["convoID"]
            await handle_message(convoID, result, 'function', '', None,0, meta = 'terminal', function_name='file_handler')
            # await return_to_GPT(convoID, 0)

    ## EASIA VARIANT            
    # elif parsed_data["type"] == "file_end":
    #     await websocket.send(json.dumps({'event':'file_end'}))

    #     # TODO : split file handler so upload eg as main, then transcribe etc as optional
    #     convoID = parsed_data["data"]["convoID"]
    #     await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'whisper', 'state': 'transcribing'}, 'convoID': convoID}))

    #     # await handle_message(convoID, response, 'function', '', None,0, meta = 'terminal', function_name='file_handler')

    #     result = await handle_file_end(parsed_data["data"])
    #     # actions = parsed_data["data"]["actions"]
    #     await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'whisper', 'state': ''}, 'convoID': convoID}))


    #     action_modiier = """

    #     To note
    #     - B-roll must illustrate the transcript's key events, objects, locations or activities.
    #     - B-roll must not illustrate specific people or animals named in the transcript.
    #     - Do not place b-roll in the first 3 seconds of any video.
    #     - B-roll must appear every 5 seconds and be held for a total of 3 seconds.
    #     - B-roll must appear on screen 1 second before its prompting word or phrase and end 2 seconds after.

    #     IMPORTANT : Return the ‘overlay_b_roll’ function immediately upon receiving the transcript.
    #     IMPORTANT : Do not return b_roll in the first 3 seconds.
    #     IMPORTANT : All b_roll must be synchronised with its prompting word or phrase.
    #     IMPORTANT : Do not run ‘overlay_b_roll’ a second time after receiving a result.

    #     """
    #     result += action_modiier

    #     if result:
    #         convoID = parsed_data["data"]["convoID"]
    #         await handle_message(convoID, result, 'function', '', None,0, meta = 'terminal', function_name='transcribe')
    #         await return_to_GPT(convoID, 0)

    elif parsed_data["type"] == "get_file_download_link":
        eZprint('get_file_download_link route hit', ['FILE_HANDLING'])
        filename = parsed_data["data"]["filename"]
        # send_file = await get_file_download_link(filename)
        # await websocket.send(json.dumps({'event':'get_file_download_link', 'payload': send_file}))
        await websocket.send(json.dumps({'event': 'video_ready', 'payload': {'video_name': filename}}))


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

    if(parsed_data['type']=='drop_loadout'):
        # print('hellooo')
        eZprint('drop_loadout route hit', ['LOADOUT'])
        sessionID = parsed_data['data']['sessionID']
        loadout = parsed_data['data']['loadout']
        userID = parsed_data['data']['userID']
        await drop_loadout(loadout, sessionID, userID)


        # convoID_full = await handle_convo_switch(sessionID)
        # if not convoID_full:
        #     convoID_full = await start_new_convo(sessionID)

        # await loadCartridges(sessionID)
        # await runCartridges(sessionID)

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
        convoID = parsed_data['data']['convoID']
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
            await get_summary_children_by_key(key, convoID, sessionID, cartKey, client_loadout)
        elif type == 'keyword':
            await get_summary_from_keyword(key, convoID, sessionID, cartKey, client_loadout, target_loadout, True)
        elif type == 'insight':
            await get_summary_from_insight(key, convoID, sessionID, cartKey, client_loadout, target_loadout, True)

    if (parsed_data['type'] == 'get_models'):
        models = await getModels()
        await websocket.send(json.dumps({'event':'populate_models', 'payload': models}))
    if (parsed_data['type'] == 'transcribe_chunk'):
        convoID = parsed_data['data']['convoID']
        recordingID = parsed_data['data']['recordingID']
        chunkID = parsed_data['data']['chunkID']
        chunk = parsed_data['data']['chunk']
        sample_rate = parsed_data['data']['sample_rate']
        await setup_transcript_chunk(convoID, recordingID, chunkID, chunk, sample_rate)
        await websocket.send(json.dumps({'event':'return_chunk_recieved', 'convoID': convoID, 'recordingID': recordingID, 'chunkID' : chunkID}))
        # transcript_text = await handle_simple_transcript(chunk, chunkID)
        # transcript_text = await handle_transcript_chunk(convoID, recordingID, chunkID, chunk)
        # await websocket.send(json.dumps({'event':'return_chunk_transcript', 'convoID': convoID, 'recordingID': recordingID, 'chunkID' : chunkID, 'transcript_text': transcript_text}))

    if (parsed_data['type'] == 'handle_transcript_end'):
        convoID = parsed_data['data']['convoID']
        recordingID = parsed_data['data']['recordingID']
        
        updated_transcript = await handle_transcript_end(convoID, recordingID)
        await websocket.send(json.dumps({'event':'transcript_end', 'convoID': convoID, 'recordingID': recordingID, 'updated_transcript' : updated_transcript}))
    if (parsed_data['type']=='set_text_to_voice'):
        ttv = parsed_data['data']['ttv']
        userID = parsed_data['data']['userID']
        sessionID = parsed_data['data']['sessionID']
        novaSession[sessionID]['TTV'] = ttv
        # await setTextToVoice(userID, ttv)
    if (parsed_data['type']=='get_text_to_voice'):
        userID = parsed_data['data']['userID']
        ttv = novaSession[sessionID].get('TTV', False)
            
        # ttv = await getTextToVoice(userID)

        await websocket.send(json.dumps({'event':'get_user_ttv', 'payload': ttv}))
        # await websocket.send(json.dumps({'event':'set_text_to_voice', 'convoID': convoID, 'text': text}))

    if (parsed_data['type']=='update_user_events'):
        userID = parsed_data['data']['userID']
        field = parsed_data['data']['field']
        value = parsed_data['data']['value']
        await update_user_events(userID, field, value)
        events = await get_user_events(userID)
        await websocket.send(json.dumps({'event':'get_user_events', 'payload': events}))
    if (parsed_data['type']=='get_user_events'):
        userID = parsed_data['data']['userID']
        events = await get_user_events(userID)
        await websocket.send(json.dumps({'event':'get_user_events', 'payload': events}))

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
        'loadout' : file_metadata['loadout'],
        'convoID' : file_metadata['convoID'],
        'file_name': file_metadata['file_name'],
        'file_type': file_metadata['file_type'],
        'sessionID': file_metadata['sessionID'],
        'tempKey': file_metadata['tempKey'],
        'indexType': file_metadata['indexType'],
        'document_type': file_metadata['document_type'],
    }

    sessionID = data['sessionID']

    indexRecordKey = await indexDocument(data, file_metadata['loadout'])
    # if indexRecord:
    #     payload = {
    #         'tempKey': data['tempKey'],
    #         'newCartridge': indexRecord.blob,
    #     }
    # await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    queryPackage = {
        'query': 'Give this document a short summary.',
        'cartKey': indexRecordKey,
        'sessionID': data['sessionID'],
        'userID': data['userID'],
    }
    sessionID = data['sessionID']

    await asyncio.create_task(handleIndexQuery(queryPackage, file_metadata['convoID'], file_metadata['loadout']))

    # Remove the stored file chunks upon completion
    del file_chunks[tempKey]

# async def handle_new_user_loadout(sessionID, loadout):
#     await add_loadout_to_profile 
#     await set_loadout(loadout, sessionID)
#     await get_loadout_logs(loadout, sessionID)

#     convoID = await get_latest_loadout_convo(loadout)
    
#     if not convoID:
#         convoID = await start_new_convo(sessionID, loadout)

#     await retrieve_loadout_cartridges(loadout, convoID)
#     await set_convo(convoID, sessionID, loadout)

#     await initialise_conversation(sessionID, convoID)
#     await runCartridges(sessionID, loadout)

if __name__ == '__main__':

    host=os.getenv("HOST", default='0.0.0.0')
    port=int(os.getenv("PORT", default=5000))
    config = Config()
    config.bind = [str(host)+":"+str(port)]  # As an example configuration setting
    os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'
    asyncio.run(serve(app, config))

    # find and print list.log
 

    # app.run(debug=True, port=os.getenv("PORT", default=5000))
    # app.run(host="127.0.0.1", port=5500) 
