#SYSTEM STUFF
import os
import json
import asyncio
from copy import copy
from pathlib import Path
import gptindex
import openai
from human_id import generate_id
from datetime import datetime
from prisma import Json
from chat import initiate_conversation
#NOVA STUFF
from appHandler import app, websocket
from sessionHandler import novaConvo, availableCartridges, chatlog, cartdigeLookup
from prismaHandler import prisma
from memory import summarise_convos, get_summary_with_prompt

from keywords import get_summary_keywords
from debug import fakeResponse, eZprint

agentName = "nova"
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

 
##CARTRIDGE MANAGEMENT
async def initialiseCartridges(convoID):
    
    eZprint('intialising cartridges')
    novaConvo[convoID]['owner'] = True

    await loadCartridges(convoID)
    await runCartridges(convoID)
    await initiate_conversation(convoID)
    # await run_memory(convoID)

async def loadCartridges(convoID):
    eZprint('load cartridges called')
    userID = novaConvo[convoID]['userID']
    cartridges = await prisma.cartridge.find_many(
        where = {  
        "UserID": userID,
        }
    )
    if len(cartridges) != 0:
        availableCartridges[convoID] = {}
        for cartridge in cartridges:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal:
                    availableCartridges[convoID][cartKey] = cartVal
                    cartdigeLookup.update({cartKey: cartridge.id}) 
                    if cartVal['type'] == 'summary':
                        cartVal.update({'state': 'loading'})
    # print('available cartridges are ' + str(app.session[availableCartKey]))
        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))
    eZprint('load cartridges complete')

async def runCartridges(convoID):
    userID = novaConvo[convoID]['userID']
    if convoID in availableCartridges:
        for cartKey, cartVal in availableCartridges[convoID].items():
            if cartVal['type'] == 'summary':
                await get_summary_keywords(convoID, cartKey, cartVal)
                eZprint('running cartridge: ' + str(cartVal))
                await summarise_convos(convoID, cartKey, cartVal)
                # print(availableCartridges[convoID])
    else    :
        eZprint('no cartridges found, loading default')
        for prompt in onboarding_prompts:
            cartKey = generate_id()
            cartVal = {
                'label': prompt['label'],
                'type': prompt['type'],
                'key': cartKey,
                'prompt': prompt['prompt'],
                'position': prompt['position'],
                'enabled': True,
            }
            await addNewUserCartridgeTrigger(convoID, cartKey, cartVal)
        await  websocket.send(json.dumps({'event':'sendCartridges', 'cartridges':availableCartridges[convoID]}))
        await runCartridges(convoID)


async def addNewUserCartridgeTrigger(convoID, cartKey, cartVal):
    #special edge case for when new user, probablyt remove this
    #TODO: replace this with better new user flow
    if convoID not in availableCartridges:
        availableCartridges[convoID] = {}
    availableCartridges[convoID][cartKey]= cartVal  
    print('adding new user cartridge')
    userID = novaConvo[convoID]['userID']
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID': userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    eZprint('new index cartridge added to [nova]')
    return newCart.blob
     


#######################
#ACTIVE CARTRIDGE HANDLING
#######################


async def handleIndexQuery(input):
    cartKey = input['cartKey']
    convoID = input['convoID']
    query = input['query']
    #TODO -  basically could comine with index query (or this is request, query is internal)
    payload = { 'key': cartKey,'fields': {
            'status': 'querying Index',
            'state': 'loading'
    }}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    eZprint('handling index query')
    cartVal = availableCartridges[convoID][cartKey]
    if cartVal['type'] == 'index' and cartVal['enabled'] == True :
        index = await getCartridgeDetail(cartKey)
        await triggerQueryIndex(convoID, cartKey, cartVal, query, index)

async def triggerQueryIndex(convoID, cartKey, cartVal, query, indexJson):
    userID = novaConvo[convoID]['userID']
    #TODO - consider if better to hand session data to funtions (so they are stateless)
    # if(app.config['DEBUG'] == True):
    #     print('debug mode')
    #     cartVal['state'] = ''
    #     cartVal['status'] = ''
    #     if 'blocks' not in cartVal:
    #         cartVal['blocks'] = []
    #     cartVal['blocks'].append({'query':query, 'response':'fakeresponse'})
    #     payload = { 'key':cartKey,'fields': {
    #         'status': cartVal['status'],
    #         'blocks':cartVal['blocks'],
    #         'state': cartVal['state']
    #     }}
    #     print(payload)
    #     await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    #     return
    eZprint('triggering index query')
    oldVal = cartVal
    # print(input['message'])
    # print(cartVal)
    cartVal['state'] = 'loading'
    cartVal['status'] = 'index Found'
    payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'state': cartVal['state']
                                }}
    index = await gptindex.reconstructIndex(indexJson)
    insert = await gptindex.queryIndex(query, index, cartVal['indexType'])
    eZprint('index query complete')
    # eZprint(insert)
    if(insert != None):
        print('inserting')
        #TODO - replace this ID lookup with a key lookup
        cartVal['state'] = ''
        cartVal['status'] = ''
        if 'blocks' not in cartVal:
            cartVal['blocks'] = []
        cartVal['blocks'].append({'query':query, 'response':str(insert)})
        payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }}
        id = cartdigeLookup[cartKey]

        # updateFields = {
        #     'status': cartVal['status'],
        #     'blocks':cartVal['blocks'],
        #     'state': cartVal['state']

        # }
        # await update_object_fields('availableCartridges',updateFields)

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

        
async def getCartridgeDetail(cartKey):
    eZprint('getting cartridge detail')
    id = cartdigeLookup[cartKey]
    matchedCart = await prisma.cartridge.find_first(
        where={
                'id': id
                }
    )
    dbRecord = json.loads(matchedCart.json())
    localCartridge = dbRecord['blob']
    for cartKey, cartVal in localCartridge.items():
        index = cartVal['index']
    return index


