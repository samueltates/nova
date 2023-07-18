from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document
import googleapiclient.discovery as discovery

from typing import Any, List
from googleAuth import getDocService


class GoogleDocsReader(BaseReader):
    """Google Docs reader.

    Reads a page from Google Docs

    """


    async def load_data(self, document_ids: List[str], sessionID) -> List[Document]:
        """Load data from the input directory.

        Args:
            document_ids (List[str]): a list of document ids.
        """
        if document_ids is None:
            raise ValueError('Must specify a "document_ids" in `load_kwargs`.')
        # print(document_ids)
        results = []
        for document_id in document_ids:
            # print(document_id)
            docResult = await self._load_doc(document_id, sessionID)
            # print(docResult)
            doc = docResult['content']
            docTitle = docResult['title']
            # print(docTitle)
            results.append(Document(doc, extra_info={"document_id": document_id, "document_title": docTitle}))
        return results

    async def _get_title(self, document_id:str, sessionID):
        docs_service = await getDocService(sessionID)
        doc = docs_service.documents().get(documentId=document_id).execute()
        doc_title = doc.get("title")
        return doc_title
    
    async def _load_doc(self, document_id: str, sessionID) -> str:
        """Load a document from Google Docs.

        Args:
            document_id: the document id.

        Returns:
            The document text.
        """
        # print('load_÷doc route hit')
        docs_service = await getDocService(sessionID)
        # print('got service')
        # print(docs_service.documents())
        # print(docs_service)
        doc = docs_service.documents().get(documentId=document_id).execute()
        # print('got doc')
        # print(doc)
        doc_content = doc.get("body").get("content")
        doc_title = doc.get("title")
        # await nova.updateAuth(credentials)
        doc_info = {
            "title": doc_title,
            "content": self._read_structural_elements(doc_content)
        }

        return doc_info


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
