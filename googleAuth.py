import os
from appHandler import app, websocket
from quart import redirect, url_for, request, render_template
import asyncio
import json
import nova
import requests

CLIENT_SECRETS_FILE = "credentials.json"

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery as discovery
from googleapiclient import errors


# google auth docs : https://developers.google.com/identity/protocols/oauth2/web-server
# oauth lib docs : https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html

async def silent_check_login():
    nova.eZprint('silent check')
    user_id = app.session.get('userID')
    credentials = app.session.get('credentials')
    # print(app.session)
    if user_id and credentials:
        print('user_id and credentials found')
        creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        # If the credentials have an expiry and the token is expired
        if creds_obj.expiry and creds_obj.expired:
            print('credentials expired')
            # Check if the credentials have a refresh token
            if creds_obj.refresh_token:
                # Refresh the access token
                try:
                    creds_obj.refresh(Request())
                    # Store the updated credentials
                    print('credentials refreshed')
                    app.session['credentials'] =  creds_obj.to_json()
                except :
                    print(f"Failed to refresh the access token: ")
                    return False
            else:
                print("No refresh token found for existing user")
                return False
        elif not creds_obj.expired and creds_obj.has_scopes(['https://www.googleapis.com/auth/userinfo.profile']):
            print('credentials not expired and has right scope')
            return True

    return False

async def login():
    print('SSOLOGIN route hit')
    credentials = app.session.get('credentials')
    PROFILE_SCOPE = 'https://www.googleapis.com/auth/userinfo.profile'
    SCOPES = []
    if credentials:
        print('credentials found')
        try:
            creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        except:
            print('credentials not found')
            SCOPES = [PROFILE_SCOPE]
            if app.session.get('scopes'):
                app.session.pop('scopes')
            app.session['scopes'] = []
            for scope in SCOPES:
                print(scope)
                app.session['scopes'].append(scope)
            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            'credentials.json', scopes=SCOPES)    
            flow.redirect_uri = url_for('authoriseLogin', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
            authorization_url, state = flow.authorization_url(
                # Enable offline access so that you can refresh an access token without
                # re-prompting the user for permission. Recommended for web server apps.
                access_type='offline',
                prompt="consent",  # Add this line
                # Enable incremental authorization. Recommended as a best practice.
                include_granted_scopes='true'
            )
            app.session['state'] =  state
            redir = redirect(authorization_url)
            print(redir)
            print('got authorization')
            print(authorization_url)
            return authorization_url
        if not creds_obj.has_scopes(['https://www.googleapis.com/auth/userinfo.profile']) :
            print('credentials do not have right scope')
            SCOPES = creds_obj.scopes + [PROFILE_SCOPE]  # Add the Google Docs scope to the existing scopes.
            print(SCOPES)
            if app.session.get('scopes'):
                app.session.pop('scopes')
            app.session['scopes'] = []
            for scope in SCOPES:
                app.session['scopes'].append(scope)
    else:
        print('credentials not found')
        SCOPES = [PROFILE_SCOPE]
        if app.session.get('scopes'):
            app.session.pop('scopes')
        app.session['scopes'] = []
        for scope in SCOPES:
            app.session['scopes'].append(scope)
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=SCOPES)    
    flow.redirect_uri = url_for('authoriseLogin', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        prompt="consent",  # Add this line
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true'
    )
    app.session['state'] =  state
    redir = redirect(authorization_url)
    print(redir)
    print('got authorization')

    return authorization_url

@app.route('/authoriseLogin')
async def authoriseLogin():
    nova.eZprint('authoriseLogin')
    print(app.session)
    state = app.session.get('state')
    scopes = app.session.get('scopes')

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=scopes, state=state) 
    flow.redirect_uri = url_for('authoriseLogin', _external=True, _scheme=os.environ.get('SCHEME') or 'https')
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    print('flow token fetched')
    # print(flow.credentials)
    credentials = flow.credentials
    print(credentials)
    print('credentials fetched')
    userInfo = flow.authorized_session()
    print('userInfo fetched')
    print(userInfo)
    service = discovery.build('oauth2', 'v2', credentials=credentials)
    userInfo = service.userinfo().get().execute()
    print(userInfo)
    user = await nova.GoogleSignOn(userInfo, credentials)
    app.session['userID'] =  userInfo['id']
    app.session['userName'] =  userInfo['name']
    app.session['authorised'] =  1
    app.session['credentials'] = credentials.to_json()
    return redirect(url_for('authComplete'))


