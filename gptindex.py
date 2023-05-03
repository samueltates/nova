import logging
import sys
import tempfile
import json
import nova
import base64
import os

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


from llama_index import (
    GPTSimpleVectorIndex, 
    StringIterableReader,
    download_loader,
    SimpleDirectoryReader,
    LLMPredictor,
    PromptHelper
)

from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
# from IPython.display import Markdown, display


llm_predictor_gpt3 = LLMPredictor(llm=OpenAI(temperature=0, model_name="text-davinci-003"))

#query Index
from llama_index.indices.query.query_transform.base import StepDecomposeQueryTransform

GoogleDocsReader = download_loader('GoogleDocsReader')
UnstructuredReader = download_loader("UnstructuredReader")

async def indexDocument(userID, sessionID, file_content, file_name, file_type, tempKey):
    #reconstruct file
    binary_data = base64.b64decode(file_content)
    nova.eZprint('reconstructing file')
    # payload = { 'key':tempKey,'fields': {'status': 'indexing'}}
    # socketio.emit('updateCartridgeFields', payload)

    # Save the binary data to a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="."+file_type.split('/')[1])
    temp_file.write(binary_data)

    # Read and process the reconstructed file
    temp_file.close()

    unstructured_reader = UnstructuredReader()
    documents = unstructured_reader.load_data(temp_file.name)
    # Cleanup: delete the temporary file after processing
    os.unlink(temp_file.name)


    index = GPTSimpleVectorIndex.from_documents(documents)
    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)
    
    index_json = json.load(open(tmpfile.name))
        
    payload = { 'key':tempKey,'fields': {'status': 'query: name'}}
    # socketio.emit('updateCartridgeFields', payload)
    name = queryIndex('give this document a title', index_json)
    name = str(name).strip('\"')
    payload = { 'key':tempKey,'fields': {'label': name}}
    # socketio.emit('updateCartridgeFields', payload)
    description = queryIndex('give this document a description', index_json) 
    description = str(description).strip('\"')
    # payload = { 'key':tempKey,'fields': {'blocks': {description}}, 'action':'append'}
    # socketio.emit('updateCartridgeFields', payload)
    
    cartval = {
        'label': name,
        'type': 'index',
        'enabled': True,
        'description': 'a document indexed to be queriable by NOVA',
        'blocks': [description],
        # 'file':{file_content},
        'index': index_json,
    }

    tmpfile.close()
    newCart = await nova.addCartridgeTrigger(userID, sessionID, cartval)
    nova.eZprint('printing new cartridge')

    # print(newCart)
    return newCart


def queryIndex(queryString, storedIndex ):
    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    json.dump(storedIndex, tmpfile)
    tmpfile.seek(0)

    index = GPTSimpleVectorIndex.load_from_disk(tmpfile.name)
    # index.set_text("Body of text uploaded to be summarised or have question answered")
    llm_predictor_gpt4 = LLMPredictor(llm=ChatOpenAI(temperature=0, model_name="gpt-4"))

    step_decompose_transform = StepDecomposeQueryTransform(
    llm_predictor_gpt4, verbose=True

    )
    response_gpt4 = index.query(
        queryString
    )
    nova.eZprint(response_gpt4)
    return response_gpt4


async def indexGoogleDoc(userID, sessionID, docIDs,tempKey):

    payload = { 'key':tempKey,'fields': {'status': 'indexing'}}
    # socketio.emit('updateCartridgeFields', payload)

    loader =    GoogleDocsReader() 
    documents = loader.load_data(document_ids=[docIDs])
    
    index = GPTSimpleVectorIndex.from_documents(documents)

    # return

    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)

    payload = { 'key':tempKey,'fields': {'status': 'query-name'}}
    # socketio.emit('updateCartridgeFields', payload)

    index_json = json.load(open(tmpfile.name))
    name = queryIndex('give this document a title', index_json)
    name = str(name).strip()
    payload = { 'key':tempKey,'fields': {'label': name}}
    # socketio.emit('updateCartridgeFields', payload) 

    payload = { 'key':tempKey,'fields': {'status': 'query-description'}}
    # socketio.emit('updateCartridgeFields', payload)
    blocks = []
    documentDescription = queryIndex('Create a one sentence summary of this document, with no extraneous punctuation.', index_json) 
    documentDescription = str(documentDescription).strip()
    blocks.append(documentDescription)
    cartval = {
        'label': name,
        'type': 'index',
        'description': 'a document indexed to be queriable by NOVA',
        'blocks': blocks,
        'enabled': True,
        # 'file':{file_content},
        'index': index_json,
    }

    tmpfile.close()
    newCart = await nova.addCartridgeTrigger(userID, sessionID, cartval)
    nova.eZprint('printing new cartridge')
    # print(newCart)
    #TO DO - add to running cartridges
    return newCart


