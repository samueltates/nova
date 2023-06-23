import logging
import sys
import tempfile
import json
import base64
import os
from appHandler import app, websocket
from sessionHandler import novaConvo, available_cartridges, cartdigeLookup
import asyncio
from human_id import generate_id
from cartridges import addCartridgeTrigger
from debug import eZprint
from prismaHandler import prisma
from prisma import Json
from GoogleDocsReader import GoogleDocsReader 
from UnstructuredReader import UnstructuredReader
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
    StorageContext, load_index_from_storage,
    ServiceContext,
    GPTVectorStoreIndex
)

from llama_index.logger import LlamaLogger
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
# from IPython.display import Markdown, display


llm_predictor_gpt3 = LLMPredictor(llm=OpenAI(temperature=0, model_name="text-davinci-003"))

#query Index
from llama_index.indices.query.query_transform.base import StepDecomposeQueryTransform

async def indexDocument(payload):
    eZprint('indexDocument called')
    print(payload)

    userID = payload['userID']
    indexType = payload['indexType']
    tempKey = payload['tempKey']
    convoID = payload['convoID']
    sessionID = payload['sessionID']
    document = None
    documentTitle = None
    if payload['document_type'] == 'googleDoc':
        print('google doc triggered')
        gDocID = payload['gDocID']
        loader = GoogleDocsReader() 
        print(loader)
        try:
            print('loading data')
            document = await loader.load_data([gDocID], sessionID)
            documentTitle = await loader._get_title(str(gDocID), sessionID)
            print(document)
        except:
            print('document not found')
            payload = { 'key':tempKey,'fields': {'status': 'doc not found'}}
            await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

        print(document)
        
    elif payload['document_type'] == 'file':
        file_content = payload['file_content']
        file_name = payload['file_name']
        documentTitle = file_name
        file_type = payload['file_type']
        eZprint('reconstructing file')
        payload = { 'key':tempKey,'fields': {'status': 'file recieved, indexing'}}
        await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
        print(file_type)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="."+file_type.split('/')[1])
        temp_file.write(file_content)

        # Read and process the reconstructed file
        temp_file.close()
        
        unstructured_reader = UnstructuredReader()
        document = unstructured_reader.load_data(temp_file.name)
    # Cleanup: delete the temporary file after processing
        os.unlink(temp_file.name)


    index = None
# if(indexType == 'Vector'):
    index = GPTVectorStoreIndex.from_documents(document)
    eZprint('vector index created')
    # if(indexType == 'List'):
    #     index = GPTListIndex.from_documents(document)
    #     eZprint('list index created')

    # tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    tmpDir = tempfile.mkdtemp()+"/"+convoID+"/storage"
    index.storage_context.persist(tmpDir)
    print(tmpDir)
    indexJson = dict()
    for file in os.listdir(tmpDir):
        if file.endswith(".json"):
            content = json.load(open(os.path.join(tmpDir, file)))
            print(content)
            indexJson.update({file:content})
  

    key = generate_id()
    index_store = None
    vector_store = None
    docstore = None
    if 'index_store.json' in indexJson:
        index_store = indexJson['index_store.json']
    if 'vector_store.json' in indexJson:
        vector_store = indexJson['vector_store.json']
    if 'docstore.json' in indexJson:
        docstore = indexJson['docstore.json']    

    index_blob =  {
        'key' :key,
            'label': documentTitle,
            'type': 'index',
            'description': 'a document indexed to be queriable by NOVA',
            'enabled': True
    }

    index = await prisma.index .create(

        data = {'key' :key,
                'UserID' : userID,
                'docstore': Json(docstore),
                'index_store': Json(index_store),
                'vector_store': Json(vector_store),
                'blob': Json(index_blob),
        }
    )

  
    cartVal = {
        'label' : documentTitle,
        'type': 'index',
        'description': 'a document indexed to be queriable by NOVA',
        'enabled': True,
        'blocks': [],
        'index': key,
    }

    cartUpdate = {
        'userID' : userID,
        'convoID' : convoID,
        'cartVal': cartVal,
        }

    newCart = await addCartridgeTrigger(cartUpdate)
    payload = { 'key':tempKey,'fields': {'label':documentTitle, 'status': 'index created, getting summary'}}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    eZprint('printing new cartridge')
    return newCart

