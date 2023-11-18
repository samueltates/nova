import asyncio
from prisma import Json
import json

from session.prismaHandler import prisma
from session.appHandler import app, websocket
from session.sessionHandler import active_cartridges, novaConvo, current_loadout, available_loadouts, active_loadouts, current_config, available_convos, novaSession
from tools.debug import eZprint, eZprint_anything

CLASS_KEY = 'LOADOUT'

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
            if val.get('config', {}) == {}:
                continue
            if val.get('config', {}).get('dropped', False):
                continue
            if key == loadout.key:
                available_loadouts[sessionID][key] = val

    user_details = await prisma.user.find_first(
        where={ "UserID": userID },
    )
    # if not loadout: 
        # await loadCartridges(sessionID, convoID)
    novaSession[sessionID]['owner'] = True
    await websocket.send(json.dumps({'event': 'set_config', 'payload':{'config': {}, 'owner': novaSession[sessionID]['owner']}}))
 
    # if its a signed in user, checks what last loadout was, sets to that
    # otherwise sets current loadout to none
    latest_loadout = None
    if user_details:
        userBlob = json.loads(user_details.json())['blob']
        # print(userBlob)
        if 'latest_loadout' not in userBlob:
            latest_loadout = None
        else:
            if userBlob['latest_loadout']:
                latest_loadout = userBlob['latest_loadout']
            else: 
                latest_loadout = None
    await websocket.send(json.dumps({'event': 'populate_loadouts', 'payload': available_loadouts[sessionID]}))
    return latest_loadout



async def set_loadout(loadout_key: str, sessionID, referal = False):

    eZprint('set_loadout' + str(loadout_key), ['LOADOUT', 'INITIALISE'])

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
                user_blob['latest_loadout'] = loadout_key
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
        eZprint_anything(blob, ['LOADOUT', 'INITIALISE'], message='loadout pulled down')
        eZprint_anything(active_loadouts, ['LOADOUT', 'INITIALISE'], message= 'loadouts in memory')

        for key, val in blob.items():
            # if loadout_key not in active_loadouts:
            active_loadouts[loadout_key] = val
            # loadout_cartridges = val['cartridges']
            config = val['config']

    # sets the config to current - shiould just be 'configs[loadoutid]'

    if sessionID not in current_config:
        current_config[sessionID] = {}
    current_config[sessionID] = config
    eZprint_anything(config, ['LOADOUT', 'INITIALISE'])
    # sends config over to front end for that loadout 
    # TODO : Switch to front end side dict of [loadouts][config] so can handle multiple + switching
    await websocket.send(json.dumps({'event': 'set_config', 'payload':{'config': config, 'owner': novaSession[sessionID]['owner']}}))
    
async def add_loadout(loadout: str, convoID):
    
    loadout_values = {
        'cartridges':[],
        'config': { 
                'title': '...',
                'read_only': False,
                'convo_summary': 'one_way',
                'show_cartridges' : True,
                'shared' : False,
                }
    }

    active_loadouts[loadout] = loadout_values

    new_loadout = await prisma.loadout.create(
        data={
            "key": str(loadout),
            'UserID': novaSession[convoID]['userID'],
            "blob":Json({loadout:loadout_values})
        }
    )

  
