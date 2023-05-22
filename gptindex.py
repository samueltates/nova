import logging
import sys
import tempfile
import json
import nova
import base64
import os
from appHandler import app, websocket

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


from llama_index import (
    # GPTSimpleVectorIndex, 
    GPTListIndex,
    StringIterableReader,
    download_loader,
    SimpleDirectoryReader,
    LLMPredictor,
    PromptHelper,
    StorageContext, load_index_from_storage

)

from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
# from IPython.display import Markdown, display


llm_predictor_gpt3 = LLMPredictor(llm=OpenAI(temperature=0, model_name="text-davinci-003"))

#query Index
from llama_index.indices.query.query_transform.base import StepDecomposeQueryTransform

GoogleDocsReader = download_loader('GoogleDocsReader')
UnstructuredReader = download_loader("UnstructuredReader")

async def indexDocument(userID, sessionID, file_content, file_name, file_type, tempKey, indexType):
    nova.eZprint('reconstructing file')
    payload = { 'key':tempKey,'fields': {'status': 'file recieved, indexing'}}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    print(file_type)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="."+file_type.split('/')[1])
    temp_file.write(file_content)

    # Read and process the reconstructed file
    temp_file.close()

    unstructured_reader = UnstructuredReader()
    documents = unstructured_reader.load_data(temp_file.name)
    # Cleanup: delete the temporary file after processing
    os.unlink(temp_file.name)
    index = None
    if(indexType == 'Vector'):
        # index = GPTSimpleVectorIndex.from_documents(documents)
        nova.eZprint('vector index created')
    if(indexType == 'List'):
        index = GPTListIndex.from_documents(documents)
        nova.eZprint('list index created')

    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.storage_context.persist()
    storage_context = StorageContext.from_defaults(persist_dir="./storage")

    # save_to_disk(tmpfile.name)
    # tmpfile.seek(0)
    payload = { 'key':tempKey,'fields': {'status': 'index complete, getting title'}}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    index = load_index_from_storage(storage_context)
    name = queryIndex('give this document a title', index, indexType)
    name = str(name).strip()
    blocks = []
    block = {'query': 'Document title', 'response': name}
    blocks.append(block)
    payload = { 'key':tempKey,'fields': {'blocks': blocks,'status': 'index complete, getting title'}}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    documentDescription = queryIndex('Create a one sentence summary of this document, with no extraneous punctuation.', index, indexType) 
    documentDescription = str(documentDescription).strip()
    block = {'query': 'Document summary', 'response': documentDescription}
    blocks.append(block)
    payload = { 'key':tempKey,'fields': {'blocks': blocks, 'state':'', 'status':''}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

    cartval = {
        'label': name,
        'type': 'index',
        'description': 'a document indexed to be queriable by NOVA',
        'blocks': blocks,
        'enabled': True,
        # 'file':{file_content},
        # 'index': index_json,
        'indexType': indexType,
    }

    tmpfile.close()
    newCart = await nova.addCartridgeTrigger(userID, sessionID, cartval)
    nova.eZprint('printing new cartridge')

    # print(newCart)
    return newCart


def queryIndex(queryString, index, indexType ):
    
    # tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    # json.dump(index, tmpfile)
    # tmpfile.seek(0)
    # index = None
    if(indexType == 'Vector'):
        # index = GPTSimpleVectorIndex.load_from_disk(tmpfile.name)
        # index.set_text("Body of text uploaded to be summarised or have question answered")
        llm_predictor_gpt = LLMPredictor(llm=ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo"))

        step_decompose_transform = StepDecomposeQueryTransform(
        llm_predictor_gpt, verbose=True

        )
        response_gpt = index.query(
            queryString
        )
        nova.eZprint(response_gpt)
        return response_gpt
    if(indexType == 'List'):
        # index = GPTListIndex.load_from_disk(tmpfile.name)
        query_engine = index.as_query_engine()
        response = index.query_engine.query(queryString)
        nova.eZprint(response)
        return response




async def indexGoogleDoc(userID, sessionID, docIDs,tempKey, indexType):


    index = None
    loader = GoogleDocsReader() 
    documents = loader.load_data(document_ids=[docIDs])
    print(documents)
    if(indexType == 'Vector'):
        # index = GPTSimpleVectorIndex.from_documents(documents)
        nova.eZprint('vector index created')
    if(indexType == 'List'):
        index = GPTListIndex.from_documents(documents)
        nova.eZprint('list index created')

    # return

    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)

    index_json = json.load(open(tmpfile.name))
    name = queryIndex('give this document a title', index_json, indexType)
    name = str(name).strip()
    blocks = []
    block = {'query': 'give this document a title', 'response': name}
    blocks.append(block)
    payload = { 'key':tempKey,'fields': {'blocks': blocks}}
    # socketio.emit('updateCartridgeFields', payload) 
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    payload = { 'key':tempKey,'fields': {'status': 'query-description'}}
    # socketio.emit('updateCartridgeFields', payload)
    documentDescription = queryIndex('Create a one sentence summary of this document, with no extraneous punctuation.', index_json, indexType) 
    documentDescription = str(documentDescription).strip()
    block = {'query': 'Create a one sentence summary of this document, with no extraneous punctuation.', 'response': documentDescription}
    blocks.append(block)
    payload = { 'key':tempKey,'fields': {'blocks': blocks}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

    cartval = {
        'label': name,
        'type': 'index',
        'description': 'a document indexed to be queriable by NOVA',
        'blocks': blocks,
        'enabled': True,
        # 'file':{file_content},
        'index': index_json,
        'indexType': indexType,
    }

    tmpfile.close()
    newCart = await nova.addCartridgeTrigger(userID, sessionID, cartval)
    nova.eZprint('printing new cartridge')
    # print(newCart)
    #TO DO - add to running cartridges
    return newCart
