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
    SimpleDirectoryReader,
    LLMPredictor,
    PromptHelper
)

from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from IPython.display import Markdown, display

# LLM Predictor (gpt-3)
llm_predictor_gpt3 = LLMPredictor(llm=OpenAI(temperature=0, model_name="text-davinci-003"))

# LLMPredictor (gpt-4)
llm_predictor_gpt4 = LLMPredictor(llm=ChatOpenAI(temperature=0, model_name="gpt-4"))

#query Index
from llama_index.indices.query.query_transform.base import StepDecomposeQueryTransform
# gpt-4
step_decompose_transform = StepDecomposeQueryTransform(
    llm_predictor_gpt4, verbose=True
)

# import openai
# import os

def indexDocument(userID, file_content, file_name):

    string = base64.b64decode(file_content).decode('utf-8')
    strings = [string,'']
    documents = StringIterableReader().load_data(strings)
    print(documents)
    index = GPTSimpleVectorIndex(documents)
    # print(index)
    # index. 
    # for dex in index:
    #     print(dex)
    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    index.save_to_disk(tmpfile.name)
    tmpfile.seek(0)
    # print(tmpfile)
    # index_json=json.load(tmpfile)
    index_json = json.load(open(tmpfile.name))
    print(index_json)

    # # for doc in index_json:
    # #     print(doc)
    # # for doc in index_json["docstore"]["docs"]:
    cartval = {
        'label': file_name,
        'type': 'index',
        'enabled': True,
        # 'file':{file_content},
        'index': index_json,
    }

    tmpfile.close()
    newCart = nova.addCartridgeTrigger(userID, cartval)

    return newCart

    # with tempfile.NamedTemporaryFile() as tmpfile:

    #     index.save_to_disk(tmpfile.name)
    #     tmpfile.seek(0)
    #     index_json=json.load(tmpfile)
    #     for doc in index_json["docstore"]["docs"]:
    #         cartval = {file_name : {
    #             "label": file_name,
    #             "type": "index",
    #             "enabled": True,
    #             "file":file_content,
    #             "index": doc,
    #         }}
    #         newCart = addCartridgeTrigger(userID, cartval)
    # return newCart



# index = GPTSimpleVectorIndex(documents)
# index.save_to_disk('index_simple.json')
# index = GPTSimpleVectorIndex.load_from_disk('index_simple.json')

def queryIndex(storedIndex, queryString):
    print(storedIndex)
    tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False, suffix=".json")
    json.dump(storedIndex, tmpfile)
    tmpfile.seek(0)

    index = GPTSimpleVectorIndex.load_from_disk(tmpfile.name)
    response_gpt4 = index.query(
        queryString,
        query_transform=step_decompose_transform,
        llm_predictor=llm_predictor_gpt4
    )
    print(response_gpt4)
    return response_gpt4


# # gpt-3
# step_decompose_transform_gpt3 = StepDecomposeQueryTransform(
#     llm_predictor_gpt3, verbose=True
# )

# index.set_text("Used to extract key decisions and actions from a meeting.")

# response_gpt4 = index.query(
#     "This is a meeting from XR company PHORIA, working on mixed reality project about the daintree, doing a retro on the project. Find any specific actions discussed, who reccomendeded them, and document them in an actionable way. Also identify any key themes that arose, or decisions that were made, or questions left to be answered.",
#     query_transform=step_decompose_transform,
#     llm_predictor=llm_predictor_gpt4
# )


# display(Markdown(f"<b>{response_gpt4}</b>"))
# print(response_gpt4)

# # response = index.query("", response_mode="tree_summarize")
# # str(response)
# # print(response)
# # print(response.get_formatted_sources())

# # for resp in response:
# #     print(resp)