async def add_cartridge_to_loadout(convoID, cartridge, loadout_key):
    DEBUG_KEYS = ['LOADOUT', 'ADD_CARTRIDGE']
    eZprint('add cartridge to loadout triggered', DEBUG_KEYS)

    loadout_record = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    loadout = json.loads(loadout_record.json()).get('blob', {}).get(loadout_key, None)
    if not loadout:
        return
    
    loadout_config = loadout.get('config', {})
    cleanSlate = loadout_config.get('cleanSlate', False)
    # print(loadout_config)
    # print(loadout)
    if cleanSlate:
        eZprint('clean slate detected', DEBUG_KEYS)
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

    DEBUG_KEYS = ['LOADOUT', 'UPDATE_SETTINGS']
    eZprint('update settings in loadout triggered', DEBUG_KEYS, line_break=True)
    loadout_record = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    loadout = json.loads(loadout_record.json()).get('blob', {}).get(loadout_key, None)
    if not loadout:
        return
    loadout_config = loadout.get('config', {})
    cleanSlate = loadout_config.get('cleanSlate', False)

    if cleanSlate:
        # if cleanslate then it sets all the settings at the convo level
        eZprint('clean slate detected', DEBUG_KEYS)
        if 'convos' not in loadout:
            loadout['convos'] = {}
        if convoID not in loadout['convos']:
            loadout['convos'][convoID]={}
        if 'cartridges' not in loadout['convos'][convoID]:
            loadout['convos'][convoID]['cartridges'] = []
        # making edits to list copy to avoid 'list changed size during iteration' error
        # cartridges_copy = loadout['convos'][convoID]['cartridges'][:]
        for cart in loadout['convos'][convoID]['cartridges']:
            if 'key' in cart and cart['key'] == cartridge:
                if 'settings' not in cart:
                    cart['settings'] = {}                
                for settingsKey, settingsVal in settings.items():
                    if settingsKey in ['enabled', 'minimised', 'softDelete', 'pinned', 'position']:
                        cart['settings'][settingsKey] = settingsVal
                if 'softDelete' in settings and settings['softDelete'] == True:
                    loadout['convos'][convoID]['cartridges'].remove(cart)
        # write back to original list if there's been a change

        # print(loadout['convos'])
        # print('adding cartridge ' + cartridge + ' to convo ' + convoID)
        # but it also sets only the 'pinned' status at the base level
        # loadout_cartridge = loadout['cartridges'][:]
        for cart in loadout['cartridges']:
            if 'key' in cart and cart['key'] == cartridge:
                for settingsKey, settingsVal in settings.items():
                    if settingsKey in ['enabled', 'minimised', 'softDelete', 'pinned',  'position']:
                        cart['settings'][settingsKey] = settingsVal 
        
    else:
    #otherwise it sets all the settings at the base level
        if 'cartridges' not in loadout:
            loadout['cartridges'] = []
        # cartridges_copy = loadout['cartridges'][:]
        for cart in loadout['cartridges']:
            if 'key' in cart and cart['key'] == cartridge:
                if 'settings' not in cart:
                    cart['settings'] = {}                
                for settingsKey, settingsVal in settings.items():
                    if settingsKey in ['enabled', 'minimised', 'softDelete', 'pinned']:
                        cart['settings'][settingsKey] = settingsVal
                if 'softDelete' in settings and settings['softDelete'] == True:
                    loadout['cartridges'].remove(cart)
  
        
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
    eZprint('loadout updated', DEBUG_KEYS)
    eZprint_anything(update, DEBUG_KEYS)


async def clear_loadout(sessionID, convoID):
    DEBUG_KEYS = ['LOADOUT', 'CLEAR_LOADOUT']
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
    await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': active_cartridges[convoID], 'convoID': convoID}))


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
        
async def drop_loadout(loadout_key: str, sessionID):
    DEBUG_KEYS = ['LOADOUT', 'DROP_LOADOUT']
    eZprint('drop_loadout', DEBUG_KEYS)
    await update_loadout_field(loadout_key, 'dropped', True)
    active_loadouts.pop(loadout_key, None)
    available_loadouts[sessionID].pop(loadout_key, None)
    await websocket.send(json.dumps({'event': 'populate_loadouts', 'payload': available_loadouts[sessionID]}))
    

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


async def get_latest_loadout_convo(loadout_key):
    DEBUG_KEYS = ['LOADOUT', 'GET_LATEST_LOADOUT_CONVO']
    eZprint('get_latest_loadout_convo', DEBUG_KEYS)
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )
    
    if loadout:
        eZprint_anything(loadout, DEBUG_KEYS)
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            if 'config' in val and 'latest_convo' in val['config']:
                eZprint_anything(val['config']['latest_convo'], DEBUG_KEYS, message='latest convo')
                await websocket.send(json.dumps({'event': 'set_convoID', 'payload':{'convoID': val['config']['latest_convo']}}))
                return val['config']['latest_convo']
    return None


async def update_loadout_field(loadout_key, field, value):
    DEBUG_KEYS = ['LOADOUT', 'UPDATE_LOADOUT_FIELD']
    eZprint('update_loadout_field', DEBUG_KEYS)
    # print(loadout_key, field, value)
    # active_loadout = active_loadouts[loadout_key]
    eZprint(loadout_key, DEBUG_KEYS, message='update field')

    active_loadout = {} 
    loadout = await prisma.loadout.find_first(
        where={ "key": str(loadout_key) },
    )

    if loadout:
        
        blob = json.loads(loadout.json())['blob']
        for key, val in blob.items():
            active_loadout = val
            
        if 'config' in active_loadout:
            active_loadout['config'][field] = value

        update = await prisma.loadout.update(
            where = {
                'id' : loadout.id
            },
            data={
                "blob":Json({loadout_key:active_loadout})
                }
        )
            # print(update)
