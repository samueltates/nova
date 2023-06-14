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
from chat import agent_initiate_convo
#NOVA STUFF
from appHandler import app, websocket
from sessionHandler import novaConvo, availableCartridges, chatlog, cartdigeLookup, novaSession, current_loadout
from prismaHandler import prisma
from memory import summarise_convos, get_summaries, update_cartridge_summary

from keywords import get_summary_keywords
from debug import fakeResponse, eZprint

agentName = "nova"
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

 
##CARTRIDGE MANAGEMENT




async def initialise_conversation(convoID, params = None):
    ##session setup stuff should be somewhere else
    eZprint('initialising conversation')
    print(params)
    if 'fake_user' in params and params['fake_user'] == 'True':
        eZprint('fake user detected')
        novaConvo[convoID]['fake_user'] = True 
        novaConvo[convoID]['userName'] = "Archer"

    if 'agent_initiated' in params and params['agent_initiated'] == 'True':
        eZprint('agent initiated convo')
        novaConvo[convoID]['agent_initiated'] = True

    if convoID not in novaConvo:
        novaConvo[convoID] = {}
    novaConvo[convoID]['agent_name'] = agentName
    novaConvo[convoID]['token_limit'] = 4000
    sessionID = novaConvo[convoID]['sessionID'] 
    novaSession[sessionID]['latestConvo']= convoID

async def initialiseCartridges(convoID):
    
    eZprint('intialising cartridges')

    novaConvo[convoID]['owner'] = True
    await loadCartridges(convoID)
    await runCartridges(convoID)


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
                if 'softDelete' not in cartVal or cartVal['softDelete'] == False:
                    availableCartridges[convoID][cartKey] = cartVal
                    cartdigeLookup.update({cartKey: cartridge.id}) 
                    # if cartVal['type'] == 'summary':
                    #     cartVal.update({'state': 'loading'})
        # print('available cartridges are ' + str(availableCartridges[convoID]))
        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))
    eZprint('load cartridges complete')

async def runCartridges(convoID):
    userID = novaConvo[convoID]['userID']
    if 'agent_initiated' in novaConvo[convoID] and novaConvo[convoID]['agent_initiated'] == True:
        await agent_initiate_convo(convoID)
    if convoID in availableCartridges:
        for cartKey, cartVal in availableCartridges[convoID].items():
            if cartVal['type'] == 'summary':
                cartVal['blocks'] = []
                loadout = None
                if 'loadout' in cartVal:
                    loadout = cartVal['loadout']
                print('loadout is ' + str(loadout))
                
                if (convoID in current_loadout and current_loadout[convoID] == loadout) or convoID not in current_loadout:
                    eZprint('running cartridge')
                    print('running cartridge: ' + str(cartVal['label']))
                    print('loadout is ' + str(loadout))
                    await get_summaries(userID, convoID, loadout)
                    await update_cartridge_summary(userID, cartKey, cartVal, convoID)
                    # asyncio.create_task(get_summary_keywords(convoID, cartKey, cartVal))
                    # asyncio.create_task(eZprint('running cartridge: ' + str(cartVal)))
                    await summarise_convos(convoID, cartKey, cartVal, loadout)
                    # print(availableCartridges[convoID])
                    await update_cartridge_summary(userID, cartKey, cartVal, convoID)
                    print('ending run')

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

