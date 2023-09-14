import json
import asyncio
from prisma import Json
from human_id import generate_id
from Levenshtein import distance
from datetime import datetime

# from nova import getPromptEstimate, getChatEstimate
from session.appHandler import app, websocket
from session.prismaHandler import prisma
from session.sessionHandler import novaConvo, active_loadouts, active_cartridges, chatlog, cartdigeLookup, novaSession
from core.loadout import current_loadout, add_cartridge_to_loadout, update_settings_in_loadout
from tools.debug import eZprint


whole_cartridge_list = {}

async def retrieve_loadout_cartridges(loadout_key, convoID):
    print('retrieving loadout cartridges')
    print(convoID)
    # gets cartridges associated with that loadout
    # TODO : switch to cartridges, calling active loadouts, uses loadout key
    # same logic or question, is the cartridge session wide... on the content side, basically?
    # so its active_cartridges[cartridgeID] -  info goes to their, 'session carts, loadouts' is just key
    # also allows for debounce across multiple users? - leave that for now
    
    # print('loadout Key', loadout_key, 'convoID', convoID)

    loadout_cartridges = []
    if convoID not in active_cartridges:
        active_cartridges[convoID] = {}

    # print(active_loadouts)
    #could possible clean slate check here and branch not sure
    loadout_data = active_loadouts.get(loadout_key, None)

    # print(loadout_data)
    if not loadout_data:
        return
    
    config = loadout_data.get('config', {})
    convos = loadout_data.get('convos', {})
    
    convo_cartridges = None
    loadout_cartridges = None
    cleanSlate = config.get('cleanSlate', None)

    # print('config', config)
    # print('convos', convos)
    # if clean slate, then gets the convo cartridges and then loadout cartridges

    if cleanSlate :
        if convoID in convos:
            convo_cartridges = convos[convoID].get('cartridges', None)
        loadout_cartridges = loadout_data.get('cartridges', None) 

    else :

        loadout_cartridges = loadout_data.get('cartridges', None)

    # print(convo_cartridges, 'convo carts')
    # print(loadout_cartridges, 'loadout cartridges')

    #recalls cartridges in loadout
    if not loadout_cartridges and not convo_cartridges:
        return
    
    cartridges_to_add = []

    ## new idea, checks for loadout carts, differntiated on pin setting if cleanslate, then checks convo carts if they're popped, then adds through that.
    for loadout_cartridge in loadout_cartridges:

        # has to find a lot of cartridges maybe unesarily
        # to do, clean slate check here eg
        # if cleanSlate and pinned then ... - pinned needs to get saved on a loadout level - sort of happens in settings anyways!
        # print(loadout_cartridge)
        settings = loadout_cartridge.get('settings', False)
        if settings:
            pinned = settings.get('pinned', False)
        cartKey = loadout_cartridge.get('key', None)

        # checks if its not clean slate its added, or if it is cleanslate, but its pinned its added, and always needs cartKey
        if (not cleanSlate or pinned) and cartKey:        
            remote_cartridge = await prisma.cartridge.find_first(
                where={ "key": cartKey },
            )

            if not remote_cartridge:
                continue
            cartridges_to_add.append(remote_cartridge)

    if convo_cartridges:
            for convo_cartridge in convo_cartridges:
                cartKey = convo_cartridge.get('key', None)
                remote_cartridge = await prisma.cartridge.find_first(
                    where={ "key": cartKey },
                )
            cartridges_to_add.append(remote_cartridge)

    for cartridge_to_add in cartridges_to_add:
        blob = json.loads(cartridge_to_add.json())
        for cartKey, cartVal in blob['blob'].items():
            # this check won't need to happen if done at loadout settings level
            
            cartVal['softDelete'] = False
            active_cartridges[convoID][cartKey ]= cartVal
            # print('reading cart', cartVal)

            if 'settings' in loadout_cartridge:
                if 'enabled' in loadout_cartridge['settings']:
                    cartVal['enabled'] = loadout_cartridge['settings']['enabled'] 
                else:
                    cartVal['enabled'] = True

                if 'minimised' in loadout_cartridge['settings']:
                    cartVal['minimised'] = loadout_cartridge['settings']['minimised']
                else:
                    cartVal['minimised'] = False
                    
                if 'pinned' in loadout_cartridge['settings']:
                    cartVal['pinned']= loadout_cartridge['settings']['pinned']
                else:
                    cartVal['pinned'] = False

                if 'position' in loadout_cartridge['settings']:
                    cartVal['position'] = loadout_cartridge['settings']['position']

    # print('cartridge list')
    # print(active_cartridges[convoID])
    await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': active_cartridges[convoID]}))

