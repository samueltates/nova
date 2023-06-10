
from sessionHandler import novaConvo, availableCartridges, chatlog, cartdigeLookup
from keywords import get_summary_from_keyword, keywords_available
from debug import eZprint

async def handle_commands(command_object, convoID):
    userID = novaConvo[convoID]['userID']
    eZprint('handling command')
    print(command_object)
    for key, val in command_object.items():
        print(key, val)
        if key == 'command':
            val = val.split(' ')
            if val[0] == 'select':
                if val[1] == 'keyword':
                    get_summary_from_keyword(val[2], convoID)


