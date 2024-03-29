
from Levenshtein import distance
import asyncio
import json

from session.sessionHandler import active_cartridges, current_loadout, novaConvo, novaSession, system_threads, command_loops, command_state
from core.cartridges import addCartridge, update_cartridge_field, get_cartridge_list, whole_cartridge_list, add_existing_cartridge, search_cartridges
from core.cartridges import whole_cartridge_list
from web_handling.google_search import google_api_search
from web_handling.url_scraper import advanced_scraper
from file_handling.media_editor import split_video,overlay_video,overlay_b_roll
from file_handling.transcribe import transcribe_file
from file_handling.image_handling import generate_image, generate_images
from file_handling.video_editor import cut_video
from file_handling.text_handler import large_document_loop, parse_text_to_json, create_json_doc, update_json_doc
from tools.memory import summarise_from_range, get_summary_children_by_key
from tools.gptindex import handleIndexQuery, quick_query, QuickUrlQuery
from tools.debug import eZprint, eZprint_anything
from index.handle_llama_index import handle_query

DEBUG_KEYS = ['COMMANDS']

async def handle_commands(command_object, convoID, thread = 0, loadout = None):
    # eZprint('handling command')
    sessionID = novaConvo[convoID]['sessionID']
    # loadout = novaConvo[convoID]['loadout']
    splitID = convoID.split('-')
    loadout = None
    if len(splitID) > 1:
        loadout = splitID[2]

    print(command_object)
    if command_object:
        name = ''
        args = ''

        if 'name' in command_object:
            name = str(command_object['name'])

        else:

            name = command_object.name
            args = json.loads(command_object.arguments, strict=False)

        if isinstance(command_object, dict): 
            if command_object.get('args'):
                args = command_object['args']
            if command_object.get('arguments'):
                args = json.loads(command_object['arguments'], strict=False)

    eZprint('parsing command')
    if convoID not in command_state:
        command_state[convoID] = {}

    if name == '':
        command_return = {"status": "Error", "name" : '', "message": "No command supplied"}
        return False
    
    command_return = {"status": "", "name" : name, "message": ""}
    print( 'command name: ' + name + ' args: ' + str(args))


    if name == 'read':
        for key, val in active_cartridges[convoID].items():
            eZprint(val['label'], ['COMMANDS', 'READ'])
            if val.get('label', '').lower() == args['filename'].lower():
                new_page = 0
                page = args.get('page', None)
                text_to_read = val.get('text', '')
                elements = val.get('elements', None)

                response = await read_text(name, val['label'], text_to_read, convoID, thread, page, elements)
        
                new_page = int(new_page) + 1
                
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
 
                await update_cartridge_field(payload, convoID)
                return response           
        # await asyncio.sleep(0.001)
        command_return['status'] = "Error."
        command_return['message'] = "File not found."
        return command_return
    
    if name == 'write' or name == 'append':
        WRITE_DEBUG_KEYS = DEBUG_KEYS + ['WRITE']
        new_text = args.get('text', '')
        filename = args.get('filename', '')
        eZprint('writing file ' + filename + ' with content ' + new_text, WRITE_DEBUG_KEYS)

        for key, val in active_cartridges[convoID].items():
            string_match = distance(filename, str(val['label']))
            if string_match < 3:

                eZprint('found file '+ val.get('label','') + ' to write to', WRITE_DEBUG_KEYS)
                current_text = val.get('text', None)
                eZprint_anything(current_text, WRITE_DEBUG_KEYS, message = 'current text')


                # TODO : can probably compress this all so less calls
                if current_text is None:
                    eZprint('no curent text starting new doc', WRITE_DEBUG_KEYS)
                    json_object = create_json_doc(new_text, WRITE_DEBUG_KEYS)
                
                if current_text:
                    if isinstance(current_text, dict):
                        eZprint('current text is object', WRITE_DEBUG_KEYS)
                        json_object = update_json_doc(new_text, current_text, WRITE_DEBUG_KEYS)
                    elif isinstance(current_text, str):
                        eZprint('current text is string', WRITE_DEBUG_KEYS)
                        new_text = current_text + new_text
                        eZprint_anything(new_text, WRITE_DEBUG_KEYS, message='text to transform')
                        json_object = create_json_doc(new_text, WRITE_DEBUG_KEYS)

                eZprint_anything(json_object, WRITE_DEBUG_KEYS, message = 'final object to write')
                
                payload = {
                    'sessionID': sessionID,
                    'cartKey' : key,
                    'fields':
                            {'text': json_object}
                            }
                
                await update_cartridge_field(payload, convoID, loadout, True)
                command_return['status'] = "Success."
                command_return['message'] = "file '" +filename  + "' exists, so appending to file"
                print(command_return)
                return command_return
            
        eZprint_anything(new_text, WRITE_DEBUG_KEYS,message = 'no existing file found, creating new')
        # json_object = parse_text_to_json(new_text)
        json_object = create_json_doc(new_text, WRITE_DEBUG_KEYS)

        eZprint_anything(json_object, WRITE_DEBUG_KEYS, message = 'final object to write')

        cartVal = {
        'label' : filename,
        'text' :json_object,
        'type' : 'note',
        'enabled' : True,
        'minimised' : False,
        }

        await addCartridge(cartVal, sessionID, loadout, convoID, True)

        command_return['status'] = "Success."
        command_return['message'] = "file '" + filename  + "' written"
        # print(command_return)
        return command_return
    
             
    # if 'append' in name or name in 'append':
    #     eZprint('appending file')
    #     if 'text' in args:
    #         text = args['text']
    #     if 'filename' in args:
    #         filename = args['filename']


    #         for key, val in active_cartridges[convoID].items():
    #             string_match = distance(filename, str(val['label']))
    #             if string_match < 3:
    #                 current_text = ''
    #                 if 'text' in val:
    #                     current_text = val['text']
    #                     current_text += '\n\n' + text
    #                 val['text'] = current_text

    #                 payload = {
    #                     'sessionID': sessionID,
    #                     'cartKey' : key,
    #                     'fields':
    #                             {'text': val['text']}
    #                             }
    #                 loadout = current_loadout[sessionID]
    #                 await update_cartridge_field(payload, convoID, loadout, True)                    
    #                 command_return['status'] = "Success."
    #                 command_return['message'] = "file " +args['filename']  + " appended."
    #                 print(command_return)
    #                 return command_return
    #         cartVal = {
    #         'label' : args['filename'],
    #         'text' : text,
    #         'type' : 'note',
    #         'enabled' : True,
    #         }

    #         # print(cartVal)
    #         await addCartridge(cartVal, sessionID, loadout, convoID, True)
    #         command_return['status'] = "Success."
    #         command_return['message'] = "File " +args['filename']  + " not found, so new file created and text appended."
    #         return command_return
        
    #     command_return['status'] = "Error."
    #     command_return['message'] = "Arg 'filename' missing"
    #     print(command_return)
    #     return command_return
        
    if name == 'query':

        QUERY_KEYS = DEBUG_KEYS + ['QUERY']
        eZprint('querying file', QUERY_KEYS)

        if 'query' not in args or args['query']=='':
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'query' missing"
            return command_return

        if 'filename' in args:
            filename = args['filename']

            for cartKey, cartVal in active_cartridges[convoID].items():
                string_match = distance(filename, str(cartVal['label']))

                if string_match < 2:
                    eZprint('found match' + str(cartVal['label']), QUERY_KEYS)

                    if 'query' in args:

                        query = str(args['query'])
                        response = await handle_query(cartVal, query, sessionID, convoID, loadout)
                        response = str(response)

                        command_return['status'] = "Success."
                        command_return['message'] = query + ": from " + args['filename']  + ": "+ response
                        print(command_return)
                        return command_return
                    
                    else:
                        command_return['status'] = "Error."
                        command_return['message'] = "Arg 'query' missing"
                        return command_return

    if name == 'search_files':
        if args.get('query'):
            # if args.get('type') == 'files':
            response = await search_files(name, args, sessionID, loadout, thread) 
            return response
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Query can't be blank"
            return command_return
            # elif args.get('type') == 'web':
            #     # response = await search_web(name, args, sessionID, loadout, thread)
            #     return response
    if  name in 'list_files':
        response = await list_files(name, sessionID, loadout, convoID)
        return response
    
    # print('shouldnt be going past here')
    if 'continue' in name or 'next' in name :
        response = await continue_command(convoID, thread)
        return response
    
    if 'return' in name:
        response = await return_from_thread(args, convoID, thread)
        return response
    
    if name.lower() == 'none':
        return 




    if 'search_web' in name or name in 'search_web':
            # elif args.get('type') == 'web':
            if args.get('query'):
                # Call the Google API Search function
                searchResults = google_api_search(args.get('query'))
                results = []
                for result in searchResults:
                    results.append({'title': result['title'], 'snippet': result ['snippet'], 'link': result['link']})
                # Return results
                command_return['status'] = 'Success.'
                command_return['message'] = 'Google web search completed. Results : ' + str(results)
                # command_return['data'] = searchResults
                return command_return
            else:
                command_return['status'] = "Error."
                command_return['message'] = "Query can't be blank"
                return command_return
     
    if name == 'query_website':
        if args.get('website_url'):
            website_url = args['website_url']
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'website_url' missing"
            return command_return
        if args.get('query'):
            # if args.get('type') == 'files':
            query = args['query']
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Query can't be blank"
            return command_return
        
        response = await QuickUrlQuery(website_url, query)
        # scraped_data = await advanced_scraper(website_url)
        # response = await quick_query(scraped_data, query)
        command_return['status'] = "Success."
        command_return['message'] = "Response : " + str(response)
        return command_return



    if name == 'open':
        response = await open_file(name, args, sessionID, convoID, loadout)
        eZprint(response, DEBUG_KEYS.append( 'OPEN_FILE'), message = 'response from opening')
        return response
       

    # if name in 'preview' or 'preview' in name:
    #     eZprint('previewing file')
    #     all_text = ''
    #     if 'filename' in args:
    #         filename = args['filename']

    #         for key, val in active_cartridges[convoID].items():
    #             all_text += str(val)
    #             string_match = distance(filename, str(val['label']))
    #             if string_match < 3:
    #                 preview_string = val['label'] + '\n'
    #                 if 'blocks' in val:
    #                     preview_string += str(val['blocks'] )+ '\n'
    #                     # if isinstance(val['blocks'], list):
    #                     #     for block in val['blocks']:
    #                     #         if isinstance(block, dict):
    #                     #             for key, val in block.items():
    #                     #                 preview_string += key + ': ' + str(val) + '\n'
    #                     #         else:
    #                     #             preview_string +=  str(block) + '\n'
    #                     # for block in val['blocks']:
    #                     #     preview_string +=  str(block) + '\n'
    #                 if 'text' in val:
    #                     preview_string += val['text'] + '\n'

    #                 preview_string = preview_string[0:500]
    #                 preview_string += '\n'
    #                 command_return['status'] = "Success."
    #                 command_return['message'] = preview_string
    #                 print(command_return)
    #                 return command_return
    #         command_return['status'] = "Error."
    #         command_return['message'] = "File not found."
    #         print(command_return)
    #         return command_return
    #     else:
    #         command_return['status'] = "Error."
    #         command_return['message'] = "Arg 'filename' missing"
    #         print(command_return)
    #         return command_return
                

    if name == 'close':
        eZprint('closing file')
        if 'filename' in args:
            filename = args['filename']
            for key, val in active_cartridges[convoID].items():
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
                    await update_cartridge_field(payload, convoID, loadout, True)       

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

    if name == 'delete':
        eZprint('deleting file')
        if 'filename' in args:
            filename = args['filename']
            for key, val in active_cartridges[convoID].items():
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
                    await update_cartridge_field(payload, convoID, loadout, True)       
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
    
    if name == 'generate_image':
        if 'prompt' in args:
            prompt = args['prompt']
            response = await generate_image(prompt, sessionID, convoID, loadout)
            command_return['status'] = "Success."
            command_return['message'] = "Image " + response + " generated."
            return command_return
        
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'prompt' missing"
            return command_return
        
    if name == 'generate_images':
        if 'prompts' in args:
            prompts = args['prompts']
            response = await generate_images(prompts, sessionID, convoID,loadout)
            command_return['status'] = "Success."
            command_return['message'] = "Images generated. "
            return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "Arg 'prompts' missing"
            return command_return
        
    if name == 'overlay_b_roll':
        main_video_cartridge = None
        if args.get('main_video'):
            main_video = args['main_video']
            for key, val in active_cartridges[convoID].items():
                if 'label' in val and val['label'] == main_video:
                    main_video_cartridge = val
                    main_video_cartridge.update({'key' : key})
                    print(main_video_cartridge)
                    break
        if args.get('b_roll'):
            b_roll_to_overlay = args['b_roll']

        overlay_video_name = await overlay_b_roll(main_video_cartridge, b_roll_to_overlay, sessionID, convoID, loadout)
        if overlay_video_name:
            command_return['status'] = "Success."
            command_return['message'] = "video overlayed and saved as " + str(overlay_video_name)
            return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "video overlay failed"
            return command_return


    if 'overlay_video' in name:
        main_video_key = None
        main_video_cartridge = None
        text_to_overlay = None
        media_to_overlay = None
        media_to_overlay_keys = []
        if args.get('main_video'):
            main_video = args['main_video']
            for key, val in active_cartridges[convoID].items():
                if 'label' in val and val['label'] == main_video:
                    main_video_cartridge = val
                    main_video_cartridge.update({'key' : key})
                    print(main_video_cartridge)
                    break
        if args.get('media_to_overlay'):
            media_to_overlay = args['media_to_overlay']
            for media in media_to_overlay:
                print(media)
                if media.get('file_name'):
                    print('file name found')
                    for key, val in active_cartridges[convoID].items():
                        if 'label' in val and val['label'] == media.get('file_name'):
                            media.update({'aws_key' : key})
                            break
        if args.get('text_to_overlay'):
            text_to_overlay = args['text_to_overlay']
        print(media_to_overlay)

        overlay_video_name = await overlay_video(main_video_cartridge, media_to_overlay,text_to_overlay, sessionID, convoID, loadout) 
        if overlay_video_name:
            command_return['status'] = "Success."
            command_return['message'] = "video overlayed and saved as " + str(overlay_video_name)
            return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "video overlay failed"
            return command_return
        

    if name == 'edit_video':
        video_file = args['video_file']
        extension = None
        for key, val in active_cartridges[convoID].items():
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

    # if name == 'read_website':

    if name == 'cut_video':
        video_file = args['target_video']
        extension = None
        for key, val in active_cartridges[convoID].items():
            # if 'type' in val and val['type'] == 'media':
            if 'label' in val and val['label'] == video_file:
                eZprint_anything(val, ['COMMANDS', 'VIDEO'], message='found target' )
                video_file = val['key']
                # extension = val['extension']
                break
        edited_video = await cut_video(video_file,args, sessionID, convoID, loadout )
        eZprint_anything(edited_video)
        command_return['status'] = "Success."
        command_return['message'] = "video edited" 
        print(command_return)
        return command_return
    

    if name == 'transcribe':
        video_file_name = args['filename']
        video_file = None
        extension = None
        for key, val in active_cartridges[convoID].items():
            # if 'type' in val and val['type'] == 'media':
            if 'label' in val and val['label'] == video_file_name:
                eZprint(val, ['COMMANDS', 'TRANSCRIBE'])
                video_file = val['aws_key']
                extension = val['extension']
                break

        if video_file:
            transcript = await transcribe_file(None, video_file, video_file_name, extension, sessionID, convoID,  loadout)

            if transcript:
                command_return['status'] = "Success."
                command_return['message'] = "video transcript:\n" + str(transcript)
                eZprint_anything(command_return, ['COMMANDS', 'TRANSCRIBE'], message = 'transcript return')
                return command_return
            else:
                command_return['status'] = "Error."
                command_return['message'] = "video transcript failed"
                eZprint_anything(command_return, ['COMMANDS', 'TRANSCRIBE'], message = 'transcript return')
                return command_return
        else:
            command_return['status'] = "Error."
            command_return['message'] = "video not found"
            eZprint(command_return)
            return command_return

        

    if name == 'scrape_website':
        website_url = args['website_url']
        scraped_data = await advanced_scraper(website_url)
        # print('length is ' + str(len(str(scraped_data))))
        output = ''
        print(scraped_data)
        # for element in scraped_data:
        #     if 'image_alt_text' in element and 'image_src' in element:
        #         output += '!['+ element['image_alt_text'] +']('+ element['image_src'] +')\n'
        #     if 'url' in element and 'link_text' in element:
        #         output += '['+ element['link_text'] + '](' + element['url'] + ')\n'
        #     elif 'text' in element:
        #         output += element['text'] + '\n'
        
        print(output)
        cartVal = {
        'label' : 'scrape of ' + website_url,
        'text' :str(scraped_data),
        'type' : 'note',
        'enabled' : True,
        'minimised' : False,
        }

        # print(cartVal)
        await addCartridge(cartVal, sessionID, loadout, convoID, True)
        command_return['status'] = "Success."
        command_return['message'] = "Website scrape saved as  : 'scrape of ' + " + str(website_url)
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
    # else:
    #     command_return['status'] = "Error."
    #     command_return['message'] = "Command not recognised"
    #     return command_return