async def get_cartridge_list(sessionID):
    userID = novaSession[sessionID]['userID']
    print('get cartridge list triggered')
    cartridges = await prisma.cartridge.find_many(
        where={ "UserID": userID },
    )
    cartridge_list = []
    if sessionID not in whole_cartridge_list:
        whole_cartridge_list[sessionID] = {}

    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']
        for key, val in blob.items():
            if 'supersoftdelete' in val and 'supersoftdelete' == True:
                continue
            whole_cartridge_list[sessionID][key] = val
            val.update({'key':key})
            cartridge_list.append(val)
    await websocket.send(json.dumps({'event': 'cartridge_list', 'payload': cartridge_list}))


async def addCartridge(cartVal, sessionID, client_loadout = None, convoID = None, system = False):
    eZprint('add cartridge triggered')
    userID = novaSession[sessionID]['userID']
    cartKey = generate_id()

    if 'key' not in cartVal:
        cartVal.update({'key':cartKey})
    if client_loadout:
        await add_cartridge_to_loadout(convoID, cartKey, client_loadout)
        cartVal["softDelete"] = True
    if 'position' not in cartVal:
        cartVal['position'] = 99
    
    cartVal['initial-loadout'] = client_loadout
    cartVal['dateAdded'] = str(datetime.now())

    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal}),
        }
    )
    
    eZprint('new cartridge added to [nova]')
    # print(newCart)


    if client_loadout:
        cartVal["softDelete"] = False
    
    if convoID not in active_cartridges:
        active_cartridges[convoID]  = {}

    active_cartridges[convoID][cartKey] = cartVal

    payload = {
            'client_loadout': convoID,
            'cartKey': cartKey,
            'cartVal': cartVal,
        }
    
    # print('sending add cartridge event' + str(payload) + ' supplied loadout ' + str(client_loadout) +  ' curent loadout :  ' + str(current_loadout[convoID]))
    # if system:
    await  websocket.send(json.dumps({'event':'add_cartridge', 'payload':payload}))

    return cartKey


async def addCartridgePrompt(input, convoID, client_loadout = None):

    eZprint('add cartridge prompt triggered')
    cartKey = generate_id()
    sessionID = input['sessionID']
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    cartVal.update({'key': cartKey})
    userID = novaSession[sessionID]['userID']
    cartVal['dateAdded'] = str(datetime.now())
    cartVal['initial-loadout'] = client_loadout

    if client_loadout:
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
    
    if convoID not in active_cartridges:
        active_cartridges[convoID]  = {}

    active_cartridges[convoID][cartKey] = cartVal
    
    if current_loadout[sessionID] != None:
        if client_loadout == current_loadout[sessionID]:
            ##another stupid hack, this time to set it to avail as it isn't running the loadout change 
            print('in loadout at the moment so setting back to enabled as loadout mutate hasnt occured')
            cartVal["softDelete"] = False

    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
        
    if current_loadout[sessionID] == client_loadout:
        await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    return newCart

async def add_existing_cartridge(input, loadout = None ):

    eZprint('add existing cartridge triggered')
    print(input)
    print(loadout)
    sessionID = input['sessionID']
    convoID = input['convoID']
    cartKey = input['cartridge']


    
    cartridge = await prisma.cartridge.find_first(
        where={
            "key": cartKey
            },
    )

    cartVal = json.loads(cartridge.json())['blob'][cartKey]
    active_cartridges[convoID][cartKey] = cartVal

    #as no lodout sets base layer settings
    if loadout == None:
        input = {
            'sessionID': sessionID,
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
    sessionID = input['sessionID']

    userID = novaSession[sessionID]['userID']
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

    if sessionID not in active_cartridges:
        active_cartridges[sessionID] = {}
    active_cartridges[sessionID][cartKey] = cartVal

    if client_loadout:
        await add_cartridge_to_loadout(sessionID,cartKey, client_loadout)
    if current_loadout[sessionID] == client_loadout:
        payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
        await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

    return newCart

async def update_cartridge_field(input, convoID, client_loadout= None, system = False):
    targetCartKey = input['cartKey']
    sessionID = input['sessionID']
    # print('update cartridge field ' + str(available_cartridges[sessionID][targetCartKey]))
    print(input['fields'])
    
    # if client_loadout != current_loadout[sessionID]:
    #     return False
    matchedCart = await prisma.cartridge.find_first(
        where={
        'key':
        {'equals': input['cartKey']}
        },         
    )

    # print(active_cartridges[convoID])
    if targetCartKey in active_cartridges[convoID]:
        for key, val in input['fields'].items():
            active_cartridges[convoID][targetCartKey][key] = val

    if matchedCart:
        # print('matched cart ' + str(matchedCart.id))
        matchedCartVal = json.loads(matchedCart.json())['blob'][targetCartKey]
        # print ('checking loadout ' + str(loadout))
            # print('loadout match')
        if client_loadout:
            #if coming from loadout then it doesn't update the base settings, they get applied at loadout level
            # print('update settings in loadout')
            setting_update = False
            for key, val in input['fields'].items():
                    if key in ['enabled', 'minimised', 'pinned', 'position']:
                        setting_update = True
                        continue
                    if key == 'softDelete' and val == True:
                        # print('soft delete')
                        setting_update = True

                        del active_cartridges[convoID][targetCartKey]
                        continue
                    matchedCartVal[key] = val
            if setting_update:
                await update_settings_in_loadout(convoID, targetCartKey, input['fields'], client_loadout)

        elif client_loadout == None: 
            #if not coming from loadout then applies to base
            # print('update base cartridge')

            for key, val in input['fields'].items():
                matchedCartVal[key] = val
                if key == 'softDelete' and val == True:
                    # print('soft delete')
                    del active_cartridges[convoID][targetCartKey]

                
        # print(available_cartridges[convoID])

        matchedCartVal['lastUpdated'] = str(datetime.now())

        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({targetCartKey:matchedCartVal})
            }
        )
        # print('updated cart' + str(updatedCart.id))
        if system:
            print('system update')
            payload = { 'key':targetCartKey,
                        'fields': input['fields'], 
                        'convoID': convoID,
                            }
            if client_loadout == current_loadout[sessionID]:
                await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))



