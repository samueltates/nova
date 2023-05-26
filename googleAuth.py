import os
from appHandler import app, websocket
from quart import redirect, url_for, session, request
import asyncio

import json
import nova 

userAuths = dict()

ACCOUNTSCOPE = ["https://www.googleapis.com/auth/userinfo.profile"]
DRIVESCOPE = ["https://www.googleapis.com/auth/documents.readonly"]
CLIENT_SECRETS_FILE = "credentials.json"

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery as discovery
from googleapiclient import errors

from authlib.integrations.base_client.async_app import AsyncOAuthError
from authlib.integrations.quart_client import OAuth

# Setup OAuth and register Google provider

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.environ.get('CLIENT_ID')',
    client_secret=os.environ.get('CLIENT_SECRET')
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    userinfo_endpoint='https://www.googleapis.com/oauth2/v3/userinfo',
    client_kwargs={'scope': 'openid email'},
)

async def login():
    redirect_uri = url_for('authoriseLogin', _external=True)
    return await oauth.google.authorize_redirect(redirect_uri)

@app.route('/authoriseLogin')
async def authorize():
    token = await oauth.google.authorize_access_token()
    userinfo = await oauth.google.userinfo(token=token)
    await nova.addAuth(userinfo, token)
    # Here, userinfo contains the user's profile information such as email, name, etc.
    # At this point, you can look up or create the user in your database,
    # store the access and refresh tokens, and create a server-side session.

    # ... (store tokens, create session, etc.)

    # Redirect the user to a protected page or dashboard
    return redirect(url_for('dashboard'))

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
    

@app.route('/authComplete')
async def authComplete():
    print('authComplete')
    return "Authentication complete, please return to browser!"

    # await websocket.send(json.dumps({'event':'authComplete'}))

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

