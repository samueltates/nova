import json
import asyncio
# from nova import getPromptEstimate, getChatEstimate
from appHandler import app, websocket
from prismaHandler import prisma
from prisma import Json
from sessionHandler import novaConvo, available_cartridges, chatlog, cartdigeLookup
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
    if convoID not in whole_cartridge_list:
        whole_cartridge_list[convoID] = {}

    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']
        for key, val in blob.items():
            whole_cartridge_list[convoID][key] = val
            val.update({'key':key})
            cartridge_list.append(val)
    await websocket.send(json.dumps({'event': 'cartridge_list', 'payload': cartridge_list}))


async def addCartridge(cartVal, convoID, loadout = None):
    eZprint('add cartridge triggered')
    userID = novaConvo[convoID]['userID']
    cartKey = generate_id()
    if 'blocks' not in cartVal:
        cartVal.update({"blocks":{}})
    if 'enabled' not in cartVal:
        cartVal.update({"enabled":True})
    if 'softDelete' not in cartVal:
        cartVal.update({"softDelete":False})
    if convoID in current_loadout:
        cartVal.update({'loadout':current_loadout[convoID] })
    if 'key' not in cartVal:
        cartVal.update({'key':cartKey})

    if current_loadout[convoID] != None:
        if loadout == current_loadout[convoID]:
            await add_cartridge_to_loadout(convoID, cartKey)
            if 'softDelete' not in cartVal:
                cartVal["softDelete"] = True

    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    
    eZprint('new cartridge added to [nova]')
    # print(newCart)

    if convoID not in available_cartridges:
        available_cartridges[convoID]  = {}
    available_cartridges[convoID][cartKey] = cartVal

    if current_loadout[convoID] != None:
        if loadout == current_loadout[convoID]:
            ##another stupid hack, this time to set it to avail as it isn't running the loadout change so setting it false for first load (or resetting)
            if 'softDelete' not in cartVal:
                cartVal["softDelete"] = False

    payload = {
            'cartKey': cartKey,
            'cartVal': cartVal,
        }
    if current_loadout[convoID] == loadout:
        await  websocket.send(json.dumps({'event':'add_cartridge', 'payload':payload}))

    return True


async def addCartridgePrompt(input, loadout = None):

    eZprint('add cartridge prompt triggered')
    cartKey = generate_id()
    convoID = input['convoID']
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    cartVal.update({'key': cartKey})
    userID = novaConvo[convoID]['userID']

    if current_loadout[convoID] != None:
        if loadout == current_loadout[convoID]:
            print('adding to loadout so setting as deleted on main')
            await add_cartridge_to_loadout(convoID, cartKey)
            if 'softDelete' not in cartVal:
                cartVal["softDelete"] = True

    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    
    if convoID not in available_cartridges:
        available_cartridges[convoID]  = {}
    available_cartridges[convoID][cartKey] = cartVal
    
    if current_loadout[convoID] != None:
        if loadout == current_loadout[convoID]:
            ##another stupid hack, this time to set it to avail as it isn't running the loadout change 
            print('in loadout at the moment so setting back to enabled as loadout mutate hasnt occured')
            cartVal["softDelete"] = False

    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
        
    if current_loadout[convoID] == loadout:
        await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

async def add_existing_cartridge(input, loadout = None ):

    print(input)
    convoID = input['convoID']
    cartKey = input['cartridge']

    
    cartridge = await prisma.cartridge.find_first(
        where={
            "key": cartKey
            },
    )

    cartVal = json.loads(cartridge.json())['blob'][cartKey]
    available_cartridges[convoID][cartKey] = cartVal

    #as no lodout sets base layer settings
    if loadout == None:
        input = {
            'convoID': convoID,
            'cartKey': cartKey,
            'fields':{
            'softDelete': False,
            'enabled': True,
            },
            }
        await update_cartridge_field(input, loadout)

    if loadout:
        ## if loadout then sends to loadout, but sets base layer settings just for this session
        await add_cartridge_to_loadout(convoID,cartKey, loadout)

    cartVal["softDelete"] = False
    cartVal["enabled"] = True

    payload = {
            'cartKey': cartKey,
            'cartVal': cartVal,
        }
    
    print('cartVal' , cartVal)    
    ##if still on the right loadout then sends new cartridge.
    # if current_loadout[convoID] == loadout:
    await  websocket.send(json.dumps({'event':'add_cartridge', 'payload':payload}))



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
            }})
        }
    )
    eZprint('new index cartridge added to [nova]')
    cartdigeLookup.update({cartKey: newCart.id}) 
    if convoID not in available_cartridges:
        available_cartridges[convoID] = {}
    available_cartridges[convoID][cartKey] = cartVal
    await add_cartridge_to_loadout(convoID,cartKey)

    return newCart

async def update_cartridge_field(input, loadout = None, system = False):
    targetCartKey = input['cartKey']
    convoID = input['convoID']
    # print(input['fields'])
    # print('update cartridge field' + targetCartKey)
    matchedCart = await prisma.cartridge.find_first(
        where={
        'key':
        {'equals': input['cartKey']}
        },         
    )

    for key, val in input['fields'].items():
        available_cartridges[convoID][targetCartKey][key] = val

    if matchedCart:
        # print('matched cart' + str(matchedCart.id))
        matchedCartVal = json.loads(matchedCart.json())['blob'][targetCartKey]
        # print ('checking loadout ' + str(loadout))
        if loadout:
            #if coming from loadout then it doesn't update the base settings, they get applied at loadout level
            # print('update settings in loadout')
            await update_settings_in_loadout(convoID, targetCartKey, input['fields'], loadout)
            for key, val in input['fields'].items():
                    if key == 'enabled':
                        continue
                    if key == 'minimised':
                        continue
                    if key == 'softDelete':
                        continue
                    matchedCartVal[key] = val
            
        else: 
            #if not coming from loadout then applies to base
            print('update base cartridge')

            for key, val in input['fields'].items():
                matchedCartVal[key] = val

        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({targetCartKey:matchedCartVal})
            }
        )
        if system:
            payload = { 'key':targetCartKey,'fields': input['fields'], 
                            }

            await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))



async def updateContentField(input):
    convoID = input['convoID']
    # print('update chatlog field')
    for log in chatlog[convoID]:
        if log['ID'] == input['ID']:
            for key, val in input['fields'].items():
                log[key] = val
    # await getChatEstimate(convoID)