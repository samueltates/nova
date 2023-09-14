import asyncio
from prisma import Json
import json

from session.prismaHandler import prisma
from session.appHandler import app, websocket
from session.sessionHandler import active_cartridges, novaConvo, current_loadout, available_loadouts, active_loadouts, current_config, available_convos, novaSession
from tools.debug import eZprint

async def get_loadouts(sessionID):

    """
    
    This asynchronous function 'get_loadouts' retrieves and manages a user's loadouts 
    for a given session ID. 
    
    A loadout is a configuration of cartridges (custom prompts and behaviours) as well as settings for how conversatinos are shared, loaded, and other behaviours.
    
    This includes setting the current loadout based on user's previous selection, and making all the user's loadouts available for the session. The loadouts are 
    then sent to the user via websockets.
    
    """

    #TODO: add definitions for loadout, cartridge, and config

    # instantiates session if none - shouldn't be necessary
    if sessionID not in novaSession:
        novaSession[sessionID] = {}

    # if not a user sets to none (to ensure value there for check)
    if 'userID' not in novaSession[sessionID]:
        novaSession[sessionID]['userID'] = None
    userID = novaSession[sessionID]['userID']

    # gets loadouts associated with that user
    loadouts = await prisma.loadout.find_many(
        where={ "UserID": userID },
    )
    
    # stores loadouts for session - does this get used much? 
    available_loadouts[sessionID] = {}

    for loadout in loadouts:
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            if key == loadout.key:
                available_loadouts[sessionID][key] = val

    user_details = await prisma.user.find_first(
        where={ "UserID": userID },
    )

    # if its a signed in user, checks what last loadout was, sets to that
    # otherwise sets current loadout to none
    # if user_details:
    #     userBlob = json.loads(user_details.json())['blob']
    #     # print(userBlob)
    #     if 'current_loadout' not in userBlob:
    #         current_loadout[sessionID] = None
    #     else:
    #         if userBlob['current_loadout']:
    #             current_loadout[sessionID] = userBlob['current_loadout']
    #             current_remote_loadout = current_loadout[sessionID]
    #             await set_loadout(current_loadout[sessionID], sessionID)
    #             await websocket.send(json.dumps({'event': 'set_loadout', 'payload': current_loadout[sessionID]}))
    #         else: 
    #             current_loadout[sessionID] = None
    await websocket.send(json.dumps({'event': 'populate_loadouts', 'payload': available_loadouts[sessionID]}))



async def set_loadout(loadout_key: str, sessionID, referal = False):

    eZprint('set_loadout')

    # gets remote loadout content - this includes the cartridges that loadout has, the configuration file with information like title and setup rules
    remote_loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key)}
    )

    # print(remote_loadout)
    # instantiates session if none - shouldn't be necessary
    #TODO : REMOVE
    if sessionID not in current_loadout:
        current_loadout[sessionID] = None
    current_loadout[sessionID] = loadout_key

    config = {}

    # if value is present unpacks it, figures out if its the owner which changes the behaviours
    if remote_loadout:
        
        blob = json.loads(remote_loadout.json())['blob']
        novaSession[sessionID]['owner'] = False

        if novaSession[sessionID]['userID']:

            if remote_loadout.UserID == novaSession[sessionID]['userID']:
                novaSession[sessionID]['owner'] = True

            
            user_details = await prisma.user.find_first(
                where={ "UserID": novaSession[sessionID]['userID'] },
            )

            if user_details:
                user_blob = json.loads(user_details.json())['blob']
                user_blob['current_loadout'] = loadout_key
                update_user = await prisma.user.update(
                    where = {
                        'id' : user_details.id
                    },
                    data = {
                        'blob': Json(user_blob)
                        }
                )

                # print(update_user)

        # new - sets up on server (shared) loadout object
        # should get loaded in and out of memory, be shared across sessions
        # can probably then bounce / debounce changes to main server




        # print(active_loadouts)


        for key, val in blob.items():
            if loadout_key not in active_loadouts:
                active_loadouts[loadout_key] = val
            # loadout_cartridges = val['cartridges']
            # config = val['config']

    # sets the config to current - shiould just be 'configs[loadoutid]'

    if sessionID not in current_config:
        current_config[sessionID] = {}
    current_config[sessionID] = config

    # sends config over to front end for that loadout 
    # TODO : Switch to front end side dict of [loadouts][config] so can handle multiple + switching
    await websocket.send(json.dumps({'event': 'set_config', 'payload':{'config': config, 'owner': novaSession[sessionID]['owner']}}))
    