async def reconstructIndex(indexJson):
    tmpDir = tempfile.mkdtemp()
    # print(index)
    # nova.eZprint("reconstructIndex: tmpDir={}".format(tmpDir))
    # print(indexJson)
    llama_logger = LlamaLogger()
    service_context = ServiceContext.from_defaults(llama_logger=llama_logger)
    # service_context.set_global_service_context(service_context)
    print(indexJson)
    for key, val in indexJson.items():
        if key == 'index_store' or key == 'vector_store' or key == 'docstore':
            print(os.path.join(tmpDir, key))
            eZprint("reconstructIndex: key={}".format(key))
            print(val)
            # GPTListIndex.service_context = service_context
            # index = GPTListIndex.build_index_from_nodes(val)
            # print(index)

            try:
                with open(os.path.join(tmpDir, key + '.json'), "w") as f:
                    json.dump(val, f)
            except Exception as e:
                print(f"Error writing file: {str(e)}")

    storage_context = StorageContext.from_defaults(persist_dir=tmpDir, )
    storage_context.persist(tmpDir)
    eZprint("reconstructIndex: storage_context={}".format(storage_context))
    index = load_index_from_storage(storage_context)
   

    return index

    
async def queryIndex(queryString, index ):

    loop = asyncio.get_event_loop()
    query_engine = index.as_query_engine()
    response = await loop.run_in_executor(None, lambda: query_engine.query(queryString))
    eZprint(response)
    return response 


async def handle_nova_query(cartKey, cartVal, convoID, query):
    index_key = cartVal['index']
    indexJson = await get_index_json(index_key)
    index = await reconstructIndex(indexJson)
    insert = await queryIndex(query, index)
    if insert:
        cartVal['blocks'].append(insert)
        payload = { 'key': cartKey,'fields': {'blocks': cartVal['blocks'], 'status': 'index query complete'}}
        await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    return insert



async def quick_query(text, query):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    temp_file.write(text.encode())
    temp_file.seek(0)
    unstructured_reader = UnstructuredReader()
    document = unstructured_reader.load_data(temp_file.name)
    index = GPTVectorStoreIndex.from_documents(document)
    response = await queryIndex(query, index)
    return response



async def handleIndexQuery(input, loadout = None):
    cartKey = input['cartKey']
    convoID = input['convoID']

    query = input['query']
    #TODO -  basically could comine with index query (or this is request, query is internal)
    payload = { 'key': cartKey,
               'fields': {
            'status': 'querying Index',
            'state': 'loading'
            },
            'loadout': loadout
    }
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    eZprint('handling index query')
    cartVal = available_cartridges[convoID][cartKey]
    if cartVal['type'] == 'index' and cartVal['enabled'] == True :
        index_key = cartVal['index']
        index = await get_index_json(index_key)
        await triggerQueryIndex(convoID, cartKey, cartVal, query, index, index_key, loadout )


async def triggerQueryIndex(convoID, cartKey, cartVal, query, indexJson, index_key, loadout = None):
    userID = novaConvo[convoID]['userID']
    eZprint('triggering index query')
    oldVal = cartVal

    cartVal['state'] = 'loading'
    cartVal['status'] = 'index Found'
    payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'state': cartVal['state']
                                }}
    
    index = await reconstructIndex(indexJson)
    insert = await queryIndex(query, index)

    indexJson = dict()  

    tmpDir = tempfile.mkdtemp()+"/"+convoID+"/storage"
    index.storage_context.persist(tmpDir)
    print(tmpDir)
    indexJson = dict()
    for file in os.listdir(tmpDir):
        if file.endswith(".json"):
            content = json.load(open(os.path.join(tmpDir, file)))
            print(content)
            indexJson.update({file:content})


    index_store = None
    vector_store = None
    docstore = None

    if 'index_store.json' in indexJson:
        index_store = indexJson['index_store.json']
    if 'vector_store.json' in indexJson:
        vector_store = indexJson['vector_store.json']
    if 'docstore.json' in indexJson:
        docstore = indexJson['docstore.json']   

    index = await prisma.index.find_first(where={'key':index_key})

    update_index = await prisma.index.update(
        where={
                'id': index.id
        },
        data = {
                'docstore': Json(docstore),
                'index_store': Json(index_store),
                'vector_store': Json(vector_store),
        }
    )

    
    eZprint('index query complete')
    # eZprint(insert)
    if(insert != None):
        print('inserting')
        #TODO - replace this ID lookup with a key lookup
        cartVal['state'] = ''
        cartVal['status'] = ''
        if 'blocks' not in cartVal:
            cartVal['blocks'] = []
        if 'queries' not in cartVal:
            cartVal['blocks']['queries'] = []
        cartVal['blocks']['queries'].append({'query':query, 'response':str(insert)})
        payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }, 
                                'loadout':loadout
                                }
        id = cartdigeLookup[cartKey]

        matchedCart = await prisma.cartridge.find_first(
            where={
                    'id': id                                    
                      }
        )

        if matchedCart:
            updatedCart = await prisma.cartridge.update(
                where={ 'id': id },
                data={
                    'UserID': userID,
                    'blob' : Json({cartKey:cartVal})
                }
            )

        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

        
async def get_index_json(index_key):
    eZprint('getting cartridge detail')
    matchedCart = await prisma.index.find_first(
        where={
                'key': index_key
                }
    )
    dbRecord = json.loads(matchedCart.json())
    return dbRecord

