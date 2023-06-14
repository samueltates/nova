
from keywords import get_summary_from_keyword, keywords_available
from debug import eZprint
from cartridges import addCartridge, updateCartridgeField
from sessionHandler import availableCartridges
from memory import summarise_from_range
# from nova import handleIndexQuery
import asyncio

system_threads = {}

async def handle_commands(command_object, convoID):
    eZprint('handling command')
    print(command_object)
    if command_object:
        if 'name' and 'args' in command_object:
            command_response = await parse_command(command_object['name'], command_object['args'], convoID)
            return command_response
    else:
        eZprint('no command found')
        return

async def parse_command(name, args, convoID):
    eZprint('parsing command')
    command_return = {"status": "", "name" : name, "message": ""}
    if name == 'summarise_conversation':
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
    if name == 'create_note':
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

    if name == 'list_documents':
        eZprint('listing notes')
        string = '\nDocuments available:'
        for key, val in availableCartridges[convoID].items():
            if val['type'] == 'index':
                if val['enabled'] == True:
                    string += '\n' + val['label']+"\n"
        command_return['status'] = 'success'
        command_return['message'] = string
        print(command_return)
        return command_return
                
    
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

# command_name\n\nCommands:\n1. create_note: Create Note, args: "label": "<label_string>", "body": "<body_string>"\n2. append_note: Append Note, args: "label": "<filename>", "line" : <new_line> <\n4. list_notes: List available notes, args: "type": "<resource type>"\n6. open_note: Open a note, args: "label": "<labelname>"\n7. list_documents: List document embeddings, args: "document": "<filename>", "text": "<text>"\n7. query_document: Query document embedding, args: "document": "<filename>", "text": "<text>"
# """





  

"""\nCommands:\n1. add_note: Creates new note for later reference, args: "title" : <title>, "body" : <body>\n2. list_notes: shows available notes, args: "note": "<note title>"\n3. append_to_note: Append note with new line, args: "note": "<note title>, "new line":<new line>"""