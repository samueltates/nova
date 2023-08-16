
from keywords import get_summary_from_keyword, keywords_available
from debug import eZprint
from cartridges import addCartridge, update_cartridge_field, get_cartridge_list, whole_cartridge_list, add_existing_cartridge, search_cartridges
from sessionHandler import available_cartridges, current_loadout, novaConvo, novaSession
from cartridges import whole_cartridge_list
from memory import summarise_from_range, get_summary_children_by_key
from gptindex import handleIndexQuery, quick_query
from Levenshtein import distance
from file_handling.media_editor import split_video
from file_handling.url_scraper import advanced_scraper
import asyncio

system_threads = {}

command_state = {}

all_cartridges = {}

command_loops = {}

async def handle_commands(command_object, convoID, thread = 0, loadout = None):
    eZprint('handling command')
    sessionID = novaConvo[convoID]['sessionID']
    loadout = novaConvo[convoID]['loadout']
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
        return False
    
    if  name in 'list_files':
        response = await list_files(name, sessionID, loadout)
        print('back at list parent function')
        print(response)
        return response
    
    # print('shouldnt be going past here')
    if 'continue' in name or 'next' in name :
        response = await continue_command(convoID, thread)
        return response
    
    if 'return' in name:
        response = await return_from_thread(args, convoID, thread)
        return response
    
    command_return = {"status": "", "name" : name, "message": ""}
    print( 'command name: ' + name + ' args: ' + str(args))
    
    if 'search' in name or name in 'search':
        if args.get('query'):
            if args.get('type') == 'files':
                response = await search_files(name, args, sessionID, loadout, thread) 
                return response
            # elif args.get('type') == 'web':
            #     # response = await search_web(name, args, sessionID, loadout, thread)
            #     return response
            else:
                command_return['status'] = "Error."
                command_return['message'] = "type can't be blank"
                return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Query can't be blank"
            return command_return
        # if args.get('type') == 'web':

    if 'query' in name or name in 'query':
        response = await broad_query(name, args, sessionID, thread)
        print(response)
        return response
    
    if 'read' in name or name in 'read':
        for key, val in available_cartridges[sessionID].items():
            if 'label' in val:
                if val['label'] == args['filename']:
                    new_page = 0
                    text_to_read = ''
                    if val.get('text', None):
                        text_to_read = val['text']
                    else:
                        text_to_read = str(val)
                    if 'text' in val:
                        if 'page' not in args:
                            response = await read_text(name, val['label'], str(text_to_read), sessionID, thread,0)
                        if 'page' in args:
                            new_page = args['page']
                            response = await read_text(name, val['label'],  str(text_to_read), sessionID, thread, args['page'])
                        new_page = int(new_page + 1)

                        if 'status' in response:
                            if response['status'] == 'Success.':
                                new_page = 0

                        payload = {
                            'cartKey' : key,
                            'sessionID' : sessionID,
                            'fields' : {
                                'page' : new_page
                            }
                            }
                            
                        update_cartridge_field(payload)
                        return response

                    else:

                        command_return['status'] = "Error."
                        command_return['message'] = "Text empty."
                        print(command_return)
                        return command_return
                    
        command_return['status'] = "Error."
        command_return['message'] = "File not found."
        print(command_return)
        return command_return

    if name in 'open' or 'open' in name :
        response = await open_file(name, args, sessionID, loadout)
        print(response)
        return response
                
    if 'create' in name or name in 'create':
        eZprint('create file')
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[sessionID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                # print('distance: ' + str(string_match))
                # print('filename: ' + filename)
                # print('label: ' + str(val['label']))
                if string_match < 3:
                    payload = {
                    'cartKey' : key,
                    'sessionID' : sessionID,
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
            await addCartridge(cartVal, sessionID, current_loadout[sessionID])
            command_return['status'] = "Success."
            command_return['message'] = "file " +filename  + " created"
            print(command_return)
            return command_return
        
    if 'write' in name or name in 'write':
        eZprint('writing file')
        text = ''
        if 'text' in args:
            text = args['text']
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[sessionID].items():
                string_match = distance(filename, str(val['label']))
                # print('distance: ' + str(string_match))
                # print('filename: ' + filename)
                # print('label: ' + str(val['label']))
                if string_match < 3:
                    print('file exists so appending')
                    if 'text' in val:
                        val['text'] += "\n"+text
                    else:
                        val['text'] = text
                    payload = {
                        'sessionID': sessionID,
                        'cartKey' : key,
                        'fields':
                                {'text': val['text']}
                                }
                    loadout = current_loadout[sessionID]
                    await update_cartridge_field(payload,loadout, True)
                    command_return['status'] = "Success."
                    command_return['message'] = "file '" +filename  + "' exists, so appending to file"
                    print(command_return)
                    return command_return
                
            cartVal = {
            'label' : filename,
            'text' :text,
            'type' : 'note',
            'enabled' : True,
            'minimised' : False,
            }

            print(cartVal)
            await addCartridge(cartVal, sessionID, current_loadout[sessionID])

            command_return['status'] = "Success."
            command_return['message'] = "file '" + filename  + "' written"
            print(command_return)
            return command_return
            
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'filename' missing"
        return command_return

    if 'append' in name or name in 'append':
        eZprint('appending file')
        if 'text' in args:
            text = args['text']
        if 'filename' in args:
            filename = args['filename']


            for key, val in available_cartridges[sessionID].items():
                string_match = distance(filename, str(val['label']))
                if string_match < 3:
                    current_text = ''
                    if 'text' in val:
                        current_text = val['text']
                        current_text += '\n\n' + text
                    val['text'] = current_text

                    payload = {
                        'sessionID': sessionID,
                        'cartKey' : key,
                        'fields':
                                {'text': val['text']}
                                }
                    loadout = current_loadout[sessionID]
                    await update_cartridge_field(payload, loadout, True)                    
                    command_return['status'] = "Success."
                    command_return['message'] = "file " +args['filename']  + " appended."
                    print(command_return)
                    return command_return
            cartVal = {
            'label' : args['filename'],
            'text' : text,
            'type' : 'note',
            'enabled' : True,
            }

            # print(cartVal)
            await addCartridge(cartVal, sessionID, current_loadout[sessionID])
            command_return['status'] = "Success."
            command_return['message'] = "File " +args['filename']  + " not found, so new file created and text appended."
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'filename' missing"
        print(command_return)
        return command_return

    if name in 'preview' or 'preview' in name:
        eZprint('previewing file')
        all_text = ''
        if 'filename' in args:
            filename = args['filename']

            for key, val in available_cartridges[sessionID].items():
                all_text += str(val)
                string_match = distance(filename, str(val['label']))
                if string_match < 3:
                    preview_string = val['label'] + '\n'
                    if 'blocks' in val:
                        preview_string += str(val['blocks'] )+ '\n'
                        # if isinstance(val['blocks'], list):
                        #     for block in val['blocks']:
                        #         if isinstance(block, dict):
                        #             for key, val in block.items():
                        #                 preview_string += key + ': ' + str(val) + '\n'
                        #         else:
                        #             preview_string +=  str(block) + '\n'
                        # for block in val['blocks']:
                        #     preview_string +=  str(block) + '\n'
                    if 'text' in val:
                        preview_string += val['text'] + '\n'

                    preview_string = preview_string[0:500]
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
                

    if name in 'close' or 'close' in name :
        eZprint('closing file')
        if 'filename' in args:
            filename = args['filename']
            for key, val in available_cartridges[sessionID].items():
                # all_text += str(val)
                string_match = distance(filename, str(val['label']))
                if string_match < 3:
                    return_string = ''
                    if 'softDelete' not in val:
                        val['softDelete'] = True
                    if val['softDelete'] == False:
                        val['softDelete'] = True
                        return_string += "File " + args['filename'] + " closed.\n"
                    else:
                        return_string += "File " + args['filename'] + " already closed.\n"

                    payload = {
                        'sessionID': sessionID,
                        'cartKey' : key,
                        'fields':
                                {'softDelete': val['softDelete']}
                                }
                    loadout = current_loadout[sessionID]
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
            for key, val in available_cartridges[sessionID].items():
                string_match = distance(filename, str(val['label']))
                # print('distance: ' + str(string_match))
                # print('filename: ' + filename)
                # print('label: ' + str(val['label']))
                if string_match < 3:
                    val['softDelete'] = True
                    return_string += "File " + args['filename'] + " deleted.\n"

                    payload = {
                        'sessionID': sessionID,
                        'cartKey' : key,
                        'fields':
                                {'enabled': val['enabled']}
                                }
                    loadout = current_loadout[sessionID]
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
    
    if name == 'edit_video':
        video_file = args['video_file']
        extension = None
        for key, val in available_cartridges[sessionID].items():
            # if 'type' in val and val['type'] == 'media':
            if 'label' in val and val['label'] == video_file:
                print(val)
                video_file = val['key']
                # extension = val['extension']
                break
        edited_video = await split_video(args, video_file)
        print(edited_video)
        command_return['status'] = "Success."
        command_return['message'] = "video edited" 
        print(command_return)
        return command_return

    if name == 'scrape_website':
        website_url = args['website_url']
        scraped_data = await advanced_scraper(website_url)
        print('length is ' + str(len(str(scraped_data))))

        
        cartVal = {
        'label' : 'scrape of ' + website_url,
        'text' :str(scraped_data),
        'type' : 'note',
        'enabled' : True,
        'minimised' : False,
        }

        print(cartVal)
        await addCartridge(cartVal, sessionID, current_loadout[sessionID])
        command_return['status'] = "Success."
        command_return['message'] = "Website scrape saved as  : " + str(website_url)
        return command_return

        # if len(str(scraped_data)) > 2000:
        #     print('website larger than 2k starting large doc loop')
        #     command_return = await large_document_loop(website_url, str(scraped_data), name, sessionID, thread)
        #     return command_return
        # elif len(scraped_data) > 0:
        #     command_return['status'] = "Success."
        #     command_return['message'] = "Website scraped : " + str(scraped_data)
        #     # command_return['data'] = scraped_data
        #     return command_return
        # else:
        #     command_return['status'] = "Error."
        #     command_return['message'] = "Website scrape failed"
        #     return command_return


async def open_file(name, args, sessionID, loadout):
    command_return = {"status": "", "name" :name, "message": ""}
    eZprint('reading file')            
    if sessionID not in whole_cartridge_list:
        await get_cartridge_list(sessionID)
    if 'filename' in args:
        filename = args['filename']
        for cartKey, cartVal in whole_cartridge_list[sessionID].items():
            if 'label' in cartVal:
                string_match = distance(filename, str(cartVal['label']))
                # print('distance: ' + str(string_match))
                # print('filename: ' + filename)
                # print('label: ' + str(cartVal['label']))
                if string_match < 3:
                    print('found match' + str(cartVal))
            
                    return_string = ''
                    print('file found')
                    if cartVal.get('softDelete') == True:
                        return_string += "File " + filename + " opened.\n"
                    else:
                        return_string += "File " + filename + " already open.\n"

                    payload = {
                        'sessionID': sessionID,
                        'cartridge' : cartKey,
                        'fields':
                                {'enabled': True,
                                'minimised': False,
                                'softDelete': False,
                                }
                                }
                    loadout = current_loadout[sessionID]
                    await add_existing_cartridge(payload, loadout)       
                    command_return['status'] = "Success."
                    command_return['message'] = return_string
                    print(command_return)
                    return command_return
                
            # if cartVal['type'] == 'summary':
            #     print('checking summary')
            #     if 'blocks' in cartVal:
            #         if 'summaries' in cartVal['blocks']:
            #             for summary in cartVal['blocks']['summaries']:
            #                 for summaryKey, summaryVal in summary.items():
            #                     if 'title' in summaryVal:
            #                         # print('checking summary title' + str(summaryVal['title']))
            #                         similarity = distance(filename, summaryVal['title'])
            #                         if similarity < 3:
            #                             # print('found match' + str(summaryVal))  
            #                             children = await get_summary_children_by_key(summaryKey, sessionID, cartKey, loadout)
            #                             if children:
            #                                 for child in children:
            #                                     # print('child' + str(child))
            #                                     cartVal['blocks']['summaries'].append(child)

            #                                 input = {
            #                                     'sessionID': sessionID,
            #                                     'cartKey' : cartKey,
            #                                     'fields':
            #                                             {'blocks': cartVal['blocks']},
            #                                             'loadout': loadout
            #                                             }                                        
            #                                 update_cartridge_field(input, loadout, True)
            #                                 return_string = "File " + filename + " opened.\n"
            #                                 command_return['status'] = "Success."
            #                                 command_return['message'] = return_string
            #                                 print(command_return)
            #                                 return command_return
        command_return['status'] = "Error."
        command_return['message'] = "File not found.\n"
        print(command_return)
        return command_return
    else:
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'filename' missing"
        print(command_return)
        return command_return


async def broad_query(name, args, sessionID, loadout):
         # await get_cartridge_list(convoID)
    all_text = ''
    command_return = {"status": "", "name" :name, "message": ""}
    if 'query' not in args or args['query']=='':
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'query' missing"
        return command_return

    if 'filename' in args:
        filename = args['filename']

        for cartKey, cartVal in available_cartridges[sessionID].items():
            all_text += str(cartVal)
            string_match = distance(filename, str(cartVal['label']))
            # print('distance: ' + str(string_match))
            # print('filename: ' + filename)
            # print('label: ' + str(cartVal['label']))
            if string_match < 3:
                print('found match' + str(cartVal['label']))
                if 'type' in cartVal and cartVal['type'] == 'index':
                    print('index query')
                    if 'query' in args:

                        input = {
                            'cartKey' : cartKey,
                            'sessionID' : sessionID,
                            'query' : str(args['query'])
                        }

                        response = await handleIndexQuery(input, loadout)
                        response = str(response)

                        command_return['status'] = "Success."
                        command_return['message'] = "From " + args['filename']  + ": "+ response
                        print(command_return)
                        return command_return
                    
                    else:
                        command_return['status'] = "Error."
                        command_return['message'] = "Arg 'query' missing"
                        return command_return

                if 'type' in cartVal and cartVal['type'] == 'summary':
                    if 'query' in args:
                        if 'blocks' in cartVal:
                            if 'summaries' in cartVal['blocks']:
                                query_response = await traverse_blocks(args['query'], cartVal['blocks'], sessionID,cartKey, loadout)
                                command_return['status'] = "Success."
                                command_return['message'] = "From " + filename  + ": "+ str(query_response)
                                print(command_return)
                                return command_return
                            
                if 'type' in cartVal and cartVal['type'] == 'note':

                    if 'query' in args:
                        if 'text' in cartVal:
                            query_response = await quick_query(cartVal['text'], str(args['query']))
                            command_return['status'] = "Success."
                            command_return['message'] = "From " + filename  + ": "+ str(query_response)
                            print(command_return)
                            return command_return
                    
        for cartKey, cartVal in available_cartridges[sessionID].items():
            if 'type' in cartVal and cartVal['type'] == 'summary':
                # print('searching summary for pointer')
                if 'blocks' in cartVal:
                    if 'summaries' in cartVal['blocks']:
                        for summaries in cartVal['blocks']['summaries']:
                            for summaryKey, summaryVal in summaries.items():
                                if 'title' in summaryVal:
                                    similarity = distance(filename, summaryVal['title'])
                                    # print('distance: ' + str(similarity))
                                    # print('filename: ' + filename)
                                    # print('label: ' + str(summaryVal['title']))
                                    if similarity <3:
                                        # print('found match' + str(summaryVal))
                                        if 'query' in args:
                                            query_response = await traverse_blocks(args['query'], cartVal['blocks'], sessionID,cartKey, loadout)
                                            command_return['status'] = "Success."
                                            command_return['message'] = "From " + filename  + ": "+ str(query_response)
                                            print(command_return)
                                            return command_return
                                    

    print('all text query')
    query = ''
    if 'query' in args:
        # query = args['query']
        # query_response = await quick_query(all_text, str(query))
        command_return['status'] = "Return."
        command_return['message'] = "File not found, please use exact filename"
        return command_return


async def traverse_blocks(query, blocks, sessionID, cartKey, loadout):
    text_to_query = ''
    to_open = ''
    closest = 0
    text_to_query += "\nSummaries: \n" 
    if 'summaries' in blocks:
        for summary in blocks['summaries']:   
            for summaryKey, summaryVal in summary.items():
                if 'title' in summaryVal:
                    text_to_query += summaryVal['title'] + ": "
                if 'body' in summaryVal:
                    text_to_query += summaryVal['body'] + "\n"
            # print('text to query: ' + text_to_query)
                    
            similarity = distance(str(query), str(summary))
            # print('checking for matches ' + str(query) + ' ' + str(summary) + ' ' + str(similarity))
            if similarity > closest:
                # print('found closer match')
                closest = similarity
                to_open = summaryKey
        if to_open:
            # print('opening ' + str(to_open))
            children = await get_summary_children_by_key(to_open, sessionID, cartKey, loadout)
            if children:
                for child in children:
                    # print('child' + str(child))
                    text_to_query += "\n Source: " + str(child['source']) + "\n"
                    if 'title' in child:
                        text_to_query += child['title'] + ": "
                    if 'body' in child:
                        text_to_query += child['body'] + "\n"
                    else:
                        text_to_query += str(child) + "\n"
                    text_to_query += "\n"
                    if child not in blocks['summaries']:
                        # print('optimistically adding child')
                        blocks['summaries'].append(child)
                        input = {
                            'cartKey' : cartKey,
                            'sessionID' : sessionID,
                            'blocks' : blocks
                        }
                        update_cartridge_field(input, loadout)
    # if 'insights' in blocks:
    #     print('insights')
    #     text_to_query += "Insights: \n"
    #     closest = 0
    #     to_open = ''
    #     candidate_text = ''
    #     print('insights: ' + str(blocks['insights']))
    #     for key,val in blocks['insights'].items():
    #         print('key: ' + str(key) + ' val: ' + str(val))
    #         for element in val:
    #             candidate_text = str(key) + " - " + str(element['line']) + "\n"
    #             print(element)
    #             similarity = distance(str(query), str(candidate_text))
    #             if similarity > closest:
    #                 closest = similarity
    #                 to_open = element['key']
    #             print('current text to query: ' + text_to_query)
    #             text_to_query += candidate_text
    #             # print('source to check is ' + str(element['source']))
    #     if to_open:
    #         print('opening ' + str(to_open))
    #         children = await get_summary_children_by_key(to_open, convoID, cartKey, loadout)
    #         if children:
    #             for child in children:
    #                 if 'title' in child:
    #                     text_to_query += child['title'] + ": "
    #                 if 'body' in child:
    #                     text_to_query += child['body'] + "\n\n"
    #                 else:
    #                     text_to_query += str(child) + "\n"
    #     print('text to query: ' + text_to_query)
    if 'keywords' in blocks:
        closest = 0
        to_open = ''
        for key, val in blocks['keywords'].items():
            similarity = distance(str(query), str(key))
            # print('checking for matches ' + str(query) + ' ' + str(key) + ' ' + str(similarity))
            if similarity > closest:
                closest = similarity
                for element in val:
                    to_open = element['source']

        if to_open:
            children = await get_summary_children_by_key(to_open, sessionID, key, loadout)
            if children:
                for child in children:
                    if 'title' in child:
                        text_to_query += child['title'] + ": "
                    if 'body' in child:
                        text_to_query += child['body'] + "\n"
                    else:
                        text_to_query += str(child) + "\n"
        # print('text to query: ' + text_to_query)
        response = await quick_query(text_to_query, str(query))
        response = str(response)
        print(response)
        return response

async def read_text(name, text_title, text_body, sessionID, thread = 0, page = 0):
    command_return = {"status": "", "name" :name, "message": ""}
    if text_body == '':
        command_return['status'] = "Error."
        command_return['message'] = "No text supplied"
        return command_return
    
    if len(text_body) > 2000:
        command_return = await large_document_loop(text_title, text_body, name, sessionID, thread, page)
        return command_return
    
    else:
        command_return['status'] = "Success."
        command_return['message'] = text_title + '\n' + text_body
        return command_return



async def list_files(name, sessionID, loadout, thread = 0):
    command_return = {"status": "", "name" : name, "message": ""}

    eZprint('list available files')
    string = '\nOpen files:\n'

    label = ''
    type = ''
    description = ''
    preview = ''
    state = ''
    # string = ''
    # await ava(convoID)
    if sessionID in available_cartridges:
        for key, val in available_cartridges[sessionID].items():
            if 'type' in val and val['type'] == 'note' or val['type'] == 'index' or val['type'] == 'summary':
                if val.get('label', None):
                    print(val['label'])
                    string += '\n-' + val['label']
                if val.get('lastUpdated', None):
                    string += ' | Last updated : ' + val['lastUpdated']
                if val.get('summary', None):
                    string += ' | Summary: ' + val['summary']
                if val.get('text', None):
                    string += val['text'][0:280] + '...\n'
    scope = None
    if sessionID in novaSession and 'convoID' in novaSession[sessionID]:
        convoID = novaSession[sessionID]['convoID'] 
    if convoID in novaConvo and 'scope' in novaConvo[convoID]:
        scope = novaConvo[convoID]['scope']

    if sessionID not in whole_cartridge_list:
        await get_cartridge_list(sessionID)
    string += '[Open file commands: Read, Write, Append, Query or Close.]'

    if sessionID in whole_cartridge_list and len(whole_cartridge_list[sessionID])>0:
        string += '\nClosed files:\n'
        for key, val in whole_cartridge_list[sessionID].items():    
            if key not in available_cartridges[sessionID]:
                if scope == 'global' or loadout == None or 'initial-loadout' in val and val['initial-loadout'] == loadout:
                    if val.get('label', None):
                        print(val['label'])
                        string += '\n-' + val['label']
                    if val.get('lastUpdated', None):
                        string += ' | Last updated : ' + val['lastUpdated']
                    if val.get('summary', None):
                        string += ' | Summary: ' + val['summary']
                    if val.get('text', None):
                        string += val['text'][0:280] + '...\n'
        string += '[Closed file commands: Open, Read, Query or Delete.]'

    if string == '':
        string = 'no files available'
        command_return['status'] = "Success."
        command_return['message'] = string
        return command_return
    
    if len(string) > 2000:
        command_return = await large_document_loop("Files available", string, name, sessionID, thread)
        return command_return

    string = '\nFile List:\n' + string
    command_return['status'] = "Success."
    command_return['message'] = string
    print(command_return)
    return command_return

async def search_files(name, args, sessionID, loadout, thread = 0):
    command_return = {"status": "", "name" : name, "message": ""}

    query = args.get('query', '')
    results = await search_cartridges(query, sessionID)

    scope = None
    if sessionID in novaSession and 'convoID' in novaSession[sessionID]:
        convoID = novaSession[sessionID]['convoID'] 
    if convoID in novaConvo and 'scope' in novaConvo[convoID]:
        scope = novaConvo[convoID]['scope']

    search_response = ''
    for cartridge in results:
        # for key, val in cartridge.items():
        if scope == 'global' or loadout == None or 'initial-loadout' in cartridge and cartridge['initial-loadout'] == loadout:
            if cartridge.get('label', None):
                print(cartridge['label'])
                search_response += '\n-' + cartridge['label']
            if cartridge.get('lastUpdated', None):
                search_response += ' | Last updated : ' + cartridge['lastUpdated']
            if cartridge.get('softDelete', None):
                search_response += ' | Closed\n'
            else:
                search_response += ' | Open\n'
            if cartridge.get('summary', None):
                search_response += ' | Summary: ' + cartridge['summary']
            if cartridge.get('text', None):
                search_response += ' | ' + cartridge['text'][0:280] + '...\n'
            # if 'blocks' in val:
            #     if 'summaries' in val['blocks']:
            #         for summary in val['blocks']['summaries']:
            #             for summaryKey, summaryVal in summary.items():
            #                 if 'title' in summaryVal:
            #                     search_response += "\n-"+summaryVal['title'] 

    if search_response == '':
        search_response = 'no files available'
        command_return['status'] = "Success."
        command_return['message'] = search_response
        return command_return
    
    if len(search_response) > 2000:
        command_return = await large_document_loop("Search results", search_response, name, sessionID, thread)
        return command_return
    
    else:
        search_response = '\nSearch results:\n' + search_response
        command_return['status'] = "Success."
        command_return['message'] = search_response
        return command_return     


async def return_from_thread(args):

    eZprint('returning from thread')    

    command_return = {"status": "", "message": ""}
    if 'message' in args:
        command_return['status'] = 'Return.'
        command_return['message'] = "thread closed with message" + args['message']
        return command_return



async def continue_command(convoID, thread):
    # eZprint('continuing command' + str(loop))
    if convoID in command_loops:
        if thread in command_loops[convoID]:
            command_return = large_document_loop('','','',convoID, thread)
            return command_return

async def large_document_loop(title, string, command = '', convoID= '', thread = 0, page = -1):

    command_return = {"status": "", "name" : command, "message": ""}

    if convoID not in command_loops:
        command_loops[convoID] = {}
    if thread not in command_loops[convoID]:
        command_loops[convoID][thread] = {}
    if command not in command_loops[convoID][thread]:
        command_loops[convoID][thread][command] = {}
        command_loops[convoID][thread][command]['loop'] = 0

    loop = command_loops[convoID][thread][command]['loop']

    if page != -1:
        loop = page
    
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
        command_loops[convoID][thread][command]['sections'] = sections

    else:
        eZprint('loop not 0 sections retrieved')

        sections = command_loops[convoID][thread][command]['sections']

    sections = command_loops[convoID][thread][command]['sections']
    command_loops[convoID][thread][command]['loop'] += 1
    # print(sections)
    # print(len(sections))
    # print(loop)
    if loop < len(sections):
        eZprint('returning sections based on loop')
        command_return['status'] = 'in-progress'
        
        message = title + ":\n\n Page " + str(loop) + " of " + str(len(sections)) + "\n\n" + str(sections[loop])
        command_return['message'] = message + "\n\nUse " + command + " for next page."""
        command_return['name'] = command
        print(command_return)
        return command_return
    
    else:
        eZprint('Loop complete as sections val is not last val')
        command_return['status'] = "Success."
        message = title + " is complete." 
        command_return['message'] = message
        print(command_return)
        return command_return