async def read_text(name, text_title, text_body, convoID, thread = 0, page = None, elements = None):

    command_return = {"status": "", "name" :name, "message": ""}

    eZprint('text larger than 2k starting large doc loop ' + str(len(text_body)), ['COMMANDS', 'READ'])
    command_return = await large_document_loop(text_title, text_body, name, convoID, thread, page, elements = elements, break_into_sections= True)
    return command_return


async def open_file(name, args, sessionID, convoID, loadout):
    command_return = {"status": "", "name" :name, "message": ""}
    eZprint_anything(['reading file', args], ['COMMANDS', 'OPEN_FILE'])            
    if sessionID not in whole_cartridge_list:
        await get_cartridge_list(sessionID)
    if 'filename' in args:
        filename = args['filename']
        eZprint_anything(['reading file', filename], ['COMMANDS', 'OPEN_FILE'])
        for cartKey, cartVal in whole_cartridge_list[sessionID].items():
            if cartVal.get('label', '') == filename: 
                    print('found match' + str(cartVal))
            
                    return_string = ''
                    print('file found')
                    if cartVal.get('softDelete') == True:
                        return_string += "File " + filename + " opened.\n"
                    else:
                        return_string += "File " + filename + " already open.\n"

                    payload = {
                        'sessionID': sessionID,
                        'convoID' : convoID, 
                        'cartridge' : cartKey,
                        'fields':
                                {'enabled': True,
                                'minimised': False,
                                'softDelete': False,
                                }
                                }
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


