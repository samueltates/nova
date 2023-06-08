import json
from nova import getPromptEstimate, getChatEstimate
from appHandler import app, websocket
from prismaHandler import prisma
from prisma import Json
from sessionHandler import novaConvo, availableCartridges, chatlog, cartdigeLookup
from debug import eZprint
from human_id import generate_id
from loadout import current_loadout, add_cartridge_to_loadout


async def addCartridgePrompt(input):
    eZprint('add cartridge prompt triggered')
    cartKey = generate_id()
    convoID = input['convoID']
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
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
    await add_cartridge_to_loadout(convoID, cartKey)
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

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
    print(targetCartKey)
    # print(sessionData)
    # TODO: switch to do lookup via key not blob
    eZprint('cartridge update input')
    # print(input)
    matchedCart = await prisma.cartridge.find_first(
        where={
        'blob':
        {'equals': Json({input['cartKey']: targetCartVal})}
        },         
    )

    print(matchedCart)
    for key, val in input['fields'].items():
        availableCartridges[convoID][targetCartKey][key] = val
        
    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({targetCartKey:targetCartVal})
            }
        )
        print(updatedCart)
        eZprint('updated cartridge')
        # print(updatedCart)
    payload = { 'key':targetCartKey,'fields': {'state': ''}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    await getPromptEstimate(convoID)

async def updateContentField(input):
    convoID = input['convoID']
    print('update chatlog field')
    for log in chatlog[convoID]:
        if log['ID'] == input['ID']:
            for key, val in input['fields'].items():
                log[key] = val
    await getChatEstimate(convoID)