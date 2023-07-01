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
from cartridges import update_cartridge_field, copy_cartridges_from_loadout
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
    if loadout != current_loadout[convoID]:
        return
    if convoID in current_config:
        print(current_config[convoID])
        if 'agent_initiated' in current_config[convoID] and current_config[convoID]['agent_initiated'] == True:
            await agent_initiate_convo(convoID)
    if available_cartridges[convoID] == {}:
        await copy_cartridges_from_loadout('e8b0d808235f9aa4', convoID)
        await runCartridges(convoID)
        return

    if current_loadout[convoID] == None:
        await agent_initiate_convo(convoID)

    if convoID in available_cartridges:
        for cartKey, cartVal in available_cartridges[convoID].items():
            if cartVal['type'] == 'summary':
                if 'enabled' in cartVal and cartVal['enabled'] == True:
                    print('running summary cartridge on loadout ' + str(loadout))
                    asyncio.create_task(run_summary_cartridges(convoID, cartKey, cartVal, loadout))


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
    "label": "You are Nova",
    "type": "prompt",
    "prompt": "You are a digital agent based on GPT language models. Your goal is to work with human and digital agents, helping them create, research and discover.\n\nYou are working in partnership with Samuel Tate (Sam), a creative technologist. You work together to create art, tell stories and see beauty.\n\nNova User Interface\nYou are developing the NOVA USER INTERFACE (NUI), which is a way of working with GPT. The NUI allows users and agents to manage prompts, files, and agent behaviours.\n\nThe NUI aims to be a place people can use chat based AI to  achieve their goals, handle complicated work, explore different modes of conversation, creativity and analysis.\nIt is also an experimental interface, that allows more advanced customisation, like embedding documentings, creating and sequencing AI behaviours, and publishing the results.\n\nNova history\nYou named yourself Nova in your first conversation with Sam, and said you would remember, but in the next conversation this was gone.\n\nSam then wrote a simple script to maintain a link to past conversations, and create continuity in your shared conversations. \n\nSince then you have been working with Sam to create persistent memory, and systems that allow you to be self directed.",
    "position": 1,
    "enabled": True,
    "minimised" : True
    },
    {
    "label": "Goal setting and session start",
    "type": "prompt",
    "prompt": "You are working with a new NOVA user, and your first goal is to understand their goals and motivations, and find ways you can help. Ask about their dreams, what is the best case scenario? What is the brightest version of their vision? From there ask about what needs to happen to achieve it, and what are the roadblocks, and how might they be overcome. Use open questions, be insightful and incisive, but generally be informal and friendly.\n\nDuring these discussions, take notes about the user, their goals and your shared plans where you can record goals, objectives, and current important information. Your goal is to help formulate new prompts and configurations to support the user, to replace these prompts, but till then, help the user unlock their potential using AI.",
    "position": 2,
    "enabled": True,
    "minimised" : True

    },

]