@app.route('/authComplete')
async def authComplete():
    nova.eZprint('authComplete')
    print(app.session)
    # return await render_template('auth_complete.html', user_id=app.session.get('userID'), user_name=app.session.get('userName'), authorised=app.session.get('authorised'), ws = os.environ.get('WEBSOCKET') or 'wss://nova-staging.up.railway.app/ws')
    return redirect(os.environ.get('NOVAHOME'))

async def logout():
    credentials = app.session.get('credentials')
    print(credentials)
    creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    if creds_obj:
        access_token = creds_obj.token
        if revoke_token(access_token):
            if app.session.get('credentials'):
                app.session.pop('credentials')
            if app.session.get('userID'):
                app.session.pop('userID')
            if app.session.get('userName'):
                app.session.pop('userName')
            if app.session.get('authorised'):
                app.session.pop('authorised')
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


@app.route('/oauth2callback')
async def oauth2callback():
    print('oauth2callback')
    state = app.session['state']
    scopes = app.session['scopes']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'credentials.json', scopes=scopes, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True, _scheme=os.environ.get('SCHEME') or 'https')
    authorization_response = request.url
    print(request)
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials
    app.session['credentials'] = credentials.to_json()
    return redirect(url_for('docAuthComplete', _external=True,  _scheme=os.environ.get('SCHEME') or 'https'))
    

@app.route('/docAuthComplete')
async def docAuthComplete():
    print('docAuthComplete')
    app.session['docsAuthorised'] = 1
    
    # return "Authentication complete, please return to browser!"

    # return "Authentication complete, please return to browser!"

async def GetDocCredentials():
    print('GetDocCredentials')
    user_id = app.session.get('userID')
    credentials = app.session.get('credentials')
    # Check if the credentials exist and are valid
    print(credentials)
    DOC_SCOPE = 'https://www.googleapis.com/auth/documents.readonly'
    creds_obj = None
    if user_id and credentials:
        print('user_id and credentials found')
        creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        if not creds_obj.has_scopes([DOC_SCOPE]) :
            print('credentials do not have the right scope')
            SCOPES = creds_obj.scopes + [DOC_SCOPE]  # Add the Google Docs scope to the existing scopes.
            print(SCOPES)
            if app.session.get('scopes'):
                app.session.pop('scopes')
            app.session['scopes'] = []
            for scope in SCOPES:
                print(scope)
                app.session['scopes'].append(scope)
            # await app.redis.set('SCOPES', SCOPES)
            # Create a new authorization URL with the additional scope
            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file('credentials.json', scopes=SCOPES) 
            flow.redirect_uri = url_for('oauth2callback', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
            auth_url, state = flow.authorization_url(prompt='consent')
            print(f"Please grant consent for Google Docs. Go to the following link: {auth_url}")
            app.session['state'], state
            await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':auth_url}}))
            app.session['docsAuthorised'] = 0
            print('waiting for authorisation')
            authorised = app.session.get('docsAuthorised')
            while authorised == 0:
                print('waiting for authorisation')
                authorised = app.session.get('docsAuthorised')
                await asyncio.sleep(1)
            credentials = app.session.get('credentials')
            creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    else :
        print('user_id and credentials not found')
        creds_obj = await NewDocAuthRequest()
    
    return creds_obj
    

async def NewDocAuthRequest():
    scopes=["https://www.googleapis.com/auth/documents.readonly"]   
    if app.session.get('scopes'):
        app.session.pop('scopes')
    app.session['scopes'] = []
    for scope in scopes:
        print(scope)
        app.session.append('scopes', scope)
    # await app.redis.set('SCOPES', SCOPES)
    # Create a new authorization URL with the additional scope
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file('credentials.json', scopes=scopes) 
    flow.redirect_uri = url_for('oauth2callback', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true'
    )
    app.session['state'] = state
    redir = redirect(authorization_url)
    print(redir)
    print('got authorization')
    print(authorization_url)
    app.session['state'] = state 
    await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':authorization_url}}))
    app.session['docsAuthorised'] =  0
    print('waiting for authorisation')
    authorised = app.session.get('docsAuthorised')
    while authorised == 0:
        print('waiting for authorisation')
        authorised = app.session.get('docsAuthorised')
        authorised = int(authorised.decode('utf-8'))
        print(authorised)
        await asyncio.sleep(1)
    credentials = app.session.get('credentials')
    creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    return creds_obj