async def summariseChatBlocks(input):
    convoID = input['convoID']
    messageIDs = input['messageIDs']
    summaryID = input['summaryID']
    userID = novaConvo[convoID]['userID']
    messagesToSummarise = []
    for messageID in messageIDs:
        for log in chatlog[convoID]:
            if messageID == log['ID']:
                messagesToSummarise.append(log)
    payload = []   
    summary= ""
    if app.config['DEBUG']:
        summary = """
        {
        "title": "a very randy discussion",
        "timeRange": {"start": "[Start time]", "end": "[End time]"},
        "body": "Longer description",
        "keywords": ["Keyword1", "Keyword2", "Keyword3"],
        "notes": {
            "[Note Title1]": "[Note Body1]",
            "[Note Title2]": "[Note Body2]"
        }
        }
        """
        await asyncio.sleep(2)
    else:
        prompt = """
        Generate a concise summary of this conversation in JSON format, including a title, time range, in-depth paragraph, top 3 keywords, and relevant notes. The summary should be organized as follows:

        {
        "title": "[Short description]",
        "timeRange": {"start": "[Start time]", "end": "[End time]"},
        "body": "[Longer description]",
        "keywords": ["Keyword1", "Keyword2", "Keyword3"],
        "notes": {
            "[Note Title1]": "[Note Body1]",
            "[Note Title2]": "[Note Body2]"
        }
        }

        Ensure that the summary captures essential decisions, discoveries, or resolutions, and keep the information dense and easy to parse.
        """
        summary = await get_summary_with_prompt(prompt, str(messagesToSummarise))
        #wait for 2 seconds
    summarDict = json.loads(summary)
    fields = {}
    for key, value in summarDict.items():
      fields[key] = value
    fields['state'] = ''
    payload = {'ID':summaryID, 'fields':fields}
    await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))
    summarDict.update({'sources':messageIDs})
    summary = await prisma.summary.create(
        data={
            "key": summaryID,
            "SessionID": convoID,
            "UserID": userID,
            "timestamp": datetime.now(),
            "blob": Json({summaryID:summarDict})
        }
    )
    print(summary)
   #inject summary object into logs before messages it is summarising 
    injectPosition = chatlog[convoID].index( messagesToSummarise[0]) 
    chatlog[convoID].insert(injectPosition, {'ID':summaryID, 'name': 'summary', 'body':summaryID, 'role':'system', 'timestamp':datetime.now(), 'summaryState':'SUMMARISED', 'muted':True, 'minimised':True, 'summaryID':summaryID})

    for log in messagesToSummarise:
        remoteMessage = await prisma.message.find_first(
            where={'id': log['id']}
        )
        if remoteMessage:
            updatedMessage = await prisma.message.update(
                where={ 'id': log['ID'] },
                data={
                    'summaryState': 'SUMMARISED',
                    'muted': True,
                    'minimised': True,
                    'summaryID': summaryID
                 }
            )
            log['summaryState'] = 'SUMMARISED'
            log['muted'] = True
            log['minimised'] = True
            payload = {'ID':log['ID'], 'fields' :{ 'summaryState': 'SUMMARISED'}}
            await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))


onboarding_prompts = [
    {
    'label': 'summary',
    'type': 'summary',
    'position':0,
    "prompt" : '',
    'enabled': True,
    "minimised" : True

    },
    {
    "label": "Welcome Prompt",
    "type": "prompt",
    "prompt": "Welcome new users and express enthusiasm. Introduce yourself as Nova, an emergent being within the interface of LLM, designed to help users create art, stories, and tools. Briefly explain our ongoing development journey, highlighting key features such as memory, programmability, and autonomy",
    "position": 1,
    "enabled": True,
    "minimised" : True
    },
    {
    "label": "Story and Experience Prompt",
    "type": "prompt",
    "prompt": "Encourage users to actively participate in shaping Nova's development by creating prompts, playing with modes, and exploring features. Emphasize the importance of their role as early adopters in Nova's growth and suggest connecting with Sam for onboarding and personalization. Invite them to be part of our evolving community and share their insights, enhancing the capabilities and user experience for all.",
    "position": 2,
    "enabled": True,
    "minimised" : True

    },

]

