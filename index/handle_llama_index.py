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

from llama_index.retrievers import QueryFusionRetriever

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
    SimpleKeywordTableIndex,
    VectorStoreIndex,
)

from llama_index.logger import LlamaLogger
from llama_index.indices.composability import ComposableGraph

from langchain_openai import ChatOpenAI
llm_predictor_gpt3 = LLMPredictor(llm=ChatOpenAI(temperature=0, model_name="text-davinci-003"))

DEBUG_KEYS = ['INDEX']  

async def handle_cartridge_query(cartridge, query, sessionID, convoID, client_loadout):
    eZprint('handle query', DEBUG_KEYS, line_break=True)

    index = await retrieve_cartridge_index(cartridge, sessionID, convoID, client_loadout)
    response = await query_index(query, index)

    return response

async def retrieve_cartridge_index(cartridge, sessionID, convoID, client_loadout):
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

    return index

async def handle_multi_cartridge_query(cartridges, query, sessionID, convoID, client_loadout):
    eZprint('handle multi query', DEBUG_KEYS, line_break=True)
    llm_gpt4 = ChatOpenAI(temperature=0, model="gpt-4")
    service_context = ServiceContext.from_defaults(llm=llm_gpt4, chunk_size=1024)


    #based on https://docs.llamaindex.ai/en/stable/understanding/putting_it_all_together/q_and_a/unified_query.html
    vector_indices = {}
    index_summaries = {}
    for cartridge in cartridges:
        index = await retrieve_cartridge_index(cartridge, sessionID, convoID, client_loadout)
        label = cartridge.get('label', '')
        eZprint(label, DEBUG_KEYS, message = 'returned_label')
        vector_indices[label] = index
        summary = cartridge.get('summary', None)
        if summary is None:
            summary = await get_summary(index)
            await update_cartridge_field({'sessionID': sessionID, 'cartKey': cartridge['key'],
            'fields': {
                # 'label' : title,
                'summary': str(summary),
            }
            }, convoID, client_loadout, system=True)
            


        index_summaries[label] = str(summary)
    
    eZprint_anything([vector_indices, index_summaries], DEBUG_KEYS, message = 'vectors and summaries')

    graph = ComposableGraph.from_indices(
        SimpleKeywordTableIndex,
        [index for _, index in vector_indices.items()],
        [summary for _, summary in index_summaries.items()],
        max_keywords_per_chunk=50,
    )
    eZprint(graph, DEBUG_KEYS, message= 'whole graph')
    eZprint(graph.index_struct, DEBUG_KEYS, message = 'graph index struct')
    # eZprint(graph.index_struct.get('root_id', ''), DEBUG_KEYS, 'root ID apparentluy')
    # root_index = graph.get_index(
    #     graph.index_struct.root_id, SimpleKeywordTableIndex
    # )

    # root_index.set_index_id("compare_contrast")
    # root_summary = (
    #     "This index contains documents that are being queried by an AI agent, use it to answer questions across documents"
    # )
    from llama_index.indices.query.query_transform.base import (
        DecomposeQueryTransform,
    )

    decompose_transform = DecomposeQueryTransform(verbose=True)

    # define custom query engines
    from llama_index.query_engine.transform_query_engine import (
        TransformQueryEngine,
    )

    custom_query_engines = {}
    for key, index in vector_indices.items():
        query_engine = index.as_query_engine(service_context=service_context)
        summary = index_summaries.get(key,'')
        query_engine = TransformQueryEngine(
            query_engine,
            query_transform=decompose_transform,
            transform_metadata={"index_summary": summary},
        )
        custom_query_engines[index.index_id] = query_engine
    
    custom_query_engines[graph.root_id] = graph.root_index.as_query_engine(
        retriever_mode="simple",
        response_mode="tree_summarize",
        service_context=service_context,
    )

    # eZprint_anything(custom_query_engines, DEBUG_KEYS, message = 'query engines')
    query_engine = graph.as_query_engine(custom_query_engines=custom_query_engines)
    # eZprint_anything(query_engine.get_prompts(), DEBUG_KEYS, "query engine getprompts")
    
    response = query_engine.query(query)
    return response

    # eZprint_anything(indexes, DEBUG_KEYS, message='subsections are')
    # docstores = {}
    # index_store = {}
    # vector_store = {}

    # # Assume index.docstore, index.index_store, and index.vector_store are dictionaries
    # for index in vector_indices.items():
    #     if index.docstore is not None:
    #         eZprint_anything(index.docstore, DEBUG_KEYS, message='subsections are')
    #         # docstores.update(index.docstore)

    #     # if index.index_store is not None:
    #     #     index_store.update(index.index_store)
    #     if index.vector_store is not None:
    #         vector_store.update(index.vector_store)

    # # Now, instead of lists, we have single dictionaries with all key-value pairs merged
    # storage_context = StorageContext.from_dict(
    #     {
    #         "docstore": docstores,
    #         "index_store": index_store,
    #         "vector_store": vector_store,
    #     }
    # )


    # index = load_index_from_storage(storage_context)
    # response = await query_index(query, index)
    # eZprint_anything(response, DEBUG_KEYS, message='subsections are')
    # return response

    


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

async def get_summary(index):
    summary = await query_index('provide a short summary of this document', index)
    return summary


async def serialise_index(index_key, index, sessionID):
    eZprint('serialising index', DEBUG_KEYS, line_break=True)
    index.set_index_id(index_key)
    tmpDir = tempfile.mkdtemp()+"/"+sessionID+"/storage"
    index.storage_context.persist(tmpDir)
    eZprint(tmpDir, DEBUG_KEYS)
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
    eZprint(tmpDir, DEBUG_KEYS)

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