async def updateContentField(input):
    convoID = input['convoID']
    # print('update chatlog field')
    for log in chatlog[convoID]:
        if 'id' in log and log['id'] == input['id']:
            for fieldKey, fieldVal in input['fields'].items():
                log[fieldKey] = fieldVal
    # await getChatEstimate(convoID)

async def handle_super_soft_delete(input):
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
        


async def copy_cartridges_from_loadout(loadout: str, sessionID):
    remote_loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout) },
    )
    print('copy cartridges from loadout ' + str(loadout))
    print('remote loadout ' + str(remote_loadout))

    cartridge_copies = []
    if sessionID not in active_cartridges:
        active_cartridges[sessionID] = {}
        
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
                await addCartridge(val, sessionID, current_loadout[sessionID])


# async def search_cartridges(search_query, sessionID):
#     matching_objects = []
#     #sort by last updated
#     if sessionID not in whole_cartridge_list:
#         whole_cartridge_list[sessionID] = {}
#         await get_cartridge_list(sessionID)
    
#     default_value = '1970-01-01 00:00:00.000000'
#     sorted_cartridge_list = sorted(whole_cartridge_list[sessionID].items(), key=lambda x: x[1].get('lastUpdated', default_value), reverse=True)
#     # sorted_cartridge_list = sorted(whole_cartridge_list[sessionID].items(), key=lambda x: x[1]['lastUpdated'], reverse=True)
#     for key, val in sorted_cartridge_list:
#             # print(val)
#             for field, value in val.items():
#                 # print(value)
#                 # if len(value) <0:
#                 if len(str(value)) and search_query in str(value):
#                     matching_objects.append(val)
#                     break

#     # print (matching_objects)
#     # if len(matching_objects) > 0:
#     await websocket.send(json.dumps({'event': 'filtered_cartridge_list', 'payload': matching_objects}))
#     return matching_objects
#     # else:
#         # await websocket.send(json.dumps({'event': 'filtered_cartridge_list', 'payload': whole_cartridge_list[convoID]}))

    
   
async def search_cartridges(search_query, sessionID):
    matching_objects = []
    #sort by last updated
    print('search cartridges')
    if sessionID not in whole_cartridge_list:
        whole_cartridge_list[sessionID] = {}
        await get_cartridge_list(sessionID)

    default_value = '1970-01-01 00:00:00.000000'
    sorted_cartridge_list = sorted(whole_cartridge_list[sessionID].items(), key=lambda x: x[1].get('lastUpdated', default_value), reverse=True)
    search_query = search_query.lower()
    for key, val in sorted_cartridge_list:
        for field, value in val.items():
            value = str(value).lower()
            if len(str(value)) and search_query in str(value):
                match_index = str(value).index(search_query)
                # print(match_index)
                start = max(0, match_index - 100) # slice bounds handling
                # print(start)
                end = min(len(str(value)), match_index + 100)
                # print(end)
                snippet = str(value)[start:end]
                # print(snippet)
                val['snippet'] = snippet
                # print(val)
                matching_objects.append(val)
                break
    # print(matching_objects)
    await websocket.send(json.dumps({'event': 'filtered_cartridge_list', 'payload': matching_objects}))
    return matching_objects