async def broad_query(name, args, sessionID, thread, convoID, loadout):
         # await get_cartridge_list(convoID)
    all_text = ''
    command_return = {"status": "", "name" :name, "message": ""}
    if 'query' not in args or args['query']=='':
        command_return['status'] = "Error."
        command_return['message'] = "Arg 'query' missing"
        return command_return

    if 'filename' in args:
        filename = args['filename']

        for cartKey, cartVal in active_cartridges[convoID].items():
            all_text += str(cartVal)
            string_match = distance(filename, str(cartVal['label']))

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

                        response = await handle_query(input, convoID, loadout)
                        response = str(response)

                        command_return['status'] = "Success."
                        command_return['message'] = "From " + args['filename']  + ": "+ response
                        print(command_return)
                        return command_return
                    
                    else:
                        command_return['status'] = "Error."
                        command_return['message'] = "Arg 'query' missing"
                        return command_return

    #             if 'type' in cartVal and cartVal['type'] == 'summary':
    #                 if 'query' in args:
    #                     if 'blocks' in cartVal:
    #                         if 'summaries' in cartVal['blocks']:
    #                             query_response = await traverse_blocks(args['query'], cartVal['blocks'], sessionID,cartKey, convoID, loadout)
    #                             command_return['status'] = "Success."
    #                             command_return['message'] = "From " + filename  + ": "+ str(query_response)
    #                             print(command_return)
    #                             return command_return
                            

    #             if 'query' in args:
    #                 string_to_query = ''

    #                 if 'text' in cartVal:
    #                     string_to_query += cartVal['text']
    #                 if 'json' in cartVal:
    #                     string_to_query += str(cartVal['json'])

    #                 if string_to_query != '':
    #                     query_response = await quick_query(str(string_to_query), str(args['query']))
    #                     command_return['status'] = "Success."
    #                     command_return['message'] = "From " + filename  + ": "+ str(query_response)
    #                     print(command_return)
    #                     return command_return
                    
    #     for cartKey, cartVal in active_cartridges[convoID].items():
    #         if 'type' in cartVal and cartVal['type'] == 'summary':
    #             # print('searching summary for pointer')
    #             if 'blocks' in cartVal:
    #                 if 'summaries' in cartVal['blocks']:
    #                     for summaries in cartVal['blocks']['summaries']:
    #                         for summaryKey, summaryVal in summaries.items():
    #                             if 'title' in summaryVal:
    #                                 similarity = distance(filename, summaryVal['title'])
    #                                 # print('distance: ' + str(similarity))
    #                                 # print('filename: ' + filename)
    #                                 # print('label: ' + str(summaryVal['title']))
    #                                 if similarity <3:
    #                                     # print('found match' + str(summaryVal))
    #                                     if 'query' in args:
    #                                         query_response = await traverse_blocks(args['query'], cartVal['blocks'], sessionID,cartKey, convoID, loadout)
    #                                         command_return['status'] = "Success."
    #                                         command_return['message'] = "From " + filename  + ": "+ str(query_response)
    #                                         print(command_return)
    #                                         return command_return
                                    

    # print('all text query')
    # query = ''
    # if 'query' in args:
    #     # query = args['query']
    #     # query_response = await quick_query(all_text, str(query))
    #     command_return['status'] = "Return."
    #     command_return['message'] = "File not found, please use exact filename"
    #     return command_return


