import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

from llama_index import (
    GPTSimpleVectorIndex, 
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
# import openai
# import os
documents = SimpleDirectoryReader('data').load_data()
index = GPTSimpleVectorIndex(documents)
index.save_to_disk('index_simple.json')
index = GPTSimpleVectorIndex.load_from_disk('index_simple.json')

#query Index
from llama_index.indices.query.query_transform.base import StepDecomposeQueryTransform
# gpt-4
step_decompose_transform = StepDecomposeQueryTransform(
    llm_predictor_gpt4, verbose=True
)

# gpt-3
step_decompose_transform_gpt3 = StepDecomposeQueryTransform(
    llm_predictor_gpt3, verbose=True
)

index.set_text("Used to extract key decisions and actions from a meeting.")

response_gpt4 = index.query(
    "This is a meeting from XR company PHORIA, working on mixed reality project about the daintree, doing a retro on the project. Find any specific actions discussed, who reccomendeded them, and document them in an actionable way. Also identify any key themes that arose, or decisions that were made, or questions left to be answered.",
    query_transform=step_decompose_transform,
    llm_predictor=llm_predictor_gpt4
)


display(Markdown(f"<b>{response_gpt4}</b>"))

# response = index.query("", response_mode="tree_summarize")
# str(response)
# print(response)
# print(response.get_formatted_sources())

# for resp in response:
#     print(resp)


