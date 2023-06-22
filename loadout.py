from prismaHandler import prisma
from prisma import Json
import json
from appHandler import app, websocket
from sessionHandler import availableCartridges, novaConvo, current_loadout, available_loadouts
from human_id import generate_id
from debug import eZprint

async def get_loadouts(convoID):
    userID = novaConvo[convoID]['userID']

    loadouts = await prisma.loadout.find_many(
        where={ "UserID": userID },
    )


    # del current_loadout[convoID]
    available_loadouts[convoID] = {}
    for loadout in loadouts:
        # print(loadout)
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            available_loadouts[convoID][key] = val
    
    await websocket.send(json.dumps({'event': 'populate_loadouts', 'payload': available_loadouts[convoID]}))

async def add_loadout(loadout: str, convoID):
    current_loadout[convoID] = loadout
    availableCartridges[convoID] = {}

    new_loadout = await prisma.loadout.create(
        data={
            "key": str(loadout),
            'UserID': novaConvo[convoID]['userID'],
            "blob":Json({loadout:{
                'cartridges':[],
                'config': { 
                        'title': '...',
                        'read_only': False,
                        'convo_summary': 'one_way',
                        'show_cartridges' : True,
                        'shared' : False,
                        }
            }})
        }
    )
    if loadout == current_loadout[convoID]:
        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))
  

async def add_cartridge_to_loadout(convoID, cartridge, loadout = None):
    eZprint('add cartridge to loadout triggered')
    print(current_loadout)

    remote_loadout = await prisma.loadout.find_first(
        where={ "key": current_loadout[convoID] },
    )
    print('loadout found')
    print(remote_loadout)
    if remote_loadout:
        blob = json.loads(remote_loadout.json())['blob']
        for key, val in blob.items():
            val['cartridges'].append({
                'key':cartridge, 
                'settings':{
                    'enabled':True,
                    'softDelete':False,
                    'minimised':True,
            }})

        update = await prisma.loadout.update(
            where = {
                'id' : remote_loadout.id
            },
            data={
                "blob":Json(blob)
                }
        )
        print('loadout updated')
        print(update)
        

async def update_settings_in_loadout(convoID, cartridge, settings, loadout):
    eZprint('update settings in loadout triggered')
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout) },
    )
    if loadout:
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            if 'cartridges' in val:
                for cart in val['cartridges']:
                    if 'key' in cart and cart['key'] == cartridge:
                        if 'softDelete' in settings and settings['softDelete'] == True:
                            val['cartridges'].remove(cart)
                        if 'settings' not in cart:
                            cart['settings'] = {}                
                        for key, val in settings.items():
                            if key == 'enabled':
                                cart['settings'][key] = val
                            if key == 'minimised':
                                cart['settings'][key] = val
                            if key == 'softDelete':
                                cart['settings'][key] = val
                                         
        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json(blob)
                }
        )

        # print(update)

async def set_loadout(loadout_key: str, convoID, referal = False):

    eZprint('set_loadout')
    # print(loadout_key)
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key)}
    )

    current_loadout[convoID] = loadout_key
    # print(loadout)
    loadout_cartridges = []
    config = {}
    blob = json.loads(loadout.json())['blob']
    owner = not referal

    novaConvo[convoID]['owner'] = owner

    for key, val in blob.items():
        config = val['config']
        await websocket.send(json.dumps({'event': 'set_config', 'payload':{'config': config, 'owner': owner}}))
        loadout_cartridges = val['cartridges']

    cartridges_to_add = []
    availableCartridges[convoID] = {}

    for loadout_cartridge in loadout_cartridges:
        print(loadout_cartridge)
        print(loadout_cartridge['key'])
        cartKey = loadout_cartridge
        if 'key' in loadout_cartridge:
            cartKey = loadout_cartridge['key']
        remote_cartridge = await prisma.cartridge.find_first(
            where={ "key": cartKey },
        )

        if not remote_cartridge:
            continue
        # print(remote_cartridge)
        cartridges_to_add.append(remote_cartridge)
        blob = json.loads(remote_cartridge.json())
        for cartKey, cartVal in blob['blob'].items():
                availableCartridges[convoID][cartKey] = cartVal
                cartVal['softDelete'] = False
                if 'settings' in loadout_cartridge:
                    print(loadout_cartridge['settings'])
                    if 'enabled' in loadout_cartridge['settings']:
                        cartVal['enabled'] = loadout_cartridge['settings']['enabled'] 
                    else:
                        cartVal['enabled'] = True
                    if 'minimised' in loadout_cartridge['settings']:
                        cartVal['minimised'] = loadout_cartridge['settings']['minimised']
                    else:
                        cartVal['minimised'] = False
                    
    if loadout_key == current_loadout[convoID]:
        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))

async def clear_loadout(convoID):
    current_loadout[convoID] = None
    
        
async def delete_loadout(loadout_key: str, convoID):
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    print(loadout)
    await prisma.loadout.delete(
        where={
            'id': loadout.id
        }
    )

    if convoID in current_loadout:
        current_loadout[convoID] = None

    await get_loadouts(convoID)

async def set_read_only(loadout_key, read_only):
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    blob = json.loads(loadout.json())['blob']
    for key, val in blob.items():
        val['config']['read_only'] = read_only
        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json({key:val})
                }
        )

async def set_loadout_title(loadout_key, title):

    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    blob = json.loads(loadout.json())['blob']
    for key, val in blob.items():
        val['config']['title'] = title
        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json({key:val})
                }
        )

async def update_loadout_field(loadout_key, field, value):
    print(loadout_key, field, value)
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    blob = json.loads(loadout.json())['blob']
    for key, val in blob.items():
        print(key, val)
        val['config'][field] = value

        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json({key:val})
                }
        )
        print(update)
