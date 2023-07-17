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
from Levenshtein import distance
from datetime import datetime


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
            if 'supersoftdelete' in val and 'supersoftdelete' == True:
                continue
            whole_cartridge_list[convoID][key] = val
            val.update({'key':key})
            cartridge_list.append(val)
    await websocket.send(json.dumps({'event': 'cartridge_list', 'payload': cartridge_list}))


async def addCartridge(cartVal, convoID, client_loadout = None):
    eZprint('add cartridge triggered')
    userID = novaConvo[convoID]['userID']
    cartKey = generate_id()
    if 'key' not in cartVal:
        cartVal.update({'key':cartKey})

    if current_loadout[convoID] != None:
        if client_loadout == current_loadout[convoID]:
            await add_cartridge_to_loadout(convoID, cartKey, client_loadout)
            cartVal["softDelete"] = True

    cartVal['dateAdded'] = str(datetime.now())
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    
    eZprint('new cartridge added to [nova]')
    # print(newCart)


    if current_loadout[convoID] != None:
        if client_loadout == current_loadout[convoID]:
            ##another stupid hack, this time to set it to avail as it isn't running the loadout change so setting it false for first load (or resetting)
            print('setting to not soft delete for current session')
            cartVal["softDelete"] = False
    
    if convoID not in available_cartridges:
        available_cartridges[convoID]  = {}

    available_cartridges[convoID][cartKey] = cartVal

    payload = {
            'cartKey': cartKey,
            'cartVal': cartVal,
        }
    
    # print('sending add cartridge event' + str(payload) + ' supplied loadout ' + str(client_loadout) +  ' curent loadout :  ' + str(current_loadout[convoID]))
    if client_loadout == current_loadout[convoID]:
        print('sending to websocket')
        await  websocket.send(json.dumps({'event':'add_cartridge', 'payload':payload}))

    return True


async def addCartridgePrompt(input, client_loadout = None):

    eZprint('add cartridge prompt triggered')
    cartKey = generate_id()
    convoID = input['convoID']
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    cartVal.update({'key': cartKey})
    userID = novaConvo[convoID]['userID']
    cartVal['dateAdded'] = str(datetime.now())

    if current_loadout[convoID] != None:
        if client_loadout == current_loadout[convoID]:
            print('adding to loadout so setting as deleted on main')
            await add_cartridge_to_loadout(convoID, cartKey, client_loadout)
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
        if client_loadout == current_loadout[convoID]:
            ##another stupid hack, this time to set it to avail as it isn't running the loadout change 
            print('in loadout at the moment so setting back to enabled as loadout mutate hasnt occured')
            cartVal["softDelete"] = False

    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
        
    if current_loadout[convoID] == client_loadout:
        await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    return newCart

async def add_existing_cartridge(input, loadout = None ):

    eZprint('add existing cartridge triggered')
    print(input)
    print(loadout)
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
    
    # print('cartVal' , cartVal) 
    # 
    # print('updated avail')   
    # print(available_cartridges[convoID])

    ##if still on the right loadout then sends new cartridge.
    # if current_loadout[convoID] == loadout:
    await  websocket.send(json.dumps({'event':'add_cartridge', 'payload':payload}))


async def addCartridgeTrigger(input, client_loadout = None):
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
                'type': cartVal ['type'],   
                'enabled': True,
                'index':cartVal['index'],
            }})
        }
    )

    if convoID not in available_cartridges:
        available_cartridges[convoID] = {}
    available_cartridges[convoID][cartKey] = cartVal

    if client_loadout:
        await add_cartridge_to_loadout(convoID,cartKey, client_loadout)
    if current_loadout[convoID] == client_loadout:
        payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
        await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

    return newCart