async def add_loadout(loadout: str, convoID):
    
    current_loadout[convoID] = loadout
    active_cartridges[convoID] = {}

    new_loadout = await prisma.loadout.create(
        data={
            "key": str(loadout),
            'UserID': novaSession[convoID]['userID'],
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
        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': active_cartridges[convoID]}))
  
async def add_cartridge_to_loadout(convoID, cartridge, loadout_key):
    eZprint('add cartridge to loadout triggered')

    loadout = active_loadouts[loadout_key]
    if not loadout:
        return
    
    loadout_config = loadout.get('config', {})
    cleanSlate = loadout_config.get('cleanSlate', False)
    print(loadout_config)
    print(loadout)
    if cleanSlate:
        print('clean slate detected')
        if 'convos' not in loadout:
            loadout['convos'] = {}
        if convoID not in loadout['convos']:
            loadout['convos'][convoID]={}
        if 'cartridges' not in loadout['convos'][convoID]:
            loadout['convos'][convoID]['cartridges'] = []
        loadout['convos'][convoID]['cartridges'].append({
            'key':cartridge, 
            'settings':{
                'enabled':True,
                'softDelete':False,
                'minimised':True,
                'pinned' : False,
        }})

    if 'cartridges' not in loadout:
        loadout['cartridges'] = []

    loadout['cartridges'].append({
        'key':cartridge, 
        'settings':{
            'enabled':True,
            'softDelete':False,
            'minimised':True,
            'pinned' : False,
    }})


    remote_loadout = await prisma.loadout.find_first(
        where={ "key": loadout_key },
    )
    
    # print(remote_loadout)

    update = await prisma.loadout.update(
        where = {
            'id' : remote_loadout.id
        },
        data={
            "blob":Json({loadout_key:loadout})
            }
    )
    print('loadout updated')
    # print(update)
        

async def update_settings_in_loadout(convoID, cartridge, settings, loadout_key):
    eZprint('update settings in loadout triggered')

    loadout = active_loadouts[loadout_key]
    if not loadout:
        return
    loadout_config = loadout.get('config', {})
    cleanSlate = loadout_config.get('cleanSlate', False)

    if cleanSlate:
        # if cleanslate then it sets all the settings at the convo level
        print('clean slate detected')
        if 'convos' not in loadout:
            loadout['convos'] = {}
        if convoID not in loadout['convos']:
            loadout['convos'][convoID]={}
        if 'cartridges' not in loadout['convos'][convoID]:
            loadout['convos'][convoID]['cartridges'] = []
        # making edits to list copy to avoid 'list changed size during iteration' error
        cartridges_copy = loadout['convos'][convoID]['cartridges'][:]
        for cart in cartridges_copy:
            if 'key' in cart and cart['key'] == cartridge:
                if 'softDelete' in settings and settings['softDelete'] == True:
                    loadout['convos'][convoID]['cartridges'].remove(cart)
                if 'settings' not in cart:
                    cart['settings'] = {}                
                for settingsKey, settingsVal in settings.items():
                    if settingsKey in ['enabled', 'minimised', 'softDelete', 'pinned']:
                        cart['settings'][settingsKey] = settingsVal
        # write back to original list if there's been a change
        loadout['convos'][convoID]['cartridges'] = cartridges_copy

        # print(loadout['convos'])
        # print('adding cartridge ' + cartridge + ' to convo ' + convoID)
        # but it also sets only the 'pinned' status at the base level
        loadout_cartridge = loadout['cartridges'][:]
        for cart in loadout_cartridge:
            if 'key' in cart and cart['key'] == cartridge:
                for settingsKey, settingsVal in settings.items():
                    if settingsKey in ['pinned']:
                        cart['settings'][settingsKey] = settingsVal 
        
    else:
    #otherwise it sets all the settings at the base level
        if 'cartridges' not in loadout:
            loadout['cartridges'] = []
        cartridges_copy = loadout['cartridges'][:]
        for cart in cartridges_copy:
            if 'key' in cart and cart['key'] == cartridge:
                if 'softDelete' in settings and settings['softDelete'] == True:
                    loadout['cartridges'].remove(cart)
                if 'settings' not in cart:
                    cart['settings'] = {}                
                for settingsKey, settingsVal in settings.items():
                    if settingsKey in ['enabled', 'minimised', 'softDelete', 'pinned']:
                        cart['settings'][settingsKey] = settingsVal
        # write back to original list if there's been a change
        loadout['cartridges'] = cartridges_copy
        
    remote_loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    # print(loadout_key)

    update = await prisma.loadout.update(
        where = {
            'id' : remote_loadout.id
        },
        data={
            "blob":Json({loadout_key:loadout})
            }
    )
    print('loadout updated')
    # print(update)


async def clear_loadout(sessionID, convoID):
    current_loadout[sessionID] = None
    novaSession[sessionID]['owner'] = True
    active_cartridges[convoID] = {}

    # if novaSession[sessionID]['userID']:
    #     user_details = await prisma.user.find_first(
    #         where={ "UserID": novaSession[sessionID]['userID'] },
    #     )

        # blob = json.loads(user_details.json())['blob']
        # blob['current_loadout'] = None
        # if user_details:
        #     update_user = await prisma.user.update(
        #         where = {
        #             'id' : user_details.id
        #         },
        #         data = {
        #             'blob': Json(blob)
        #             }
        #     )

        #     # print(update_user)

    await websocket.send(json.dumps({'event': 'set_config', 'payload':{'config': current_config[sessionID], 'owner': novaSession[sessionID]['owner']}}))
    await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': active_cartridges[convoID]}))


# async def add_loadout_to_session(loadout_key: str, sessionID):

#     loadout = await prisma.loadout.find_first(
#         where={ "key": str(loadout_key)}
#     )

#     blob = json.loads(loadout.json())['blob']
#     available_loadouts[sessionID] = {}
#     for key, val in blob.items():
#         available_loadouts[sessionID][key] = val

#     # print('available_loadouts')
#     # print(available_loadouts[convoID])

#     await websocket.send(json.dumps({'event': 'populate_loadouts', 'payload': available_loadouts[sessionID]}))
        
async def delete_loadout(loadout_key: str, sessionID):
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    # print(loadout)
    await prisma.loadout.update(
        where={
            'id': loadout.id
        }
    )

    if sessionID in current_loadout:
        current_loadout[sessionID] = None

    await get_loadouts(sessionID)

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
    print('update_loadout_field')
    # print(loadout_key, field, value)
    active_loadout = active_loadouts[loadout_key]
    if not active_loadout:
        return
    
    print(active_loadout)

    if 'config' in active_loadout:
        active_loadout['config'][field] = value

    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )

    update = await prisma.loadout.update(
        where = {
            'id' : loadout.id
        },
        data={
            "blob":Json({loadout_key:active_loadout})
            }
    )
        # print(update)