async def traverse_blocks(query, blocks, sessionID, cartKey, convoID, loadout):

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
            node = await get_summary_children_by_key(to_open, convoID, sessionID, cartKey, loadout)
            eZprint_anything(node, ['COMMANDS', 'TRAVERSE'])
            if node:
                if node.get('children'):
                    for child in node['children']:
                        eZprint('child' + str(child), DEBUG_KEYS + ['TRAVERSE'])
                        if 'title' in child:
                            text_to_query += '-## '+ child['title']
                        if 'body' in child:
                            text_to_query += "\n"+ child['body'] + "\n"
                        else:
                            text_to_query += str(child) + "\n"
                if node.get('source'):
                    text_to_query += "\n Source: " + str(node['source']) + "\n"
                    ## originaly wrote to blocks, definitely could be useful to build out / navigate tree, but will just return response for now
                    # if child not in blocks['summaries']:
                    #     # print('optimistically adding child')
                    #     blocks['summaries'].append(child)
                    #     input = {
                    #         'cartKey' : cartKey,
                    #         'sessionID' : sessionID,
                    #         'blocks' : blocks
                    #     }
                    #     update_cartridge_field(input, convoID, loadout)
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
    # if 'keywords' in blocks:
    #     closest = 0
    #     to_open = ''
    #     for key, val in blocks['keywords'].items():
    #         similarity = distance(str(query), str(key))
    #         # print('checking for matches ' + str(query) + ' ' + str(key) + ' ' + str(similarity))
    #         if similarity > closest:
    #             closest = similarity
    #             for element in val:
    #                 to_open = element['source']

    #     if to_open:
    #         node = await get_summary_children_by_key(to_open, convoID, sessionID, key, loadout)
    #         if node:
    #             for child in node:
    #                 if 'title' in child:
    #                     text_to_query += child['title'] + ": "
    #                 if 'body' in child:
    #                     text_to_query += child['body'] + "\n"
    #                 else:
    #                     text_to_query += str(child) + "\n"
        # print('text to query: ' + text_to_query)
        response = await quick_query(text_to_query, str(query))
        response = str(response)
        print(response)
        return response