async def update_cartridge_field(input, client_loadout= None, system = False):
    targetCartKey = input['cartKey']
    convoID = input['convoID']
    # print('update cartridge field ' + available_cartridges[convoID][targetCartKey]['label'])
    # print(input['fields'])
    
    if client_loadout != current_loadout[convoID]:
        return False
    matchedCart = await prisma.cartridge.find_first(
        where={
        'key':
        {'equals': input['cartKey']}
        },         
    )

    # print(available_cartridges[convoID])
    for key, val in input['fields'].items():
        available_cartridges[convoID][targetCartKey][key] = val

    if matchedCart:
        # print('matched cart ' + str(matchedCart.id))
        matchedCartVal = json.loads(matchedCart.json())['blob'][targetCartKey]
        # print ('checking loadout ' + str(loadout))
        if client_loadout == current_loadout[convoID]:
            # print('loadout match')
            if client_loadout:
                #if coming from loadout then it doesn't update the base settings, they get applied at loadout level
                # print('update settings in loadout')
                await update_settings_in_loadout(convoID, targetCartKey, input['fields'], client_loadout)
                for key, val in input['fields'].items():
                        if key == 'enabled':
                            continue
                        if key == 'minimised':
                            continue
                        if key == 'softDelete':
                            continue
                        matchedCartVal[key] = val
                
            elif client_loadout == None: 
                #if not coming from loadout then applies to base
                # print('update base cartridge')

                for key, val in input['fields'].items():
                    matchedCartVal[key] = val

            matchedCartVal['lastUpdated'] = str(datetime.now())

            updatedCart = await prisma.cartridge.update(
                where={ 'id': matchedCart.id },
                data={
                    'blob' : Json({targetCartKey:matchedCartVal})
                }
            )
            # print('updated cart' + str(updatedCart.id))
            if system:
                # print('system update')
                payload = { 'key':targetCartKey,
                           'fields': input['fields'], 
                           'loadout': client_loadout,
                                }

                await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))



async def updateContentField(input):
    convoID = input['convoID']
    # print('update chatlog field')
    for log in chatlog[convoID]:
        if log['key'] == input['key']:
            for fieldKey, fieldVal in input['fields'].items():
                log[fieldKey] = fieldVal
    # await getChatEstimate(convoID)

async def handle_super_soft_delete(input):
    convoID = input['convoID']
    cartKey = input['cartKey']
    remoteCart = await prisma.cartridge.find_first(
        where={
            "key": cartKey
            },
    )
    if remoteCart:

        blob = json.loads(remoteCart.json())['blob']
        blob['supersoftdelete'] = True
        updatedCart = await prisma.cartridge.update(
            where={ 'id': remoteCart.id },
            data={
                'blob' : Json(blob)
            }
        )
        


async def copy_cartridges_from_loadout(loadout: str, convoID):
    remote_loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout) },
    )
    print('copy cartridges from loadout ' + str(loadout))
    print('remote loadout ' + str(remote_loadout))

    cartridge_copies = []
    if convoID not in available_cartridges:
        available_cartridges[convoID] = {}
        
    if remote_loadout:
        blob = json.loads(remote_loadout.json())['blob']
        for key, val in blob.items():
            for cartridge in val['cartridges']:
                print('copy cartridge ' + str(cartridge))
                cartridge_copies.append(cartridge)
    
    for cartridge in cartridge_copies:
        remote_cartridge = await prisma.cartridge.find_first(
            where={ "key": cartridge['key'] },
        )

        if remote_cartridge:
            print('copy cartridge ' + str(remote_cartridge.key))
            cartBlob = json.loads(remote_cartridge.json())['blob']
            for key, val in cartBlob.items():
                print('copy cartridge ' + str(key))
                val['enabled'] = True
                val['softDelete'] = False
                val['minimised'] = False
                await addCartridge(val, convoID, current_loadout[convoID])

async def search_cartridges(search_query, convoID):
    matching_objects = []
    for key, val in whole_cartridge_list[convoID].items():
            # print(val)
            for field, value in val.items():
                print(value)
                # if len(value) <0:
                if len(str(value)) and search_query in str(value):
                    matching_objects.append(val)
                    break

    print (matching_objects)
    if len(matching_objects) > 0:
        await websocket.send(json.dumps({'event': 'filtered_cartridge_list', 'payload': matching_objects}))
    # else:
        # await websocket.send(json.dumps({'event': 'filtered_cartridge_list', 'payload': whole_cartridge_list[convoID]}))

    
   