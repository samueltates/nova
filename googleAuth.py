import os
import asyncio
import json
import requests
from quart import redirect, url_for, request, render_template
import secrets
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_oauthlib.flow
from googleapiclient import errors
import googleapiclient.discovery as discovery
CLIENT_SECRETS_FILE = "credentials.json"
# google auth docs : https://developers.google.com/identity/protocols/oauth2/web-server
# oauth lib docs : https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html

from appHandler import app, websocket
from sessionHandler import novaSession, current_config, current_loadout, available_convos, available_cartridges, novaConvo, chatlog, agentName

from user import GoogleSignOn
from debug import eZprint



async def check_credentials(sessionID):
    credentials = None
    if 'credentials' in novaSession[sessionID]:
        credentials = novaSession[sessionID]['credentials']
    if credentials:
        creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        eZprint('credentials found')
        # If the credentials have an expiry and the token is expired
        if creds_obj.expiry and creds_obj.expired:
            eZprint('credentials expired')
            # Check if the credentials have a refresh token
            if creds_obj.refresh_token:
                # Refresh the access token
                try:
                    creds_obj.refresh(Request())
                    # Store the updated credentials
                    eZprint('credentials refreshed')
                    novaSession[sessionID]['credentials'] = creds_obj.to_json()
                except :
                    eZprint(f"Failed to refresh the access token: ")
                    return False
            else:
                eZprint("No refresh token found for existing user")
                return False
        elif not creds_obj.expired:
            novaSession[sessionID]['scopes'] = creds_obj.scopes
            ## TODO : is this needed?
            # ('scopes set to : ' + str(novaSession[sessionID]['scopes']))
            return True
    return False

async def requestPermissions(scopes, sessionID):
    eZprint('requestPermission route hit')
    credentials = None
    if 'credentials' in novaSession[sessionID]:
        credentials = novaSession[sessionID]['credentials']    
    novaSession[sessionID]['requesting'] = True
    if credentials:
        eZprint('credentials found')
        creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        if creds_obj.has_scopes(scopes):
            eZprint('scopes already granted')
            return False
        else:
            eZprint('scopes missing')
            scopes = creds_obj.scopes + scopes

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=scopes)
    novaSession[sessionID]['scopes'] = scopes    
    flow.redirect_uri = url_for('authoriseRequest', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt="consent",  # Add this line
        # include_granted_scopes='true'
    )
    
    print('url set to : ' + authorization_url)
    novaSession[sessionID]['state'] =  state
    novaSession[state] = {}
    novaSession[state]['sessionID'] = sessionID
    redir = redirect(authorization_url)
    eZprint('got redirect URL')

    return authorization_url

@app.route('/authoriseRequest')
async def authoriseRequest():
    req = request.args
    eZprint('authorise request route hit')
    print(req)
    state = req.get('state')
    # scopes = req.get('scope')
    sessionID = novaSession[state]['sessionID']
    # print(app.session)
    sessionID = app.session.get('sessionID')
    if sessionID in novaSession:
        # state = novaSession[sessionID]['state'] 
        scopes = novaSession[sessionID]['scopes'] 
    
        
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=scopes, state=state) 
    flow.redirect_uri = url_for('authoriseRequest', _external=True, _scheme=os.environ.get('SCHEME') or 'https')
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    novaSession[sessionID]['credentials'] = credentials.to_json()
    for scope in credentials.granted_scopes:
        if scope == 'https://www.googleapis.com/auth/userinfo.profile':
            novaSession[sessionID]['profileAuthed'] = True
            await getUserInfo(sessionID)
            print('profileAuthed set to true')
        elif scope == 'https://www.googleapis.com/auth/documents.readonly':
            novaSession[sessionID]['docsAuthed'] = True
            print('docsAuthed set to true')

    return redirect(url_for('requestComplete'))

@app.route('/requestComplete')
async def requestComplete():
    eZprint('requestComplete route hit')
    print(app.session)
    sessionID = app.session.get('sessionID')
    if sessionID in novaSession:
        novaSession[sessionID]['requesting'] = False
        if novaSession[sessionID]['profileAuthed']:
            eZprint('profileAuthed')
            return redirect(os.environ.get('NOVAHOME'))
        if novaSession[sessionID]['docsAuthed']:
            eZprint('docsAuthed')
            return redirect(os.environ.get('NOVAHOME'))