async def read_text(name, text_title, text_body, convoID, thread = 0, page = None, elements = None):

    command_return = {"status": "", "name" :name, "message": ""}

    eZprint('text larger than 2k starting large doc loop ' + str(len(text_body)), ['COMMANDS', 'READ'])
    command_return = await large_document_loop(text_title, text_body, name, convoID, thread, page, elements = elements, break_into_sections= True)
    return command_return



async def list_files(name, sessionID, loadout, convoID, thread = 0):
    command_return = {"status": "", "name" : name, "message": ""}

    eZprint('list available files', ['COMMANDS', 'LIST_FILES'])
    string = '\nOpen files:\n'

    label = ''
    type = ''
    description = ''
    preview = ''
    state = ''
    # string = ''
    # await ava(convoID)
    if sessionID in active_cartridges:
        for key, val in active_cartridges[convoID].items():
            if 'type' in val and val['type'] == 'note' or val['type'] == 'index' or val['type'] == 'summary':
                if val.get('label', None):
                    print(val['label'])
                    string += '\n-' + val['label']
                if val.get('lastUpdated', None):
                    string += ' | Last updated : ' + val['lastUpdated']
                if val.get('summary', None):
                    string += ' | Summary: ' + val['summary']
                # if val.get('text', None):
                #     string += val['text'][0:280] + '...\n'
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
            if key not in active_cartridges[convoID]:
                if scope == 'global' or loadout == None or 'initial-loadout' in val and val['initial-loadout'] == loadout:
                    if val.get('label', None):
                        print(val['label'])
                        string += '\n-' + val['label']
                    if val.get('lastUpdated', None):
                        string += ' | Last updated : ' + val['lastUpdated']
                    if val.get('summary', None):
                        string += ' | Summary: ' + val['summary']
                    # if val.get('text', None):
                    #     string += val['text'][0:280] + '...\n'
        string += '[Closed file commands: Open, Read, Query or Delete.]'

    if string == '':
        string = 'no files available'
        command_return['status'] = "Success."
        command_return['message'] = string
        return command_return
    
    # if len(string) > 2000:
    command_return = await large_document_loop("Files available", string, name, sessionID, thread)
    return command_return



