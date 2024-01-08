novaSession = {}
novaConvo = {}
available_loadouts = {}
active_loadouts = {}
loadout_cartridges = {}
current_loadout = {}
current_config = {}
active_cartridges = {}
chatlog = {}
cartdigeLookup = {}
available_convos = {}
agentName = {}
system_threads = {}

command_state = {}

all_cartridges = {}

command_loops = {}

# import json
# from session.appHandler import websocket
# from session.user import set_user_value, get_user_value
# from core.convos import get_loadout_logs,  start_new_convo, get_loadout_logs, set_convo, get_latest_convo
# from core.loadout import add_loadout, get_loadouts, set_loadout, drop_loadout, set_read_only,set_loadout_title, update_loadout_field,clear_loadout, get_latest_loadout_convo, add_loadout_to_profile
# from tools.debug import eZprint, eZprint_anything
# from core.cartridges import retrieve_loadout_cartridges
# from core.nova import initialise_conversation, initialiseCartridges, loadCartridges, runCartridges

# async def request_loadouts(sessionID):
#     latest_loadout = await get_loadouts(sessionID)

# async def handle_loadout_change(target_loadout, sessionID, userID):
#         params = {}
#         # eZprint( 'current loadout is ' + str(current_loadout[sessionID]), ['LOADOUT', 'INITIALISE'])
#         # if 'params' in parsed_data['data']:
#         #     params = parsed_data['data']['params']
        
#         await set_loadout(target_loadout, sessionID)
#         await websocket.send(json.dumps({'event': 'set_loadout', 'payload': target_loadout}))
#         await get_loadout_logs(target_loadout, sessionID)

#         convoID = await get_user_value(userID, 'latest_convo')


#         # gets or creates conversation - should this pick up last?
#         # convoID = await get_latest_loadout_convo(latest_loadout)
#         if not convoID:
#             convoID = await start_new_convo(sessionID, target_loadout)

#         await retrieve_loadout_cartridges(target_loadout, convoID)
#         await set_convo(convoID, sessionID, target_loadout)

#         await initialise_conversation(sessionID, convoID, params)
#         await runCartridges(sessionID, convoID, target_loadout)

#         # async def handle_loadout_actions(sessionID, convoID, target_loadout):


# async def handle_new_user(sessionID):
     
#         latest_loadout = None
#         if sessionID in novaSession:
#             userID = None
#             if 'userID' in novaSession[sessionID]:
#                 userID = novaSession[sessionID]['userID']
#                 if not 'met_nova' in novaSession[sessionID] or not novaSession[sessionID]['met_nova']:
#                     await add_loadout_to_profile('7531ab40afd82ba4', userID)
#                     novaSession[sessionID]['needs_meet_nova'] = False
#                     await set_user_value(userID, 'met_nova', True)
#                     await set_loadout('7531ab40afd82ba4', sessionID)
#                     latest_loadout = '7531ab40afd82ba4'
#                     await websocket.send(json.dumps({'event': 'set_loadout', 'payload': latest_loadout}))
#                     await get_loadout_logs(latest_loadout, sessionID)

                    
              
#         if not 'met_sam' in novaSession[sessionID] or not novaSession[sessionID]['met_sam'] and latest_loadout == '7531ab40afd82ba4':
#             # events = await get_user_events(userID)

#             await websocket.send(json.dumps({'event': 'set_met_sam', 'payload':False}))


# async def switch_convo(requested_convoID, current_convoID):

    # if requested_convoID not in novaConvo:
    #     if current_convoID in novaConvo:
    #         novaConvo[requested_convoID] = novaConvo[current_convoID]
    #         novaConvo.pop(current_convoID)
           
    # if requested_convoID not in available_cartridges:
    #     if current_convoID in available_cartridges:
    #         available_cartridges[requested_convoID] = available_cartridges[current_convoID]
    #         available_cartridges.pop(current_convoID)

    # if requested_convoID not in current_loadout:
    #     if current_convoID in current_loadout:
    #         current_loadout[requested_convoID] = current_loadout[current_convoID]
    #         current_loadout.pop(current_convoID)

    # if requested_convoID not in current_config:
    #     if current_convoID in current_config:
    #         current_config[requested_convoID] = current_config[current_convoID]
    #         current_config.pop(current_convoID)

    ## TODO: switch to session ID as base tracker        

