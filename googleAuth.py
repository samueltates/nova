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
    user_id = await app.redis.get('userID')
    credentials = await app.redis.get('credentials')
    # Check if the credentials exist and are valid
    print(credentials)
    if user_id and credentials:
        print('user_id and credentials found')
        user_id = user_id.decode('utf-8')
        credentials = credentials.decode('utf-8')
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
                    await app.redis.set('credentials', creds_obj.to_json())
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
    print('login')
    credentials = await app.redis.get('credentials')
    PROFILE_SCOPE = 'https://www.googleapis.com/auth/userinfo.profile'
    SCOPES = []
    if credentials:
        print('credentials found')
        creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        if not creds_obj.has_scopes(['https://www.googleapis.com/auth/userinfo.profile']) :
            print('credentials do not have right scope')
            SCOPES = creds_obj.scopes + [PROFILE_SCOPE]  # Add the Google Docs scope to the existing scopes.
            print(SCOPES)
            await app.redis.delete('scopes')
            for scope in SCOPES:
                print(scope)
                await app.redis.rpush('scopes', scope)
    else:
        print('credentials not found')
        SCOPES = [PROFILE_SCOPE]
        await app.redis.delete('scopes')
        for scope in SCOPES:
            print(scope)
            await app.redis.rpush('scopes', scope)
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
    await app.redis.set('state', state)
    redir = redirect(authorization_url)
    print(redir)
    print('got authorization')
    print(authorization_url)
    return authorization_url

@app.route('/authoriseLogin')
async def authoriseLogin():
    print('authoriseLogin')
    state = await app.redis.get('state')
    state = state.decode("utf-8")
    scopes = await app.redis.lrange("scopes", 0, -1)
    scopes = [s.decode("utf-8") for s in scopes]
    localScopes = []
    for scope in scopes:
        localScopes.append(scope)
    print(localScopes)
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=localScopes, state=state) 
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
    await app.redis.set('userID', userInfo['id'])
    await app.redis.set('credentials', credentials.to_json())
    await app.redis.set('authorised',  1)
    await app.redis.set('userName', userInfo['name'])
    
    print(app.redis)
    
    return redirect(url_for('authComplete'))



@app.route('/authComplete')
async def authComplete():
    print('authComplete')
    user_id = await app.redis.get('userID')
    user_name = await app.redis.get('userName')
    authorised = await app.redis.get('authorised')
    user_id = user_id.decode("utf-8")
    user_name = user_name.decode("utf-8")
    authorised = authorised.decode("utf-8")

    # print(await app.redis.get('userName').decode("utf-8")),
    # print(await app.redis.get('authorised').decode("utf-8"))
    return redirect(os.environ.get('NOVAHOME'))

    return await render_template('auth_complete.html', user_id=user_id, user_name=user_name, authorised=authorised)

async def logout():
    credentials = await app.redis.get('credentials')
    credentials = credentials.decode('utf-8')
    creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    
    if creds_obj:
        access_token = creds_obj.token
        if revoke_token(access_token):
            await app.redis.delete('credentials')
            await app.redis.delete('userID')
            await app.redis.delete('userName')
            await app.redis.delete('authorised')
            await app.redis.delete('scopes')

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
    state = await app.redis.get('state')
    state = state.decode("utf-8")
    scopes = await app.redis.lrange("scopes", 0, -1)
    # Convert scopes from bytes to string
    scopes = [s.decode("utf-8") for s in scopes]
    localScopes = []
    for scope in scopes:
        localScopes.append(scope)
    # scopes = scopes.decode("utf-8")
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'credentials.json', scopes=localScopes, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True, _scheme=os.environ.get('SCHEME') or 'https')
    authorization_response = request.url
    print(request)
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials
    await app.redis.set('credentials', credentials.to_json())
    return redirect(url_for('docAuthComplete', _external=True,  _scheme=os.environ.get('SCHEME') or 'https'))
    

@app.route('/docAuthComplete')
async def docAuthComplete():
    print('docAuthComplete')
    await app.redis.set ('docsAuthorised', 1)

    return "Authentication complete, please return to browser!"

    # await websocket.send(json.dumps({'event':'authComplete'}))


async def GetDocCredentials():
    print('GetDocCredentials')
    user_id = await app.redis.get('userID')
    credentials = await app.redis.get('credentials')
    # Check if the credentials exist and are valid
    print(credentials)
    DOC_SCOPE = 'https://www.googleapis.com/auth/documents.readonly'
    creds_obj = None
    if user_id and credentials:
        print('user_id and credentials found')
        user_id = user_id.decode('utf-8')
        credentials = credentials.decode('utf-8')
        creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
        print(creds_obj)
        if not creds_obj.has_scopes([DOC_SCOPE]) :
            print('credentials do not have the right scope')
            SCOPES = creds_obj.scopes + [DOC_SCOPE]  # Add the Google Docs scope to the existing scopes.
            print(SCOPES)
            await app.redis.delete('scopes')
            for scope in SCOPES:
                print(scope)
                await app.redis.rpush('scopes', scope)
            # await app.redis.set('SCOPES', SCOPES)
            # Create a new authorization URL with the additional scope
            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file('credentials.json', scopes=SCOPES) 
            flow.redirect_uri = url_for('oauth2callback', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
            auth_url, state = flow.authorization_url(prompt='consent')
            print(f"Please grant consent for Google Docs. Go to the following link: {auth_url}")
            await app.redis.set('state', state )
            await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':auth_url}}))
            await app.redis.set('docsAuthorised', 0)
            print('waiting for authorisation')
            authorised = await app.redis.get('docsAuthorised')
            authorised = int(authorised.decode('utf-8'))
            while authorised == 0:
                print('waiting for authorisation')
                authorised = await app.redis.get('docsAuthorised')
                authorised = int(authorised.decode('utf-8'))
                print(authorised)
                await asyncio.sleep(1)
            credentials = await app.redis.get('credentials')
            credentials = credentials.decode('utf-8')
            creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    else :
        print('user_id and credentials not found')
        creds_obj = await NewDocAuthRequest()
    
    return creds_obj
    

async def NewDocAuthRequest():
    scopes=["https://www.googleapis.com/auth/documents.readonly"]   
    await app.redis.delete('scopes')
    for scope in scopes:
        print(scope)
        await app.redis.rpush('scopes', scope)
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
    await app.redis.set('state', state)
    redir = redirect(authorization_url)
    print(redir)
    print('got authorization')
    print(authorization_url)
    await app.redis.set('state', state )
    await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':authorization_url}}))
    await app.redis.set('docsAuthorised', 0)
    print('waiting for authorisation')
    authorised = await app.redis.get('docsAuthorised')
    authorised = int(authorised.decode('utf-8'))
    while authorised == 0:
        print('waiting for authorisation')
        authorised = await app.redis.get('docsAuthorised')
        authorised = int(authorised.decode('utf-8'))
        print(authorised)
        await asyncio.sleep(1)
    credentials = await app.redis.get('credentials')
    credentials = credentials.decode('utf-8')
    creds_obj = Credentials.from_authorized_user_info(json.loads(credentials))
    return creds_obj

