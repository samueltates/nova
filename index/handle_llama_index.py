import logging
import sys
import tempfile
import json
import base64
import os
import asyncio
from human_id import generate_id
from prisma import Json
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


from session.appHandler import  websocket
from session.sessionHandler import novaSession
from session.prismaHandler import prisma
from core.cartridges import update_cartridge_field, get_cartridge_field
from tools.debug import eZprint, eZprint_anything
from file_handling.text_handler import parse_object_to_markdown, parse_elements_to_markdown

from tools.GoogleDocsReader import GoogleDocsReader 
from tools.UnstructuredReader import UnstructuredReader
from tools.UnstructuredURLLoader import UnstructuredURLLoader

from llama_index import (
    Document,
    LLMPredictor,
    StorageContext, load_index_from_storage,
    ServiceContext,
    VectorStoreIndex,
)

from llama_index.logger import LlamaLogger
from langchain.llms import OpenAI

llm_predictor_gpt3 = LLMPredictor(llm=OpenAI(temperature=0, model_name="text-davinci-003"))

DEBUG_KEYS = ['INDEX']  

async def handle_query(cartridge, query, sessionID, convoID, client_loadout):
    eZprint('handle query', DEBUG_KEYS, line_break=True)
    cartKey = cartridge.get('key', None)
    index_key = cartridge.get('index', None)
    index = None
    content = ''
    title = cartridge.get('label', '')
    userID = novaSession[sessionID]['userID']

    if cartridge.get('text'):
        content += parse_object_to_markdown(cartridge.get('text'))
    if cartridge.get('elements'):
        content += parse_elements_to_markdown(cartridge.get('elements'))


    if index_key is None:
        if content == '':
            eZprint('no content', DEBUG_KEYS)
        else:   
            index_key, index = await create_index(title, content, userID, sessionID)
            await update_cartridge_field({'sessionID': sessionID, 'cartKey': cartKey,
            'fields': {
                # 'label' : title,
                'index': index_key,
            }
            }, convoID, client_loadout, system=True)
            
    if index is None and index_key is not None:
        index = await get_index(index_key)

    response = await query_index(query, index)

    return response



async def create_index(title, content, userID, sessionID):
    eZprint('creating index', DEBUG_KEYS, line_break=True)
    doc = Document(text=content)
    index = VectorStoreIndex.from_documents([doc], llm_predictor=llm_predictor_gpt3)
    eZprint_anything(index, DEBUG_KEYS, message='index generated is')
    key = generate_id()

    eZprint_anything([index.vector_store, index.docstore], DEBUG_KEYS, message='subsections are')
    index_blob =  {
        'key' :key,
            'label': title,
            'type': 'index',
            'description': 'a document indexed to be queriable by NOVA',
            'enabled': True
    }


    index_store, default__vector_store, docstore = await serialise_index(key, index, sessionID)
    index_record = await prisma.index.create(
    
        data = {'key' :key,
                'UserID' : userID,
                'docstore': Json(docstore),
                'index_store': Json(index_store),
                'vector_store': Json(default__vector_store),
                'blob': Json(index_blob),
        }
    )
    
    return key, index
  

async def get_index (index_key):
    eZprint('getting index', DEBUG_KEYS, line_break=True)
    index = None
    if index_key is not None:
        index = await deserialise_index(index_key)
    return index    


async def query_index(queryString, index ):
    eZprint('querying index, query is : ' + queryString , DEBUG_KEYS, line_break=True)

    loop = asyncio.get_event_loop()
    query_engine = index.as_query_engine()
    response = await loop.run_in_executor(None, lambda: query_engine.query(queryString))
    eZprint(response, DEBUG_KEYS)
    
    return response 



async def serialise_index(index_key, index, sessionID):
    eZprint('serialising index', DEBUG_KEYS, line_break=True)
    index.set_index_id(index_key)
    tmpDir = tempfile.mkdtemp()+"/"+sessionID+"/storage"
    index.storage_context.persist(tmpDir)
    print(tmpDir)
    indexJson = dict()
    for file in os.listdir(tmpDir):
        if file.endswith(".json"):
            content = json.load(open(os.path.join(tmpDir, file)))
            # print(content)
            indexJson.update({file:content})

    index_store = None
    default__vector_store = None
    docstore = None
    if 'index_store.json' in indexJson:
        index_store = indexJson['index_store.json']
    if 'default__vector_store.json' in indexJson:
        default__vector_store = indexJson['default__vector_store.json']
    if 'docstore.json' in indexJson:
        docstore = indexJson['docstore.json']    

    return index_store, default__vector_store, docstore
        


async def deserialise_index(index_key):
    eZprint('getting index from db', DEBUG_KEYS, line_break=True)
    index_record = await prisma.index.find_first(
        where={
                'key': index_key
                }
    )
    dbRecord = json.loads(index_record.json())
    tmpDir = tempfile.mkdtemp()

    for key, val in dbRecord.items():
        try:
            with open(os.path.join(tmpDir, key + '.json'), "w") as f:
                json.dump(val, f)
                # eZprint("reconstructIndex: wrote file {}".format(os.path.join(tmpDir, key + '.json')))
        except Exception as e:
            print(f"Error writing file: {str(e)}")

    storage_context = StorageContext.from_defaults(persist_dir=tmpDir)
    eZprint("reconstructIndex: storage_context={}".format(storage_context), DEBUG_KEYS)
    index = load_index_from_storage(storage_context)   

    return index
