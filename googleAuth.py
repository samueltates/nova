"""Google docs reader."""

import os
from appHandler import app, websocket
from typing import Any, List
from quart import redirect, url_for,session, request
import asyncio
from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document
import json
from nova import addAuth, getAuth, eZprint
userAuths = dict()

SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery as discovery

# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


@app.route('/oauth2callback')
def oauth2callback():
  # Specify the state when creating the flow in the callback so that it can
  # verified in the authorization server response.
    print('oauth2callback')
    
    state = userAuths['state']    
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'credentials.json', scopes=SCOPES, state=state)
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
    addAuth(userAuths['userID'], credentials)
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

class GoogleDocsReader(BaseReader):
    """Google Docs reader.

    Reads a page from Google Docs

    """

    async def load_data(self, document_ids: List[str], userID) -> List[Document]:
        """Load data from the input directory.

        Args:
            document_ids (List[str]): a list of document ids.
        """
        if document_ids is None:
            raise ValueError('Must specify a "document_ids" in `load_kwargs`.')

        results = []
        for document_id in document_ids:
            doc = await self._load_doc(document_id, userID)
            results.append(Document(doc, extra_info={"document_id": document_id}))
        return results

    async def _load_doc(self, document_id: str, userID) -> str:
        """Load a document from Google Docs.

        Args:
            document_id: the document id.

        Returns:
            The document text.
        """

        credentials = await self._get_credentials(userID)
        docs_service = discovery.build("docs", "v1", credentials=credentials)
        doc = docs_service.documents().get(documentId=document_id).execute()
        doc_content = doc.get("body").get("content")
        return self._read_structural_elements(doc_content)

    async def _get_credentials(self, userID) -> Any:
        """Get valid user credentials from storage.

        The file token.json stores the user's access and refresh tokens, and is
        created automatically when the authorization flow completes for the first
        time.

        Returns:
            Credentials, the obtained credential.
        """
   
        creds = None
        userAuths['authorised'] = False
        authToken = json.loads(getAuth(userID))
        print(authToken)
        if 'credentials' in authToken:
            creds = Credentials(authToken['blob']['credentials'])
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print('refreshing')
                creds.refresh(Request())
                userAuths['authorised'] = True
            else:
                print('getting new')
                flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                'credentials.json',
                scopes=['https://www.googleapis.com/auth/documents.readonly'])    
                flow.redirect_uri = url_for('oauth2callback', _external=True,  _scheme=os.environ.get('SCHEME') or 'https')
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
                    'userID':userID
                } )
                # session['state'] = state  
                # session['userID'] = userID
                # session['authorised'] = False
                
                app.redirect(authorization_url)
                await websocket.send(json.dumps({'event':'auth','payload':{'message':'please visit this URL to authorise google docs access', 'url':authorization_url}}))
        while not userAuths['authorised']:
            await asyncio.sleep(1)
        print('authorised')
        authToken = json.loads(getAuth(userID))
        print(authToken)
        if 'credentials' in authToken:
            creds = Credentials(authToken['blob']['credentials'])
        # if os.path.exists( userID +"-token.json"):
        #     creds = Credentials.from_authorized_user_file(userID + "-token.json", SCOPES)
        return creds
    

    def _read_paragraph_element(self, element: Any) -> Any:
        """Return the text in the given ParagraphElement.

        Args:
            element: a ParagraphElement from a Google Doc.
        """
        text_run = element.get("textRun")
        if not text_run:
            return ""
        return text_run.get("content")

    def _read_structural_elements(self, elements: List[Any]) -> Any:
        """Recurse through a list of Structural Elements.

        Read a document's text where text may be in nested elements.

        Args:
            elements: a list of Structural Elements.
        """
        text = ""
        for value in elements:
            if "paragraph" in value:
                elements = value.get("paragraph").get("elements")
                for elem in elements:
                    text += self._read_paragraph_element(elem)
            elif "table" in value:
                # The text in table cells are in nested Structural Elements
                # and tables may be nested.
                table = value.get("table")
                for row in table.get("tableRows"):
                    cells = row.get("tableCells")
                    for cell in cells:
                        text += self._read_structural_elements(cell.get("content"))
            elif "tableOfContents" in value:
                # The text in the TOC is also in a Structural Element.
                toc = value.get("tableOfContents")
                text += self._read_structural_elements(toc.get("content"))
        return text
