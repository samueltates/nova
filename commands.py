
from keywords import get_summary_from_keyword, keywords_available
from debug import eZprint
from cartridges import addCartridge, updateCartridgeField, get_cartridge_list, whole_cartridge_list
from sessionHandler import availableCartridges
from memory import summarise_from_range
# from nova import handleIndexQuery
import asyncio

system_threads = {}

command_state = {}

all_cartridges = {}

async def handle_commands(command_object, convoID):
    eZprint('handling command')
    print(command_object)
    if command_object:
        name = ''
        args = ''

        if 'name' in command_object:
            name = command_object['name']
        if 'args' in command_object:
            args = command_object['args']
        
        command_response = await parse_command(name, args, convoID)
        return command_response
    # else:
    #     eZprint('no command found')
    #     command_response = {"status": "", "name" : "command", "message": ""}
    #     command_response['status'] = "Error."
    #     command_response['message'] = "No command found."
    #     return command_response

async def parse_command(name, args, convoID):
    eZprint('parsing command')
    if convoID not in command_state:
        command_state[convoID] = {}

    command_return = {"status": "", "name" : name, "message": ""}
    if 'list' in name:
        eZprint('list available files')
        string = '\nFiles available:\n'

        await get_cartridge_list(convoID)
        for key, val in availableCartridges[convoID].items():
            label = ''
            type = ''
            description = ''
            state = ''
            if 'enabled' in val and val['enabled'] == True:
                state = 'open'
            else: 
                state = 'closed'
            if 'label' in val:
                label = val['label']
            if 'type' in val:
                type = val['type']
            if 'description' in val:
                description = val['description']
            string += '\n--' + label+ " : " + type + " - " + description + " - [" + state + "]\n"

        string += list_return_string
        string += "\n"
        
        command_return['status'] = 'success'
        command_return['message'] = string
        command_state[convoID]['files_open'] = True
        print(command_return)
        return command_return
    if 'create' in name or name in 'create':
        eZprint('create file')
        if 'filename' in args:
            blocks = []
            if 'text' in args:
                blocks.append({'text': args['text']})
            cartVal = {
            'label' : args['filename'],
            'blocks' :blocks,
            'type' : 'text'
            }
            print(cartVal)
            await addCartridge(cartVal, convoID)
            command_return['status'] = "success"
    if 'write' in name or name in 'write':
        eZprint('writing file')
        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                if 'label' in val and args['filename'].lower() in val['label'].lower() or args['filename'].lower() in val['label'].lower():
                        
                        if 'blocks' not in val:
                            val['blocks'] = []
                        val['blocks'].append({'text': args['text']})
                        payload = {
                            'convoID': convoID,
                            'cartKey' : key,
                            'fields':
                                    {'blocks': val['blocks']}
                                    }
                        await updateCartridgeField(payload)
                else : 
                    blocks = []
                    if 'text' in args:
                        blocks.append({'text': args['text']})
                    cartVal = {
                    'label' : args['filename'],
                    'blocks' :blocks,
                    'type' : 'text'
                    }
                    print(cartVal)
                    await addCartridge(cartVal, convoID)

                command_return['status'] = "success"
                command_return['message'] = "file " +args['filename']  + " written"
                print(command_return)
                return command_return
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'filename' missing"
        return command_return

    if 'append' in name or name in 'append':
        eZprint('appending file')
        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                if 'label' in val and args['filename'].lower() in val['label'].lower() or args['filename'].lower() in val['label'].lower():
                    if 'blocks' not in val:
                        val['blocks'] = []
                    if 'text' in args:
                        val['blocks'].append({'text': args['text']})
                    payload = {
                        'convoID': convoID,
                        'cartKey' : key,
                        'fields':
                                {'blocks': val['blocks']}
                                }
                    await updateCartridgeField(payload)                    
                    command_return['status'] = "success"
                    command_return['message'] = "file " +args['filename']  + " appended"
                    print(command_return)
                    return command_return
            else: 
                command_return['status'] = "Error."
                command_return['message'] = "File not found."
                print(command_return)
                return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            print(command_return)
            return command_return

    if name in 'preview' or 'preview' in name:
        eZprint('previewing file')
        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                if 'label' in val and args['filename'].lower() in val['label'].lower() or args['filename'].lower() in val['label'].lower():
                    preview_string = val['filename'] + '\n'
                    if 'blocks' in val:
                        for block in val['blocks']:
                            preview_string += block['body'] + '\n'
                    preview_string += '\n'
                    command_return['status'] = "success"
                    command_return['message'] = preview_string
                    print(command_return)
                    return command_return
            else: 
                command_return['status'] = "Error."
                command_return['message'] = "File not found."
                print(command_return)
                return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            print(command_return)
            return command_return
                
    if name in 'open' or 'open' in name :
        eZprint('reading file')

        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                return_string = ''
                if 'label' in val:
                    if args['filename'].lower() in val['label'].lower() or ['label'].lower() in args['filename'].lower():
                        print(val)

                        if 'enabled' not in val:
                            val['enabled'] = True
                        if val['enabled'] == False:
                            val['enabled'] = True
                            return_string += "File " + args['filename'] + " opened.\n"
                        else:
                            return_string += "File " + args['filename'] + " already open.\n"
                        
                        payload = {
                            'convoID': convoID,
                            'cartKey' : key,
                            'fields':
                                    {'enabled': val['enabled']}
                                    }
                        await updateCartridgeField(payload)                    
                        command_return['status'] = "Success."
                        command_return['message'] = return_string
                        print(command_return)
                        return command_return
                else:
                    command_return['status'] = "Error."
                    command_return['message'] = "File name not found.\n"
                    print(command_return)
                    return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            print(command_return)
            return command_return
                
    if name == 'close':
        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                if 'label' in val and args['filename'].lower() in val['label'].lower() or args['filename'].lower() in val['label'].lower():
                    return_string = ''
                    if 'enabled' not in val:
                        val['enabled'] = False
                    if val['enabled'] == True:
                        val['enabled'] = False
                        return_string += "File " + args['filename'] + " closed.\n"
                    else:
                        return_string += "File " + args['filename'] + " already closed.\n"


                    payload = {
                        'convoID': convoID,
                        'cartKey' : key,
                        'fields':
                                {'enabled': val['enabled']}
                                }
                    await updateCartridgeField(payload)                    
                    command_return['status'] = "success"
                    command_return['message'] = return_string
                    return command_return
                else:
                    command_return['status'] = "Error."
                    command_return['message'] = "File not found."
                    return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            return command_return


                
    if name == 'summarise_messages':
        eZprint('summarising conversation')
        summmarised = await summarise_from_range(convoID, args['start-line'], args['end-line'])
        if summmarised:
            command_return['status'] = "success"
            command_return['message'] = "summary completed" 
            print(command_return)
        else:
            command_return['status'] = "error"
            command_return['message'] = "summary failed"
            print(command_return)
        return command_return
    
    if name in 'note' or 'note' in name:
        eZprint('creating note')
        if 'label' not in args:
            args['label'] = ''
            command_return['status'] = "warning"
            command_return['message'] = "no label supplied"
        if 'body' not in args:
            args['body'] = ''
        blocks = []
        blocks.append({'body': args['body']})
        cartVal = {
        'label' : args['label'],
        'blocks' :blocks,
        'type' : 'note'
        }
        print(cartVal)
        await addCartridge(cartVal, convoID)
        command_return['status'] = "success"
        command_return['message'] = "note " +args['label']  + " created"
        print(command_return)
        return command_return

    if name == 'append_note':
        eZprint('appending note')
        eZprint(args)
        for key, val in availableCartridges[convoID].items():
            if val['label'] == args['label']:
                if 'blocks' not in val:
                    val['blocks'] = []
                val['blocks'].append(args['new_line'])
                payload = {
                    'convoID': convoID,
                    'cartKey' : key,
                    'fields':
                            {'blocks': val['blocks']}
                            }
                await updateCartridgeField(payload)
                command_return['status'] = "success"
                command_return['message'] = "note " +args['label']  + " appended"
                print(command_return)
                return command_return
        command_return['status'] = "error"
        command_return['message'] = "note " +args['label']  + " not found"
        print(command_return)
        return command_return
            
    # if name == 'edit_note':
    #     eZprint('editing note')
    #     for key, val in availableCartridges[convoID].items():
    #         if val['label'] == args['label']:
    #             val['blocks'][args['line']] = args['new_line']
    #             payload = {
    #                 'convoID': convoID,
    #                 'cartKey' : key,
    #                 'fields':
    #                         {'blocks': val['blocks']}
    #                         }
    #             await updateCartridgeField(payload)

    if name == 'list_notes':
        eZprint('listing notes')
        string = '\nNotes available:'
        for key, val in availableCartridges[convoID].items():
            if val['type'] == 'note':
                string += '\n' + val['label']
        command_return['status'] = 'success'
        command_return['message'] = string
        print(command_return)
        return command_return
                
    if name == 'open_note':
        eZprint('opening note')
        string = ''
        for key, val in availableCartridges[convoID].items():
            if 'label' in val:
                if val['label'] == args['label']:
                    if val['enabled']:
                        string += '\n' + val['label'] + ' is already open'
                    else:
                        val['enabled'] = True
                        string += '\n' + val['label'] + ' opened'
            
            command_return['status'] = 'success'
            command_return['message'] = string
            print(command_return)
            return command_return
        command_return['status'] = 'error'
        command_return['message'] = 'note not found'

    if name == 'close_note':
        eZprint('closing note')
        string = ''
        for key, val in availableCartridges[convoID].items():
            if val['label'] == args['label']:
                if val['enabled']:
                    val['enabled'] = False
                    string += '\n' + val['label'] + ' closed'
                else:
                    string += '\n' + val['label'] + ' is already closed'
            command_return['status'] = 'success'
            command_return['message'] = string
            print(command_return)
            return command_return
        command_return['status'] = 'error'
        command_return['message'] = 'note not found'

    
    if name == 'query_document':
        eZprint('querying document')
        for key, val in availableCartridges[convoID].items():
            if val['label'] == args['document']:
                queryPackage = {
                'query': args['query'],
                'cartKey': key,
                'convoID': convoID 
                }
        
                # asyncio.create_task(handleIndexQuery(queryPackage))

                print(command_return)
                command_return['status'] = "success"
                command_return['message'] = "index " +args['document']  + "query commenced"
                return command_return
            
        command_return['status'] = "error"
        command_return['message'] = "index " +args['document']  + " not found"
        return command_return


list_return_string = "\n >_"