import logging
import sys
import tempfile
import json
import nova
import base64
import os
from appHandler import app, websocket
import asyncio

import GoogleDocsReader
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

UnstructuredReader = download_loader("UnstructuredReader")

async def indexDocument(payload):
    nova.eZprint('indexDocument called')
    print(payload)
    indexType = payload['indexType']
    sessionID = payload['sessionID']
    tempKey = payload['tempKey']
    userID = payload['userID']
    documents = None

    if payload['document_type'] == 'googleDoc':
        gDocID = payload['gDocID']
        loader = GoogleDocsReader() 
        documents = await loader.load_data(document_ids=[gDocID], userID=userID)
        print(documents)
        
    elif payload['document_type'] == 'file':
        file_content = payload['file_content']
        file_name = payload['file_name']
        file_type = payload['file_type']
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

    # tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    tmpDir = tempfile.mkdtemp()+"/"+sessionID+"/storage"
    index.storage_context.persist(tmpDir)
    print(tmpDir)
    indexJson = dict()
    for file in os.listdir(tmpDir):
        if file.endswith(".json"):
            content = json.load(open(os.path.join(tmpDir, file)))
            print(content)
            indexJson.update({file:content})
    # return


    storage_context = StorageContext.from_defaults(persist_dir=tmpDir)
    
    # save_to_disk(tmpfile.name)
    # tmpfile.seek(0)
    payload = { 'key':tempKey,'fields': {'status': 'index complete, getting title'}}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    index = load_index_from_storage(storage_context)
    name = await queryIndex('give this document a title', index, indexType)
    name = str(name).strip()
    blocks = []
    block = {'query': 'Document title', 'response': name}
    blocks.append(block)
    payload = { 'key':tempKey,'fields': {'blocks': blocks,'status': 'index complete, getting title'}}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    documentDescription = await queryIndex('Create a one sentence summary of this document, with no extraneous punctuation.', index, indexType) 
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
        'index': indexJson,
        'indexType': indexType,
    }

    newCart = await nova.addCartridgeTrigger(userID, sessionID, cartval)
    nova.eZprint('printing new cartridge')

    # print(newCart)
    return newCart

async def reconstructIndex(indexJson, sessionID):
    tmpDir = tempfile.mkdtemp()
    # print(index)
    # nova.eZprint("reconstructIndex: tmpDir={}".format(tmpDir))
    
    for key, val in indexJson.items():
        print(os.path.join(tmpDir, key))
        # indexPart = GPTListIndex.build_index_from_nodes(val)
        # print(indexPart)
        try:
            with open(os.path.join(tmpDir, key), "w") as f:
                json.dump(val, f)
        except Exception as e:
            print(f"Error writing file: {str(e)}")

    storage_context = StorageContext.from_defaults(persist_dir=tmpDir, )
    nova.eZprint("reconstructIndex: storage_context={}".format(storage_context))
    index = load_index_from_storage(storage_context)
    return index

    
async def queryIndex(queryString, index, indexType ):
    
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
        loop = asyncio.get_event_loop()
        query_engine = index.as_query_engine()
        response = await loop.run_in_executor(None, lambda: query_engine.query(queryString))
        nova.eZprint(response)
        return response 

