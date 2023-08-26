novaSession = {}
novaConvo = {}
available_loadouts = {}
loadout_cartridges = {}
current_loadout = {}
current_config = {}
available_cartridges = {}
chatlog = {}
cartdigeLookup = {}
available_convos = {}
agentName = {}



system_threads = {}

command_state = {}

all_cartridges = {}

command_loops = {}
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