async def search_files(name, args, sessionID, loadout, thread = 0):
    SEARCH_DEBUG_KEYS = DEBUG_KEYS + ['SEARCH']
    command_return = {"status": "", "name" : name, "message": ""}

    query = args.get('query', '')
    results = await search_cartridges(query, sessionID, SEARCH_DEBUG_KEYS)
    # print(results)
    scope = None
    if sessionID in novaSession and 'convoID' in novaSession[sessionID]:
        convoID = novaSession[sessionID]['convoID'] 
    if convoID in novaConvo and 'scope' in novaConvo[convoID]:
        scope = novaConvo[convoID]['scope']
    # print(novaConvo[convoID])

    search_response = ''
    for cartridge in results:
        # for key, val in cartridge.items():
        if scope == 'global' or loadout == None or 'initial-loadout' in cartridge and cartridge['initial-loadout'] == loadout:
            if cartridge.get('label', None):
                eZprint(cartridge['label'], SEARCH_DEBUG_KEYS)
                search_response += '\n- **' + cartridge['label'] + '**'
            if cartridge.get('lastUpdated', None):
                search_response += ' | _Last updated_:' + cartridge['lastUpdated'] + f" | [Read]() | [Query]()" 
            if cartridge.get('snippet', None):
                search_response += '\n	- ' + cartridge['snippet']
            # if cartridge.get('summary', None):
            #     search_response += ' | Summary: ' + cartridge['summary']
            # if cartridge.get('text', None):
            #     search_response += ' | ' + cartridge['text'][0:280] + '...\n'
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
        command_return = await large_document_loop(query, search_response, name, sessionID, thread)
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
