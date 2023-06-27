
from keywords import get_summary_from_keyword, keywords_available
from debug import eZprint
from cartridges import addCartridge, update_cartridge_field, get_cartridge_list, whole_cartridge_list
from sessionHandler import available_cartridges, current_loadout
from cartridges import whole_cartridge_list
from memory import summarise_from_range
from gptindex import handleIndexQuery, quick_query
from Levenshtein import distance

import asyncio

system_threads = {}

command_state = {}

all_cartridges = {}

command_loops = {}

async def handle_commands(command_object, convoID, thread = 0, loadout = None):
    eZprint('handling command')
    print(command_object)
    if command_object:
        name = ''
        args = ''

        if 'name' in command_object:
            name = str(command_object['name'])

        else:
            for key, val in command_object.items():
                name = str(key)
        if 'args' in command_object:
            args = command_object['args']

    eZprint('parsing command')
    if convoID not in command_state:
        command_state[convoID] = {}

    if name == '':
        command_return = {"status": "Error", "name" : '', "message": "No command supplied"}
        return 



    if  name in 'list_files':
        response = await list_files(name, convoID)
        print('back at list parent function')
        print(response)
        return response
    
    # print('shouldnt be going past here')
    if 'continue' in name or 'next' in name :
        response = await continue_command(args, convoID, thread)
        return response
    
    if 'return' in name:
        response = await return_from_thread(args, convoID, thread)
        return response
    
    command_return = {"status": "", "name" : name, "message": ""}
    print( 'command name: ' + name + ' args: ' + str(args))

    all_text = ''
    if 'query' in name or name in 'query' or 'search' in name or name in 'search':
        # await get_cartridge_list(convoID)
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    if 'type' in val and val['type'] == 'index':
                        print('index query')
                        input = {
                            'cartKey' : key,
                            'convoID' : convoID,
                            'query' : str(args)
                        }
                        response = await handleIndexQuery(input, loadout)
                        response = str(response)

                        command_return['status'] = "Success."
                        command_return['message'] = "From " + args['filename']  + ": "+ response
                        print(command_return)
                        return command_return

                    if 'type' in val and val['type'] == 'summary':

                        if 'query' in args:
                            if 'blocks' in val:
                                if 'summaries' in val['blocks']:
                                    text_to_query = str(val['blocks']['summaries'])
                                    response = await quick_query(text_to_query, str(args['query']))
                                    response = str(response)
                            command_return['status'] = "Success."
                            command_return['message'] = "From " + filename  + ": "+ response
                            print(command_return)
                            return command_return
                    if 'type' in val and val['type'] == 'note':

                        if 'query' in args:
                            if 'text' in val:
                                response = await quick_query(val['text'], str(args['query']))
                            command_return['status'] = "Success."
                            command_return['message'] = "From " + filename  + ": "+ str(response)
                            print(command_return)
                            return command_return
                                
        print('all text query')
        print(all_text)
        response = await quick_query(all_text, str(args['query']))
        print(response)
        command_return['status'] = "Return."
        command_return['message'] = "File name not found, results from all text search : " + str(response)
        print(command_return)
        return command_return
       

    if 'create' in name or name in 'create':
        eZprint('create file')
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    payload = {
                    'cartKey' : key,
                    'convoID' : convoID,
                    'fields' : {
                        'text' : args['text'],
                    }
                    }
                    
                    update_cartridge_field(payload)
                    command_return['status'] = "Success."
                    command_return['message'] = "file '" +filename  + "' exists, so appending to file"
                    print(command_return)
                    return command_return
            
        
            cartVal = {
            'label' : filename,
            'text' : args['text'],
            'type' : 'note'
            }
            print(cartVal)
            await addCartridge(cartVal, convoID, current_loadout[convoID])
            command_return['status'] = "Success."
            command_return['message'] = "file " +filename  + " created"
            print(command_return)
            return command_return
        
    if 'write' in name or name in 'write':
        eZprint('writing file')
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    print('file exists so appending')
                    val['text'] += "\n"+args['text']
                    payload = {
                        'convoID': convoID,
                        'cartKey' : key,
                        'fields':
                                {'text': val['text']}
                                }
                    loadout = current_loadout[convoID]
                    await update_cartridge_field(payload,loadout, True)
                    command_return['status'] = "Success."
                    command_return['message'] = "file '" +filename  + "' exists, so appending to file"
                    print(command_return)
                    return command_return
                
                
            cartVal = {
            'label' : filename,
            'text' :args['text'],
            'type' : 'note',
            'enabled' : True,
            'minimised' : False,
            }

            print(cartVal)
            await addCartridge(cartVal, convoID, current_loadout[convoID])

            command_return['status'] = "Success."
            command_return['message'] = "file '" + filename  + "' written"
            print(command_return)
            return command_return
            
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'filename' missing"
        return command_return

    if 'append' in name or name in 'append':
        eZprint('appending file')
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    current_text = val['text']
                    current_text += '\n' + args['text']
                    val['text'] = current_text

                    payload = {
                        'convoID': convoID,
                        'cartKey' : key,
                        'fields':
                                {'text': val['text']}
                                }
                    loadout = current_loadout[convoID]
                    await update_cartridge_field(payload, loadout, True)                    
                    command_return['status'] = "Success."
                    command_return['message'] = "file " +args['filename']  + " appended."
                    print(command_return)
                    return command_return
            cartVal = {
            'label' : args['filename'],
            'text' :args['text'],
            'type' : 'note'
            }

            print(cartVal)
            await addCartridge(cartVal, convoID, current_loadout[convoID])
            command_return['status'] = "Success."
            command_return['message'] = "File " +args['filename']  + " not found, so new file created and text appended."
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'filename' missing"
        print(command_return)
        return command_return

    if name in 'preview' or 'preview' in name:
        eZprint('previewing file')
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    preview_string = val['label'] + '\n'
                    if 'blocks' in val:
                        for block in val['blocks']:
                            preview_string +=  str(block) + '\n'
                    if 'text' in val:
                        preview_string += val['text'] + '\n'

                    preview_string = preview_string[0:200]
                    preview_string += '\n'
                    command_return['status'] = "Success."
                    command_return['message'] = preview_string
                    print(command_return)
                    return command_return
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
            filename = args['filename']
            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    print('found match' + str(val))
            
                    return_string = ''
                    print('file found')
                    if 'enabled' not in val:
                        val['enabled'] = True
                    if val['enabled'] == False:
                        val['enabled'] = True
                        val['minimised'] = False
                        return_string += "File " + filename + " opened.\n"
                    else:
                        val['minimised'] = False
                        return_string += "File " + filename + " already open.\n"
                    
                    payload = {
                        'convoID': convoID,
                        'cartKey' : key,
                        'fields':
                                {'enabled': val['enabled']}
                                }
                    loadout = current_loadout[convoID]
                    await update_cartridge_field(payload, loadout, True)       
                    command_return['status'] = "Success."
                    command_return['message'] = return_string
                    print(command_return)
                    return command_return
            command_return['status'] = "Error."
            command_return['message'] = "File name not found.\n"
            print(command_return)
            return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            print(command_return)
            return command_return

                
    if name in 'close' or 'close' in name :
        eZprint('closing file')
        if 'filename' in args:
            filename = args['filename']
            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
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
                    loadout = current_loadout[convoID]
                    await update_cartridge_field(payload, loadout, True)       

                    command_return['status'] = "Success."
                    command_return['message'] = return_string
                    return command_return
            command_return['status'] = "Error."
            command_return['message'] = "File not found."
            return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            return command_return

    if name in 'delete' or 'delete' in name :
        eZprint('deleting file')
        if 'filename' in args:
            filename = args['filename']
            for key, val in available_cartridges[convoID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                print('distance: ' + str(string_match))
                print('filename: ' + filename)
                print('label: ' + str(val['label']))
                if string_match < 3:
                    val['softDelete'] = True
                    return_string += "File " + args['filename'] + " deleted.\n"

                    payload = {
                        'convoID': convoID,
                        'cartKey' : key,
                        'fields':
                                {'enabled': val['enabled']}
                                }
                    loadout = current_loadout[convoID]
                    await update_cartridge_field(payload, loadout, True)       
                    command_return['status'] = "Success."
                    command_return['message'] = return_string
                    return command_return
            command_return['status'] = "Error."
            command_return['message'] = "File not found."
            return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'filename' missing"
            return command_return

    if name == 'summarise_messages':
        eZprint('summarising conversation')
        if 'start-line' not in args:
            args['start-line'] = 0
        if 'end-line' not in args:
            args['end-line'] = 5

        summmarised = await summarise_from_range(convoID, args['start-line'], args['end-line'])
        if summmarised:
            command_return['status'] = "Success."
            command_return['message'] = "summary completed" 
            print(command_return)
        else:
            command_return['status'] = "error"
            command_return['message'] = "summary failed"
            print(command_return)
        return command_return
    
    # else :

    #     query = name + ' ' + str(args)
    #     await get_cartridge_list(convoID)
    #     for key, val in whole_cartridge_list[convoID].items():
    #         all_text += str(val)
    #         response = await quick_query(all_text, str(query))
    #         print(response)
    #         command_return['status'] = "Success."
    #         command_return['message'] = "Query not found, results from deep search" + str(response)
    #         print(command_return)
    #         return command_return
        


async def list_files(name, convoID, thread = 0):
    command_return = {"status": "", "name" : name, "message": ""}

    eZprint('list available files')
    string = '\nFiles available:\n'

    label = ''
    type = ''
    description = ''
    preview = ''
    state = ''
    string = ''
    # await ava(convoID)
    if convoID in available_cartridges:
        for key, val in available_cartridges[convoID].items():
            if 'type' in val and val['type'] == 'note' or val['type'] == 'index':
                if 'label' in val:
                    string += '\n -- ' + val['label']
                if 'type' in val:
                    string += ' -- '+val['type']
                if 'description' in val:
                    string +=  '\n' + val['description']
                if 'text' in val:
                    string += val['text'][0:20] + '...\n'
                if 'enabled' in val and val['enabled'] == True:
                    string += ' -- open'
                else:
                    string += ' -- closed'
                string += '\n'

    if string == '':
        string = 'no files available'
        command_return['status'] = "Success."
        command_return['message'] = string
        return command_return
    
    if len(string) > 1000:
        command_return = await large_document_loop(string, name, convoID, thread)
        return command_return

    string += '\nFiles available:\n' + string
    command_return['status'] = "Success."
    command_return['message'] = string
    print(command_return)
    return command_return

async def return_from_thread(args, convoID, thread):

    eZprint('returning from thread')    

    command_return = {"status": "", "message": ""}
    if 'message' in args:
        command_return['status'] = 'Return.'
        command_return['message'] = "thread closed with message" + args['message']
        return command_return



async def continue_command(convoID, thread, loop):
    eZprint('continuing command' + str(loop))
    if convoID in command_loops:
        if thread in command_loops[convoID]:
            command_return = large_document_loop(convoID, thread, loop)
            return command_return

async def large_document_loop(string, command = '', convoID= '', thread = 0):

    command_return = {"status": "", "name" : command, "message": ""}

    if convoID not in command_loops:
        command_loops[convoID] = {}
    if thread not in command_loops[convoID]:
        command_loops[convoID][thread] = {}
        command_loops[convoID][thread]['loop'] = 0

    loop = command_loops[convoID][thread]['loop']
    
    eZprint('large document loop' + str(loop) + ' ' + str(thread))

    if loop == 0:
        
        eZprint('loop 0')
        sections = []
        range = 1000
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
        
        message = "Files Available:\n Page " + str(loop) + " of " + str(len(sections)) + "\n" + sections[loop]  
        command_return['message'] = message + ongoing_return_string
        command_return['name'] = command
        print(command_return)
        return command_return
    
    else:
        eZprint('Loop complete as sections val is not last val')
        command_return['status'] = "Success."
        message = "List is complete, closing loop." 
        command_return['message'] = message
        print(command_return)
        return command_return



# ongoing_return_string = """\n Commands available: 'open' to add document to working memory, 'close' to remove, 'continue' to see next page, 'note' to take note or 'return' to return to main thread with message."""

ongoing_return_string = """\n Enter 'next' for next page, or 'return' for home."""

