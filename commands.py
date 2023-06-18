
from keywords import get_summary_from_keyword, keywords_available
from debug import eZprint
from cartridges import addCartridge, updateCartridgeField, get_cartridge_list, whole_cartridge_list
from sessionHandler import availableCartridges
from cartridges import whole_cartridge_list
from memory import summarise_from_range
# from nova import handleIndexQuery
import asyncio

system_threads = {}

command_state = {}

all_cartridges = {}

command_loops = {}

async def handle_commands(command_object, convoID, thread = 0, loop = 0):
    eZprint('handling command')
    print(command_object)
    if command_object:
        name = ''
        args = ''

        if 'name' in command_object:
            name = command_object['name']
        if 'args' in command_object:
            args = command_object['args']

    eZprint('parsing command')
    if convoID not in command_state:
        command_state[convoID] = {}

    if 'list' in name or name in 'list':
        response = await list_files(args, convoID)
        print('back at list parent function')
        print(response)
        return response
    
    print('shouldnt be going past here')
    if 'continue' in name :
        response = await continue_command(args, convoID, thread, loop)
        return response
    
    if 'return' in name:
        response = await return_from_thread(args, convoID, thread, loop)
        return response
    
    command_return = {"status": "", "name" : name, "message": ""}

    if 'create' in name or name in 'create':
        eZprint('create file')
        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                if 'label' in val and args['filename'].lower() in val['label'].lower() or args['filename'].lower() in val['label'].lower():
                    blocks = []
                    if 'text' in args:
                        blocks.append({'text': args['text']})

                    cartVal = {
                    'cartKey' : key,
                    'convoID' : convoID,
                    'fields' : {
                        'blocks' :blocks,
                    }
                    }
                    updateCartridgeField(convoID, key, cartVal)
                    command_return['status'] = "success"
                    command_return['message'] = "file " +args['filename']  + " exists, so appending to file"
                    print(command_return)
                    return command_return
                
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
            command_return['message'] = "file " +args['filename']  + " created"
            print(command_return)
            return command_return
    if 'write' in name or name in 'write':
        eZprint('writing file')
        if 'filename' in args:
            for key, val in availableCartridges[convoID].items():
                if 'label' in val and args['filename'].lower() in val['label'].lower():                        
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
                        command_return['status'] = "success"
                        command_return['message'] = "file " +args['filename']  + " exists, so appending to file"
                        print(command_return)
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
                if 'label' in val and args['filename'].lower() in val['label'].lower():
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
                if 'label' in val and args['filename'].lower() in val['label'].lower():
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
                if 'label' in val and args['filename'].lower() in val['label'].lower():
                    
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
    else:
        command_return['status'] = "error"
        command_return['message'] = "command not found"
        print(command_return)
        return command_return


list_return_string = "\n >_"


async def list_files(name, convoID):
    command_return = {"status": "", "name" : name, "message": ""}

    eZprint('list available files')
    string = '\nFiles available:\n'

    label = ''
    type = ''
    description = ''
    preview = ''
    state = ''
    string = ''
    await get_cartridge_list(convoID)
    if convoID in whole_cartridge_list:
        for key, val in whole_cartridge_list[convoID].items():
            if 'label' in val:
                string += '\n -- ' + val['label']
            if 'type' in val:
                string += ' -- '+val['type']
            if 'description' in val:
                string +=  '\n' + val['description']
            if 'prompt' in val:
                string += val['prompt'][0:20] + '...\n'
            if 'enabled' in val and val['enabled'] == True:
                string += ' -- open'
            else:
                string += ' -- closed'
            string += '\n'

    else:
        for key, val in availableCartridges[convoID].items():
            if 'label' in val:
                string += '\n -- ' + val['label']
            if 'type' in val:
                string += ' -- '+val['type']
            if 'description' in val:
                string +=  '\n' + val['description']
            if 'prompt' in val:
                string += val['prompt'][0:20] + '...\n'
            if 'enabled' in val and val['enabled'] == True:
                string += ' -- open'
            else:
                string += ' -- closed'
            string += '\n'


    string += list_return_string
    string += "\n"
    if len(string) > 2000:
        command_return = await large_document_loop(string, name, convoID)
        return command_return

    command_return['status'] = 'success'
    command_return['message'] = string
    command_state[convoID]['files_open'] = True
    print(command_return)
    return command_return

async def return_from_thread(args, convoID, thread):

    eZprint('returning from thread')    

    command_return = {"status": "", "name" : args['name'], "message": ""}
    if args['message'] in command_state[convoID]:
        command_return['status'] = 'success'
        command_return['message'] = args['message']
        command_loops[convoID][thread]['status'] = 'success'
        command_loops[convoID][thread]['message'] = args['message']
        return command_return
    else:
        command_return['status'] = 'error'
        command_return['message'] = 'message not found'
        command_loops[convoID][thread]['status'] = 'error'
        command_loops[convoID][thread]['message'] = 'message not found'
        return command_return


async def continue_command(convoID, thread, loop):
    eZprint('continuing command' + str(loop))
    if convoID in command_loops:
        if thread in command_loops[convoID]:
            command_return = large_document_loop(convoID, thread, loop)
            return command_return

async def large_document_loop(string, command = '', convoID= '', thread = 0, loop = 0):

    eZprint('large document loop' + str(loop) + ' ' + str(thread))
    command_return = {"status": "", "name" : command, "message": ""}
    if convoID not in command_loops:
        command_loops[convoID] = {}
    if thread not in command_loops[convoID]:
        command_loops[convoID][thread] = {}

    if loop == 0:
        
        eZprint('loop 0')
        sections = []
        range = 2000
        i = 0

        while i < len(string):
            sections.append(string[i:i+range])
            i += range


        eZprint('sections created')
        # eZprint(sections)
        # eZprint(len(sections))
        command_loops[convoID][thread]['sections'] = sections
        command_loops[convoID][thread]['command'] = command

    else:
        eZprint('loop not 0 sections retrieved')

        sections = command_loops[convoID][thread]['sections']
        command = command_loops[convoID][thread]['command']

    sections = command_loops[convoID][thread]['sections']
    # print(sections)
    # print(len(sections))
    # print(loop)
    if loop < len(sections):
        eZprint('returning sections based on loop')
        command_return['status'] = 'in-progress'
        
        message = "Files Available:\n Section " + str(loop) + " of " + str(len(sections)) + "\n" + sections[loop]  
        command_return['message'] = message
        command_return['name'] = command
        print(command_return)
        return command_return
    
    else:
        eZprint('Loop complete as sections val is not last val')
        command_return['status'] = 'success'
        message = "List is complete, closing loop." 
        command_return['message'] = message
        print(command_return)
        return command_return



# ongoing_return_string = """\n Commands available: 'open' to add document to working memory, 'close' to remove, 'continue' to see next page, 'note' to take note or 'return' to return to main thread with message."""

ongoing_return_string = """\n ~continue for next page, or return for home."""
