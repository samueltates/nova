import json
import asyncio
# from nova import getPromptEstimate, getChatEstimate
from appHandler import app, websocket
from prismaHandler import prisma
from prisma import Json
from sessionHandler import novaConvo, availableCartridges, chatlog, cartdigeLookup
from debug import eZprint
from human_id import generate_id
from loadout import current_loadout, add_cartridge_to_loadout, update_settings_in_loadout

whole_cartridge_list = {}

async def get_cartridge_list(convoID):
    userID = novaConvo[convoID]['userID']
    print('get cartridge list triggered')
    cartridges = await prisma.cartridge.find_many(
        where={ "UserID": userID },
    )
    cartridge_list = []
    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']
        for key, val in blob.items():
            if 'key' not in availableCartridges[convoID]:
                val.update({'key':key})
                cartridge_list.append(val)
    await websocket.send(json.dumps({'event': 'cartridge_list', 'payload': cartridge_list}))


async def addCartridge(cartVal, convoID):
    eZprint('add cartridge triggered')
    userID = novaConvo[convoID]['userID']
    cartKey = generate_id()
    if 'blocks' not in cartVal:
        cartVal.update({"blocks":[]})
    if 'enabled' not in cartVal:
        cartVal.update({"enabled":True})
    if 'softDelete' not in cartVal:
        cartVal.update({"softDelete":False})
    if convoID in current_loadout:
        cartVal.update({'loadout':current_loadout[convoID] })
    if 'key' not in cartVal:
        cartVal.update({'key':cartKey})
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    eZprint('new cartridge added to [nova]')
    print(newCart)

    if convoID not in availableCartridges:
        availableCartridges[convoID]  = {}
    availableCartridges[convoID][cartKey] = cartVal

    payload = {
            'cartKey': cartKey,
            'cartVal': cartVal,
        }

    await  websocket.send(json.dumps({'event':'add_cartridge', 'payload':payload}))
    return True


async def addCartridgePrompt(input):
    eZprint('add cartridge prompt triggered')
    cartKey = generate_id()
    convoID = input['convoID']
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    cartVal.update({'key': cartKey})
    userID = novaConvo[convoID]['userID']
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    
    if convoID not in availableCartridges:
        availableCartridges[convoID]  = {}
    availableCartridges[convoID][cartKey] = cartVal
    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    await add_cartridge_to_loadout(convoID, cartKey)

async def addExistingCartridgeToLoadout(input):
    print(input)
    convoID = input['convoID']
    cartKey = input['cartridge']
    await add_cartridge_to_loadout(convoID,cartKey)


async def addCartridgeTrigger(input):
    #TODO - very circular ' add index cartridge' triggered, goes to index, then back, then returns 
    #TODO - RENAME ADD CARTRIDGE INDEX
    cartKey = generate_id()
    convoID = input['convoID']
    userID = novaConvo[convoID]['userID']
    cartVal = input['cartVal']
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID': userID,
            'blob': Json({cartKey:{
                'label': cartVal['label'],
                'description': cartVal['description'],
                # 'blocks':cartVal['blocks'],
                'type': cartVal ['type'],   
                'enabled': True,
                'index':cartVal['index'],
                'indexType': cartVal['indexType'],

            }})
        }
    )
    eZprint('new index cartridge added to [nova]')
    cartdigeLookup.update({cartKey: newCart.id}) 
    if convoID not in availableCartridges:
        availableCartridges[convoID] = {}
    availableCartridges[convoID][cartKey] = cartVal
    await add_cartridge_to_loadout(convoID,cartKey)

    return newCart

async def updateCartridgeField(input):
    targetCartKey = input['cartKey']
    convoID = input['convoID']
    targetCartVal = availableCartridges[convoID][targetCartKey]
    await update_settings_in_loadout(convoID, targetCartKey, input['fields'])
    # print(targetCartKey)
    # print(sessionData)
    # TODO: switch to do lookup via key not blob
    # eZprint('cartridge update input')
    # print(input)
    matchedCart = await prisma.cartridge.find_first(
        where={
        'key':
        {'equals': input['cartKey']}
        },         
    )
    # print(matchedCart)
    for key, val in input['fields'].items():
        availableCartridges[convoID][targetCartKey][key] = val
        
    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({targetCartKey:targetCartVal})
            }
        )
        # print(updatedCart)
        # eZprint('updated cartridge')
        # print(updatedCart)
    payload = { 'key':targetCartKey,'fields': {'state': ''}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': 'nova', 'state': ''}}))

async def updateContentField(input):
    convoID = input['convoID']
    print('update chatlog field')
    for log in chatlog[convoID]:
        if log['ID'] == input['ID']:
            for key, val in input['fields'].items():
                log[key] = val
    # await getChatEstimate(convoID)