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


def indexDocument(userID, file_content, file_name):

    string = base64.b64decode(file_content).decode('utf-8')
    strings = [string,'']
    documents = StringIterableReader().load_data(strings)
    index = GPTSimpleVectorIndex(documents)
    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)

    index_json = json.load(open(tmpfile.name))

    cartval = {
        'label': file_name,
        'type': 'index',
        'enabled': True,
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
    index.set_text("Body of text uploaded to be summarised or have question answered")
    llm_predictor_gpt4 = LLMPredictor(llm=ChatOpenAI(temperature=0, model_name="gpt-4"))

    step_decompose_transform = StepDecomposeQueryTransform(
    llm_predictor_gpt4, verbose=True

    )
    response_gpt4 = index.query(
        queryString,
        query_transform=step_decompose_transform,
        llm_predictor=llm_predictor_gpt4
    )
    nova.eZprint(response_gpt4)
    return response_gpt4

def indexGoogleDoc(userID, docIDs, file_name):
    loader = GoogleDocsReader()
    documents = loader.load_data(document_ids=docIDs)
    
    index = GPTSimpleVectorIndex(documents)

    # return

    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)

    index_json = json.load(open(tmpfile.name))

    cartval = {
        'label': file_name,
        'type': 'index',
        'enabled': True,
        # 'file':{file_content},
        'index': index_json,
    }

    tmpfile.close()
    newCart = nova.addCartridgeTrigger(userID, cartval)
    nova.eZprint('printing new cartridge')
    # print(newCart)
    return newCart


