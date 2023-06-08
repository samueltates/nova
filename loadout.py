from prismaHandler import prisma
from prisma import Json
import json
from appHandler import app, websocket
from nova import availableCartridges, runCartridges
from sessionHandler import novaConvo, current_loadout, available_loadouts


async def get_loadouts(convoID):
    userID = novaConvo[convoID]['userID']

    loadouts = await prisma.loadout.find_many(
        where={ "UserID": userID },
    )
    current_loadout[convoID] = []
    available_loadouts[convoID] = {}
    for loadout in loadouts:
        print(loadout)
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            available_loadouts[convoID][key] = val

    await websocket.send(json.dumps({'event': 'populate_loadouts', 'payload': available_loadouts[convoID]}))

async def add_loadout(loadout: str, convoID):
    loadout_cartridges = []
    current_loadout[convoID] = loadout

    config = {
        'read_only': True,
        'convo_summary': 'one_way',
        'show_cartridges' : False
    }

    new_loadout = await prisma.loadout.create(
        data={
            "key": str(loadout),
            'UserID': novaConvo[convoID]['userID'],
            "blob":Json({loadout:{
                'cartridges':loadout_cartridges,
                'config': config
            }})
        }
    )

async def add_cartridge_to_loadout(convoID, cartridge):
    loadout = await prisma.loadout.find_first(
        where={ "key": str(current_loadout[convoID]) },
    )
    
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

async def set_loadout(loadout_key: str, convoID, referal = False):

    loadout = await prisma.loadout.find_first(
        where={ "key": loadout_key },
    )
    current_loadout[convoID] = loadout_key
    print(loadout)
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
        print(remote_cartridges)
        cartridges_to_add.append(remote_cartridges)

    if len(cartridges_to_add) != 0:
        availableCartridges[convoID] = {}
        for cartridge in cartridges_to_add:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal:
                    print(cartVal)
                    availableCartridges[convoID][cartKey] = cartVal
                    # cartVal.update({'enabled': True})
                    # cartVal.update({'via_loadout': True})

        await runCartridges(convoID)    

        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))