async def getUserInfo(sessionID):
    eZprint('getUserInfo route hit')
    print(app.session)
    credentials = None
    if 'credentials' in novaSession[sessionID]:
        eZprint('credentials found')
        credentials = novaSession[sessionID]['credentials'] 
    if not credentials or not novaSession[sessionID]['profileAuthed']:
        print('no credentials or profileAuthed')
        requestPermissions(['https://www.googleapis.com/auth/userinfo.profile'])
        return False
    eZprint('credentials found')
    credentials = Credentials.from_authorized_user_info(json.loads(credentials))
    service = discovery.build('oauth2', 'v2', credentials=credentials)
    userInfo = service.userinfo().get().execute()
    await GoogleSignOn(userInfo, credentials)
    novaSession[sessionID]['userID'] =  userInfo['id']
    novaSession[sessionID]['userName'] =  userInfo['name']
    return True

async def getDocService(sessionID):
    eZprint('getDocService route hit')
    credentials = None
    if 'credentials' in novaSession[sessionID]:
        credentials = novaSession[sessionID]['credentials'] 
        print('credentials found')
    if not credentials or not novaSession[sessionID]['docsAuthed']:
        print('no credentials or docsAuthed')
        auth_url = await requestPermissions(['https://www.googleapis.com/auth/documents.readonly'])
        await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':auth_url}}))
        novaSession[sessionID]['requesting'] = True
        while novaSession[sessionID]['requesting']:
            await asyncio.sleep(1)
        if not novaSession[sessionID]['docsAuthed']:
            await websocket.send(json.dumps({'event':'auth','payload':{'message':'something went wrong', 'url':''}}))
            return False
        await websocket.send(json.dumps({'event':'setDocAuthed'}))
        credentials = novaSession[sessionID]['credentials']
    credentials = Credentials.from_authorized_user_info(json.loads(credentials))
    service = discovery.build('docs', 'v1', credentials=credentials)
    print('service built')
    return service

async def logout(sessionID):
    credentials = None
    if 'credentials' in novaSession[sessionID]:
        credentials = novaSession[sessionID]['credentials']     
        print(credentials)
    creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    if creds_obj:
        access_token = creds_obj.token
        if revoke_token(access_token):
            convoID = novaSession[sessionID]['convoID']
            if 'credentials' in novaSession[sessionID]:
                novaSession[sessionID]['credentials'] = ''
            if 'userID' in novaSession[sessionID]:
                novaSession[sessionID]['userID']= ''
            if 'userName' in novaSession[sessionID]:
                novaSession[sessionID]['userName'] = ''
            if 'docsAuthorised' in novaSession[sessionID]:
                novaSession[sessionID]['docsAuthorised']=False
            if 'state' in  novaSession[sessionID]:
                novaSession[sessionID]['state'] =''
            if 'profileAuthed' in novaSession[sessionID]:
                novaSession[sessionID]['profileAuthed']=False
            if 'scopes' in novaSession[sessionID]:
                novaSession[sessionID]['scopes'] =''
            if 'owner' in novaSession[sessionID]:
                novaSession[sessionID]['owner'] = False
            if sessionID in novaSession:
                novaSession.pop(sessionID)
            # sessionID = secrets.token_bytes(8).hex()
            # app.session['sessionID'] = sessionID
            novaSession[sessionID] = {}
            novaSession[sessionID]['profileAuthed'] = False
            novaSession[sessionID]['docsAuthed'] = False
            novaSession[sessionID]['userName'] = 'Guest'
            novaSession[sessionID]['userID'] = 'guest-'+sessionID    
            novaSession[sessionID]['new_login'] = True
            novaSession[sessionID]['subscribed'] = False

            if sessionID in current_config:
                current_config.pop(sessionID)
            if sessionID in current_loadout:
                current_loadout.pop(sessionID)
            if sessionID in available_cartridges:
                available_cartridges.pop(sessionID)
            if sessionID in available_convos:
                available_convos.pop(sessionID)
            if convoID in novaConvo:
                novaConvo.pop(convoID)
            if sessionID in chatlog:
                chatlog.pop(sessionID)
            return True
    return False

def revoke_token(token):
    revoke_url = "https://oauth2.googleapis.com/revoke"
    # Revoke the token
    response = requests.post(revoke_url, params={"token": token})
    if response.status_code == 200:
        return True
    else:
        print(f"Failed to revoke token: {response.text}")
        return False