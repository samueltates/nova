#SYSTEM STUFF
import os
import json
import asyncio
from copy import copy
from pathlib import Path
import openai
from human_id import generate_id
from datetime import datetime
from prisma import Json
from chat import agent_initiate_convo, construct_query
#NOVA STUFF
from appHandler import app, websocket
from sessionHandler import novaConvo, available_cartridges, chatlog, cartdigeLookup, novaSession, current_loadout, current_config
from prismaHandler import prisma
from memory import run_summary_cartridges
from cartridges import update_cartridge_field
from query import get_summary_with_prompt
from keywords import get_keywords_from_summaries
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

    if 'name' in params:
        novaConvo[convoID]['userName'] = params['name']

    if 'message' in params:
        novaConvo[convoID]['message'] = params['message']
        print(params['message'])
        
    novaConvo[convoID]['agent_name'] = agentName
    novaConvo[convoID]['token_limit'] = 4000
    sessionID = novaConvo[convoID]['sessionID'] 
    novaSession[sessionID]['latestConvo']= convoID

async def initialiseCartridges(convoID):
    
    eZprint('intialising cartridges')
    if convoID not in current_loadout:
        current_loadout[convoID] = None
    novaConvo[convoID]['owner'] = True
    await loadCartridges(convoID)
    await runCartridges(convoID)


async def loadCartridges(convoID, loadout = None):
    eZprint('load cartridges called')
    userID = novaConvo[convoID]['userID']
    cartridges = await prisma.cartridge.find_many(
        where = {  
        "UserID": userID,
        }
    )
    if len(cartridges) != 0:
        available_cartridges[convoID] = {}
        for cartridge in cartridges:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal or cartVal['softDelete'] == False:
                    available_cartridges[convoID][cartKey] = cartVal
                    cartdigeLookup.update({cartKey: cartridge.id}) 
                    # cartVal['key'] = cartKey
                    if cartVal['type'] == 'summary':
                        cartVal.update({'state': 'loading'})
                        # cartVal['blocks'] = []

        # print('available cartridges are ' + str(available_cartridges[convoID]))
        # print('loadout is ' + str(loadout))
        # print('current loadout is ' + str(current_loadout[convoID]))
        if loadout == current_loadout[convoID]:
            await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': available_cartridges[convoID]}))
    eZprint('load cartridges complete')

async def runCartridges(convoID, loadout = None):
    # await construct_query(convoID)
    print('running cartridges')
    print(current_config[convoID])
    if convoID in current_config:
        if 'agent_initiated' in current_config[convoID] and current_config[convoID]['agent_initiated'] == True:
            await agent_initiate_convo(convoID)
    # if 'agent_initiated' in novaConvo[convoID] and novaConvo[convoID]['agent_initiated'] == True:
    #     await agent_initiate_convo(convoID)
    if loadout != current_loadout[convoID]:
        return
    if convoID in available_cartridges:
        for cartKey, cartVal in available_cartridges[convoID].items():
            if cartVal['type'] == 'summary':
                if 'enabled' in cartVal and cartVal['enabled'] == True:
                    print('running summary cartridge on loadout ' + str(loadout))
                    asyncio.create_task(run_summary_cartridges(convoID, cartKey, cartVal, loadout))
    else:
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
        await  websocket.send(json.dumps({'event':'sendCartridges', 'cartridges':available_cartridges[convoID]}))
        await runCartridges(convoID)


async def addNewUserCartridgeTrigger(convoID, cartKey, cartVal):
    #special edge case for when new user, probablyt remove this
    #TODO: replace this with better new user flow
    if convoID not in available_cartridges:
        available_cartridges[convoID] = {}
    available_cartridges[convoID][cartKey]= cartVal  
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

