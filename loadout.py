from prismaHandler import prisma
from prisma import Json
import json
from appHandler import app, websocket
from sessionHandler import availableCartridges, novaConvo, current_loadout, available_loadouts
from human_id import generate_id


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
    loadout_cartridges = []
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
    await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))

async def add_cartridge_to_loadout(convoID, cartridge):
    if convoID not in current_loadout:
        return
    loadout = await prisma.loadout.find_first(
        where={ "key": str(current_loadout[convoID]) },
    )
    print(loadout)
    if loadout:
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            val['cartridges'].append(cartridge)

        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json(blob)
                }
        )

async def handle_referal(loadout_key: str, convoID):
    print(loadout_key)
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key)}
    )
    current_loadout[convoID] = loadout_key
    blob = json.loads(loadout.json())['blob']
    for key, val in blob.items():
        config = val['config']
        await websocket.send(json.dumps({'event': 'set_config', 'payload':{'config': config, 'owner': False}}))
        loadout_cartridges = val['cartridges']
    
    cartridges_to_add = []
       
    for cartridge in loadout_cartridges:
        remote_cartridges = await prisma.cartridge.find_first(
            where={ "key": cartridge },
        )
        # print(remote_cartridges)
        cartridges_to_add.append(remote_cartridges)
    
    if len(cartridges_to_add) != 0:
        availableCartridges[convoID] = {}
        for cartridge in cartridges_to_add:    
            if config.shared:
                blob = json.loads(cartridge.json())
                for cartKey, cartVal in blob['blob'].items():
                    if 'softDelete' not in cartVal or cartVal['softDelete'] == False:
                        print(cartVal)
                        availableCartridges[convoID][cartKey] = cartVal
            else:
                cartKey = generate_id()
                new_cartridge = await prisma.cartridge.create(
                    data={
                        "key": cartridge.key,
                        "UserID": novaConvo[convoID]['userID'],
                        "blob": cartridge.blob,
                    })

        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))


async def set_loadout(loadout_key: str, convoID, referal = False):

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
    
    for cartridge in loadout_cartridges:
        remote_cartridges = await prisma.cartridge.find_first(
            where={ "key": cartridge },
        )
        # print(remote_cartridges)
        cartridges_to_add.append(remote_cartridges)
    

    availableCartridges[convoID] = {}
    if len(cartridges_to_add) != 0:
        for cartridge in cartridges_to_add:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal or cartVal['softDelete'] == False:
                    # print(cartVal)
                    availableCartridges[convoID][cartKey] = cartVal
                    # cartVal.update({'enabled': True})
                    # cartVal.update({'via_loadout': True})
 
    await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))

async def clear_loadout(convoID):
    if convoID in current_loadout:
        del current_loadout[convoID]
        
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
        val['config'][field] = value
        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json({key:val})
                }
        )
