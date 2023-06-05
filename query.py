import openai
import os
import asyncio
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

async def sendChat(promptObj, model):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
    return response