import os
from appHandler import app, websocket
from quart import redirect, url_for, request, render_template
import asyncio
import json
import nova 
import requests


userAuths = dict()

ACCOUNTSCOPE = ["https://www.googleapis.com/auth/userinfo.profile"]
DRIVESCOPE = ["https://www.googleapis.com/auth/documents.readonly"]
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
        elif not creds_obj.expired:
            print('credentials not expired')
            return True
    return False

async def login():
    print('login')
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=['https://www.googleapis.com/auth/userinfo.profile'])    
    flow.redirect_uri = url_for('authoriseLogin', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
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
    return authorization_url

@app.route('/authoriseLogin')
async def authoriseLogin():
    print('authoriseLogin called')
    print(request)
    stored_state = await app.redis.get('state')
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json', scopes=['https://www.googleapis.com/auth/userinfo.profile'], state = stored_state.decode("utf-8")
    )    
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
  # Specify the state when creating the flow in the callback so that it can
  # verified in the authorization server response.
    print('oauth2callback')
    
    state = userAuths['state']    
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'credentials.json', scopes=DRIVESCOPE, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True, _scheme=os.environ.get('SCHEME') or 'https')

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url
    print(request)
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
                # Save the credentials for the next run
    await nova.addAuth(userAuths['userID'], credentials)
    # with open(userAuths['userID']+"-token.json", "w") as token:
    #     token.write(credentials.to_json())
    #     userAuths['creds']= credentials
    userAuths['authorised'] = True,
    return redirect(url_for('authComplete', _external=True,  _scheme=os.environ.get('SCHEME') or 'https'))
    

async def SignIn(sessionID):
    print('SignIn')
    # userAuths['state'] = sessionID
    # userAuths['authorised'] = False
    credentials = await GetCredentials(sessionID, ['https://www.googleapis.com/auth/userinfo.profile'], 'oauth2callbackProfile', )
    service = discovery.build('oauth2', 'v2', credentials=credentials)
    try:
        user_info = service.userinfo().get().execute()
        # Save user_info to your database, or use in your application logic
    except errors.HttpError as error:
        print(f"An error occurred: {error}")


async def GetCredentials(sessionID, SCOPES, redirect):
    """Get valid user credentials from storage.

    The file token.json stores the user's access and refresh tokens, and is
    created automatically when the authorization flow completes for the first
    time.

    Returns:
        Credentials, the obtained credential.
    """

    # creds = None
    # userAuths[sessionID]['authorised'] = False
    # # authResponse = await nova.getAuth(sessionID)
    # # print(authResponse)
    # # if(authResponse is not None):
    # #     print('authResponse')
    # #     credentials = {
    # #         "token": authResponse['token'],
    # #         "refresh_token": authResponse['refresh_token'],
    # #         "token_uri": authResponse['token_uri'],
    # #         "client_id": authResponse['client_id'],
    # #         "client_secret": authResponse['client_secret'],
    # #     }
    # #     creds = Credentials(**credentials)
    # #     print(creds.refresh_token)
    # #     print(creds.client_id)
    # # # If there are no (valid) credentials available, let the user log in.
    # if not creds:
    
    print('getting new')
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    'credentials.json',
    scopes=SCOPES)    
    flow.redirect_uri = url_for(redirect, _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true'
        )
    
    print(authorization_url)
    print(state)
    print(creds)
    userAuths.update({
        'state':state,
        'authorised':False,
        'userID':sessionID
    })

    redirect(authorization_url)

    await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':authorization_url}}))
    while not userAuths['authorised']:
        await asyncio.sleep(1)
    print('authorised')
    authResponse = await nova.getAuth(userID)
    if(authResponse is not None):
        print('authResponse')
        credentials = {
            "token": authResponse['token'],
            "refresh_token": authResponse['refresh_token'],
            "token_uri": authResponse['token_uri'],
            "client_id": authResponse['client_id'],
            "client_secret": authResponse['client_secret'],
        }
        creds = Credentials(**credentials)
        print(creds.refresh_token)
        print(creds.client_id)
        # if os.path.exists( userID +"-token.json"):
        #     creds = Credentials.from_authorized_user_file(userID + "-token.json", SCOPES)
    return creds

