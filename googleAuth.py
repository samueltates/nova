"""Google docs reader."""

import os
from appHandler import app
from typing import Any, List
from quart import redirect, url_for,session, request

from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document

SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]


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
    state = session['state']    
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json', scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
                # Save the credentials for the next run
    with open(session['userID']+"-token.json", "w") as token:
        token.write(credentials.to_json())

    return redirect(url_for('test_api_request'))


class GoogleDocsReader(BaseReader):
    """Google Docs reader.

    Reads a page from Google Docs

    """

    def load_data(self, document_ids: List[str], userID) -> List[Document]:
        """Load data from the input directory.

        Args:
            document_ids (List[str]): a list of document ids.
        """
        if document_ids is None:
            raise ValueError('Must specify a "document_ids" in `load_kwargs`.')

        results = []
        for document_id in document_ids:
            doc = self._load_doc(document_id)
            results.append(Document(doc, extra_info={"document_id": document_id}))
        return results

    def _load_doc(self, document_id: str, userID) -> str:
        """Load a document from Google Docs.

        Args:
            document_id: the document id.

        Returns:
            The document text.
        """
        import googleapiclient.discovery as discovery

        credentials = self._get_credentials(self, userID)
        docs_service = discovery.build("docs", "v1", credentials=credentials)
        doc = docs_service.documents().get(documentId=document_id).execute()
        doc_content = doc.get("body").get("content")
        return self._read_structural_elements(doc_content)

    def _get_credentials(self, userID) -> Any:
        """Get valid user credentials from storage.

        The file token.json stores the user's access and refresh tokens, and is
        created automatically when the authorization flow completes for the first
        time.

        Returns:
            Credentials, the obtained credential.
        """
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        import google_auth_oauthlib.flow

        creds = None
        if os.path.exists( userID +"-token.json"):
            creds = Credentials.from_authorized_user_file(userID + "-token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                'client_secret.json',
                scopes=['https://www.googleapis.com/auth/drive.metadata.readonly'])    
                flow.redirect_uri = url_for('oauth2callback', _external=True)
                authorization_url, state = flow.authorization_url(
                    # Enable offline access so that you can refresh an access token without
                    # re-prompting the user for permission. Recommended for web server apps.
                    access_type='offline',
                    # Enable incremental authorization. Recommended as a best practice.
                    include_granted_scopes='true')
                session['state'] = state  
                session['userID'] = userID
                return redirect(authorization_url)

            # Save the credentials for the next run
            with open(userID+"-token.json", "w") as token:
                token.write(creds.to_json())

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


if __name__ == "__main__":
    reader = GoogleDocsReader()
    print(
        reader.load_data(document_ids=["11ctUj_tEf5S8vs_dk8_BNi-Zk8wW5YFhXkKqtmU_4B8"])
    )