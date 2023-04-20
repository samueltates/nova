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

def indexDocument(userID, file_content, file_name, file_type):
    #reconstruct file
    binary_data = base64.b64decode(file_content)

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

    name = queryIndex('give this document a title', index_json)
    name = str(name).strip()
    description = queryIndex('give this document a description', index_json) 
    description = str(description).strip()

    cartval = {
        'label': name,
        'type': 'index',
        'enabled': True,
        'description': description,
        # 'file':{file_content},
        'index': index_json,
    }

    tmpfile.close()
    newCart = nova.addCartridgeTrigger(userID, cartval)
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


def indexGoogleDoc(userID, docIDs):


    loader = GoogleDocsReader() 
    documents = loader.load_data(document_ids=[docIDs])
    
    index = GPTSimpleVectorIndex.from_documents(documents)

    # return

    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)

    index_json = json.load(open(tmpfile.name))
    name = queryIndex('give this document a title', index_json)
    name = str(name).strip()
    description = queryIndex('give this document a description', index_json) 
    description = str(description).strip()

    cartval = {
        'label': name,
        'type': 'index',
        'description': description,
        'enabled': True,
        # 'file':{file_content},
        'index': index_json,
    }

    tmpfile.close()
    newCart = nova.addCartridgeTrigger(userID, cartval)
    nova.eZprint('printing new cartridge')
    # print(newCart)
    return newCart


