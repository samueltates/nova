import openai
import os
import asyncio
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

async def sendChat(promptObj, model):
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
    except:
        try:
            response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
        except Exception as e:
            print(e)
            print(promptObj)
            response = "Assistant did not return a message"

    return response



async def get_summary_with_prompt(prompt, textToSummarise):

    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    # print(textToSummarise)
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    # print(response)
    content = response["choices"][0]["message"]["content"]
    # print(content)
    return content