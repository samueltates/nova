from session.sessionHandler import  command_loops
from tools.debug import eZprint, eZprint_anything
import re

DEBUG_KEYS = ['TEXT']

async def large_document_loop(title, text_to_read, command = '', convoID= '', thread = 0, requested_page = None, elements = None, break_into_sections = False):

    command_return = {"status": "", "name" : command, "message": ""}

    if convoID not in command_loops:
        command_loops[convoID] = {}
    if thread not in command_loops[convoID]:
        command_loops[convoID][thread] = {}
    if command not in command_loops[convoID][thread]:
        command_loops[convoID][thread][command] = {}
        
    if title not in command_loops[convoID][thread][command]:
        command_loops[convoID][thread][command][title] = {}

    if 'page' not in command_loops[convoID][thread][command][title]:
        command_loops[convoID][thread][command][title]['page'] = 0
    
    page = command_loops[convoID][thread][command][title]['page']
    eZprint('current page is ' + str(page) + ' and thread is ' + str(thread), ['COMMANDS', 'READ'])

    if requested_page:
        page = int(requested_page)

    combined_sections_text = ''
    
    if 'paginated_sections' not in command_loops[convoID][thread][command][title]:

        eZprint('getting text and creating sections', ['COMMANDS', 'READ', 'PAGINATE'])

        if isinstance(text_to_read, dict):
            text_to_read = parse_object_to_markdown(text_to_read, 0)

        if elements:
            parsed_elements_text = parse_elements(elements)
            eZprint_anything(elements, ['COMMANDS', 'READ'], message= 'elements returned')
            if parsed_elements_text:
                # paginated_content += elements
                combined_sections_text += parsed_elements_text
            eZprint_anything(combined_sections_text, ['COMMANDS', 'PAGINATE'], message= 'combined_sections_text returned')
        
        
        combined_sections_text += text_to_read
        pages = paginate_text(combined_sections_text, 500)
        eZprint_anything(pages, ['COMMANDS', 'PAGINATE'], message= 'pages returned')

        command_loops[convoID][thread][command][title]['paginated_sections'] = pages
    
    paginated_sections = command_loops[convoID][thread][command][title]['paginated_sections']

    if page == 0:
        message = "\n## "+ title + "\n\n "
    else:
        message = "\n#### " + title + " \n\n\n " 
    
    if page > len(paginated_sections)-1:
        page = len(paginated_sections)-1
        
    message += str(paginated_sections[page])
    
    if len(paginated_sections) == 1:
        eZprint('only one page', ['COMMANDS', 'READ', 'PAGES'])
        command_return['status'] = "Read complete."
        command_return['message'] = message



    if len(paginated_sections) > 1:

        eZprint('adding page counter page' + str(page),  ['COMMANDS', 'READ', 'PAGES'])
        message += "\n\n#### Page " + str(page) + " of " + str(len(paginated_sections)-1)

        if page < len(paginated_sections)-1:
            
            eZprint('not final page, current page :' + str(page) + ' of ' + str(len(paginated_sections)-1),  ['COMMANDS', 'READ', 'PAGES'])

            command_return['status'] = 'Page returned.'
            command_return['message'] = message + "\n\n_Use '" + command + " " + title + "' for next page or include page for a specific page._"
            command_return['name'] = command
            command_loops[convoID][thread][command][title]['page'] += 1


        else:
            eZprint('on final page :' + str(page) + ' of ' + str(len(paginated_sections)),  ['COMMANDS', 'READ', 'PAGES'])
            command_return['status'] = "Read complete."
            command_return['message'] = message + "\n\n**" + command + " " +title + " is complete.**" 
            command_return['message']  += "\n\n_Use " + command + " " + title + " to restart or or include page for a specific page._"
            command_loops[convoID][thread][command][title]['page'] = 0

    
    return command_return




def break_into_sections(text):
    sections = {}
    sections['Overview'] = []
    current_section = 'Introduction'
    sections[current_section] = []

    for line in text.split('\n'):
        if re.match(r'^#+ ', line):  # Matches markdown headings
            current_section = line.strip()
            sections[current_section] = []
            sections['Overview'].append(line.strip())
        else:
            sections[current_section].append(line.strip())


    return sections

def get_section_titles(text):
    titles = []
    for line in text.split('\n'):
        if re.match(r'^#+ ', line):  # Matches markdown headings
            titles.append("- " + line.strip())
    return titles




def paginate_text(text, max_words_per_page=500):
    eZprint('paginating text', ['COMMANDS', 'PAGINATE'])
    lines = text.splitlines()
    eZprint_anything(lines, ['COMMANDS', 'PAGINATE'], message= 'lines returned')

    pages = []
    current_page = []
    current_word_count = 0

    for line in lines:
        words_in_line = len(line.split())
        if current_word_count + words_in_line > max_words_per_page:
            pages.append('\n'.join(current_page))
            current_page = [line]
            current_word_count = words_in_line
        else:
            current_page.append(line)
            current_word_count += words_in_line

    if current_page:
        pages.append('\n'.join(current_page))

    eZprint(str(pages), ['COMMANDS', 'PAGINATE'], message= 'pages returned')

    return pages

def parse_elements(elements ):
    sections = []
    section_titles = []

    current_section = ' '
    for element in elements:
        eZprint_anything(element, ['COMMANDS', 'PAGINATE', 'ELEMENTS'], message= 'element returned')
        if element.get('type') == 'Title':

            current_section = element.get('text')
            new_header = adjust_header_depth(current_section, 4)
            # new_header = adjust_list_items(new_header, indent_depth=1, list_signifier='-')
            section_titles.append(new_header)
            eZprint_anything(new_header, ['COMMANDS', 'PAGINATE', 'ELEMENTS'], message= 'new_header returned')
        if element.get('type') == 'ListItem':
            eZprint_anything(element.get('text'), ['COMMANDS', 'PAGINATE', 'ELEMENTS'], message= 'element.get(text) returned')
            sections.append((current_section, element.get('text')))
        if element.get('type') == 'NarrativeText':
            eZprint_anything(element.get('text'), ['COMMANDS', 'PAGINATE', 'ELEMENTS'], message= 'element.get(text) returned')
            sections.append((current_section, element.get('text')))
            
    # ez
    combined_sections_text = "### Overview\n"
    for title in section_titles:
        # change heading level from current to -###
        combined_sections_text += title + '\n'
        #preview 
        # if len(sections[0][1]) > 200:
        #     combined_sections_text += sections[0][1][0:200] + '...\n'
        # else:
        #     combined_sections_text += sections[0][1] + '\n'
    for section, content in sections:
        combined_sections_text += '\n' + section + '\n' + content + '\n'
    
    return combined_sections_text

        


def parse_sections(unsorted_text):
    # Split the text into sections
    sections_pattern = re.compile(r'(#{1,6}\s[^\n]+)')
    eZprint_anything(unsorted_text, ['COMMANDS', 'PAGINATE'], message= 'unsorted_text returned')
    sections_parts = sections_pattern.split(unsorted_text)
    eZprint_anything(sections_parts, ['COMMANDS', 'PAGINATE'], message= 'sections_parts returned')
    # Pair section headings with their content and strip extra spaces
    section_titles = []
    sections = []
    current_section = ' '
    for part in sections_parts:
        eZprint('part is' + str(part), ['COMMANDS', 'PAGINATE'])
        if part.startswith('#'):
            current_section = part.strip()
            # new_header = adjust_header_depth(current_section, 4)
            # new_header = adjust_list_items(new_header, indent_depth=1, list_signifier='-')
            eZprint('new_header is' + str(current_section), ['COMMANDS', 'PAGINATE'])
            
            # eZprint('current_section is' + str(current_section), ['COMMANDS', 'PAGINATE'])
            section_titles.append(current_section)
        elif current_section:
            eZprint('current_section is' + str(current_section), ['COMMANDS', 'PAGINATE'])
            sections.append((current_section, part))

    # Generate a flat list of section texts for pagination
    combined_sections_text = "### Overview\n"
    for title in section_titles:
        combined_sections_text += title + '\n'
    for section, content in sections:
        combined_sections_text += '\n' + section + '\n' + content + '\n'
    

    return combined_sections_text


def adjust_header_depth(markdown_text, target_depth):
    lines = markdown_text.splitlines()
    adjusted_lines = []

    for line in lines:
        # Increase header depth
        if line.startswith('#'):
            current_depth = len(line) - len(line.lstrip('#'))
            depth_difference = target_depth - current_depth
            adjusted_line = '#' * depth_difference + line if depth_difference > 0 else line
        else:
            adjusted_line = line
        adjusted_lines.append(adjusted_line)

    return '\n'.join(adjusted_lines)


def adjust_list_items(markdown_text, indent_depth=None, list_signifier=None, add_check=False, remove_check=False):
    lines = markdown_text.splitlines()
    adjusted_lines = []

    for line in lines:
        stripped_line = line.lstrip()
        is_list_item = stripped_line.startswith(('-', '*', '+'))
        is_checked = stripped_line.startswith('- [x]') or stripped_line.startswith('- [ ]')
        
        # Adjust indentation
        new_indent = ' ' * (2 * indent_depth) if indent_depth is not None else ''
        # Change the list bullet signifier if requested
        if list_signifier:

            bullet, rest_of_line = stripped_line.split(' ', 1)
            if not is_checked or add_check or remove_check:
                stripped_line = list_signifier + ' ' + rest_of_line
        # Add or remove task checkboxes if requested
        if add_check and not is_checked:
            stripped_line = '- [ ] ' + stripped_line.lstrip('-*+ ')
        if remove_check and is_checked:
            stripped_line = '- ' + stripped_line[5:]
        # Combine the new indent with the updated line
        line = new_indent + stripped_line
            
        adjusted_lines.append(line)

    return '\n'.join(adjusted_lines)


# def parse_to_markdown(json_obj, level=0):
#     output = ""
#     # Check the type of the JSON object and process accordingly
#     if isinstance(json_obj, dict):
#         for key, value in json_obj.items():
#             if key == 'type':
#                 output += handle_type(value, level, json_obj)
#             elif key == 'content':
#                 output = parse_to_markdown(value, level + 1)
#             # ...
#     elif isinstance(json_obj, list):
#         for item in json_obj:
#             output += parse_to_markdown(item, level)
#     # ...

#     return output

# def handle_type(type_value, level, json_obj):
#     # Here we'll define rules for different types
#     output = ""
#     if type_value in ["heading", "Title"]:
#         output += convert_to_heading(json_obj, level)
#     elif type_value in ["taskList", "taskItem"]:
#         output += convert_to_task(json_obj, level)
#     # ...
#     return output


# def parse_tiptap_to_markdown(tiptap_json, level=0):
#     """
#     Parses TipTap JSON structure to Markdown.
    
#     :param tiptap_json: The TipTap JSON object to parse
#     :param level: Current indentation/nesting level
#     :return: A Markdown string representation of the TipTap JSON
#     """
#     # Initialize the Markdown output
#     markdown_output = ""

#     # Check if the main content key exists
#     if "content" in tiptap_json:
#         for node in tiptap_json["content"]:
#             if node["type"] == "heading":
#                 # Convert headinglevel to '#' symbols
#                 markdown_output += ("#" * node["attrs"]["level"]) + " "
#                 # Append the heading text
#                 if "content" in node:
#                     for content in node["content"]:
#                         markdown_output += content["text"]
#                 # Add newline to end the heading
#                 markdown_output += "\n\n"
            
#             elif node["type"] == "taskList":
#                 # Process each taskItem in the list and maintain the level
#                 for task in node["content"]:
#                     markdown_output += parse_tiptap_to_markdown(task, level + 1)

#             elif node["type"] == "taskItem":
#                 # Add '- [ ]' or '- [x]' based on the checked attribute
#                 markdown_output += "  " * level + "- [" + ("x" if node["attrs"]["checked"] else " ") + "] "
#                 # Append the task text
#                 if "content" in node:
#                     for content in node["content"]:
#                         markdown_output += parse_tiptap_to_markdown(content, level)
#                 # Add newline for the next item
#                 markdown_output += "\n"
            
#             elif node["type"] == "paragraph":
#                 # Process each content within the paragraph
#                 if "content" in node:
#                     for content in node["content"]:
#                         markdown_output += content["text"]
#                 # Add double newline to separate paragraphs
#                 markdown_output += "\n\n"
            
#             # Other types can be added with respective handling
#             # ...

#     return markdown_output


markdown_syntax_map = {
    "title": "#",
    "blockquote": "> ",
    "bulletlist": "",  # Nested lists will increase indentation
    "codeblock": "`",  # Multi-line code blocks wrapped in triple backticks
    "details": "<details>",  # Not standard Markdown (we'll use HTML)
    "detailssummary": "<summary>",
    "detailscontent": "",
    "hardbreak": "\n\n",
    "heading": "#",
    "horizontalrule": "\n---\n",
    "image": "![alt text]({url})",  # Images will be included inline
    "listitem": "- ",  # Nested lists will increase indentation
    "orderedlist": "1.",  # Ordered lists with incrementing numbers
    "paragraph": "",
    "table": "", # We'll need to construct Markdown tables
    "tablerow": "",
    "tablecell": "",
    "tasklist": "",
    "taskitem": "- [ ] ",  # with space or 'x' between the brackets
    "text": ""
    # Additional types like Emoji or YouTube need custom handling
}


# def handle_heading(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'heading node returned')
#     # Create Markdown heading based on the level
#     # syntax = '#'
#     return '\n'+(syntax * node['attrs']['level']) + ' ' + parse_tiptap_content(node['content']) + '\n'

# def handle_paragraph(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'paragraph node returned')
#     # Paragraphs have no special formatting in Markdown
#     return parse_tiptap_content(node['content']) + '\n\n'

# def handle_listitem(node, level, syntax):

#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'listitem node returned')
#     # List items should start with '-'
#     return "  " * level + syntax + parse_tiptap_content(node['content']) + '\n'

# def handle_bulletlist(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'bulletlist node returned')
#     # Iterate over list items and add Markdown list item syntax
#     markdown_list = ""
#     for item in node['content']:
#         markdown_list += "  " * level + syntax + ' ' + parse_tiptap_content(item, level + 1) + '\n'
#     return markdown_list

# def handle_orderedlist(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'orderedlist node returned')
#     markdown_list = ""
#     for i, item in enumerate(node['content'], start=1):
#         markdown_list += "  " * level + str(i) + '. ' + parse_tiptap_content(item, level + 1) + '\n'
#     return markdown_list

# def handle_tasklist(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'tasklist node returned')
#     # TaskList is similar to BulletList but has checkboxes
#     markdown_list = ""
#     for item in node['content']:
#         markdown_list += "  " * level + syntax + ' ' + parse_tiptap_content(item, level + 1) + '\n'
#     return markdown_list

# def handle_taskitem(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'taskitem node returned')
#     checked = "x" if node['attrs']['checked'] else " "
#     return "\n  " * level + f"{syntax[:3]}{checked}{syntax[4:]} " + parse_tiptap_content(node, level) + '\n'

# def handle_bloquote(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'blockquote node returned')
#     # Blockquote content should start with '>'
#     return syntax + parse_tiptap_content(node['content']) + '\n\n'

# def handle_codeblock(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'codeblock node returned')
#     # Code blocks in Markdown are wrapped in triple backticks
#     return "```" + "\n" + parse_tiptap_content(node['content']).strip() + "\n""```" + '\n\n'

# def handle_image(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'image node returned')
#     # In Markdown images are represented as ![alt text](url)
#     alt_text = node['attrs'].get('alt', '')
#     image_url = node['attrs'].get('src', '')
#     return f'![{alt_text}]({image_url})' + '\n\n'

# def handle_text(node, level, syntax):
#     eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'text node returned')
#     # Text nodes have no special formatting, return the text directly
#     return node['text'] if 'text' in node else ''

# # The central parsing function:
# def parse_tiptap_to_markdown(tiptap_json, level=0):
#     eZprint_anything(tiptap_json, ['COMMANDS', 'PAGINATE'], message= 'tiptap_json returned')
#     markdown_output = ""


#     if "content" in tiptap_json:
#         for node in tiptap_json['content']:
#             # Depending on the type, call the appropriate handler function
#             handler_func_name = 'handle_' + node['type'].lower()
#             syntax = markdown_syntax_map.get(node['type'].lower(), '')

#             if 'content' in node:
#                 eZprint_anything(node['content'], ['COMMANDS', 'PAGINATE'], message= 'content found')
#                 if handler_func_name in globals():
#                     eZprint_anything(handler_func_name, ['COMMANDS', 'PAGINATE'], message= 'function found')
#                     handler_function = globals()[handler_func_name]
#                     markdown_output += handler_function(node, level,  syntax)
#                 else:
#                     eZprint_anything(handler_func_name, ['COMMANDS', 'PAGINATE'], message= 'function not found')
#                     # If a handler doesn't exist, fall back to text handling
#                     markdown_output += handle_text(node, level, syntax)
#             elif 'text' in node:
#                 eZprint_anything(node['text'], ['COMMANDS', 'PAGINATE'], message= 'text found and no content')
#                 markdown_output += handle_text(node, level, syntax)
                
#     return markdown_output.strip()


# def parse_tiptap_content(node_content, level=0):
#     eZprint_anything(node_content, ['COMMANDS', 'PAGINATE'], message= 'node_content returned')
#     # When content is a list of objects, parse each
#     parsed_content = ""
#     if isinstance(node_content, list):
#         eZprint_anything(node_content, ['COMMANDS', 'PAGINATE'], message= 'node_content is list')
#         for content in node_content:
#             if 'text' in content:
#                 parsed_content += content['text']
#             if 'content' in content:
#                 parsed_content += parse_tiptap_to_markdown(content, level+1) # Recurse into nested content
#     elif isinstance(node_content, dict):
#         eZprint_anything(node_content, ['COMMANDS', 'PAGINATE'], message= 'node_content is dict')
#         # When content is a single object, parse it
#         if 'text' in node_content:
#             parsed_content += node_content['text']
#         if 'content' in node_content:
#             parsed_content += parse_tiptap_to_markdown(node_content, level+1)
#     return parsed_content

## need a router so if a new doc then wraps in doc, if existing, appends to existing

def create_json_doc(text, DEBUG_KEYS = DEBUG_KEYS):

    eZprint('new document called', DEBUG_KEYS)

    
    parsed_content = parse_text_to_json(text, DEBUG_KEYS)
    

    document_json = {
        'type':'doc',
        'content':parsed_content
        }

    return document_json

def update_json_doc(text, existing_doc, DEBUG_KEYS = DEBUG_KEYS):

    parsed_content = parse_text_to_json(text, DEBUG_KEYS)
    existing_doc.setdefault('content', []).extend(parsed_content)

    return existing_doc

def parse_text_to_json(text, DEBUG_KEYS = DEBUG_KEYS):
    PARSE_DEBUG = DEBUG_KEYS + ['PARSE']
    
    eZprint('parse_text_to_json_called', PARSE_DEBUG)
    lines = text.split('\n')
    content = []
    current_parent = content
    parent_type = ''
    stack = [{'level':0, 'node': content}]

    for line in lines:
        eZprint_anything(line, PARSE_DEBUG, message = 'line being checked')
        type, level =  determine_text_type(line, PARSE_DEBUG)
        content_node = create_content_node(line, type, PARSE_DEBUG)
        if parent_type != wrapper_types.get(type,''):
            eZprint('parent doesnt match required type so creating wrapper ', PARSE_DEBUG)
            parent_node = create_wrapper_node(type, PARSE_DEBUG)
            current_parent.append(parent_node)
            current_parent = parent_node.get('content',[])
            parent_type = wrapper_types.get(type,'')
            ## how does it handle if it drops a level while still in same 'type' ...
        if level > stack[-1]['level']:
            ## child of current so add
            eZprint('child of current, dropping a level, so creating new parent ', PARSE_DEBUG)
            current_parent.append(content_node)
            stack.append({'level': level, 'node':content_node})
            current_parent = content_node.get('content', [])
        elif level < stack[-1]['level']:
            #higher in stack so remove till get to sibling
            eZprint('lower level than current so clearing stack till find sibling', PARSE_DEBUG)
            while stack and stack[-1]['level'] >= level:
                stack.pop()
            stack[-1]['node']['content'].append(content_node)
            current_parent = content_node.get('content', [])
        else:
            #sibbling so add? whats different
            eZprint('sibbling of current so appending', PARSE_DEBUG)
            current_parent.append(content_node)

        eZprint_anything(current_parent, PARSE_DEBUG, message = 'current parent after cycle')
        eZprint_anything(stack, PARSE_DEBUG, message = 'stack after cycle')
    
    #so this returns whole doc which is maybe fine for raw text
    return content            
   
"""
    - break text into chunks
    - cycle through
    - detect type
    - if parent type create type, text, content, stores level
    - loop through adding nodes as children
    - if hits same or lower level breaks
    - how do we account for depth via tab?

"""


def determine_text_type(line, DEBUG_KEYS = DEBUG_KEYS):
    level = None
    type = 'text'
    if line.startswith('#'):
        level = line.count('#')
        type = 'heading'
    if line.startswith('- ') or line.startswith('* '):
        type = 'listItem'
    if line.startswith('-[ ] '):
        type = 'taskItem'
    if isinstance(line[0], int) :
        type = 'orderedListItem'
    if not level:
        level = line.count('  ')
    eZprint('line assesed, type is ' + type + ' level is ' + str(level), DEBUG_KEYS)    
    return type, level
    

wrapper_types = {
    #child type : parent type
    'text':'paragraph',
    'listItem':'bulletList',
    'taskItem':'taskList',
    'orderedListItem': 'orderedList'
}


def create_wrapper_node(type, DEBUG_KEYS = DEBUG_KEYS):
    # TODO : could probably parse just type to get corresponding, then one item

    # handles default esp text
    parent_type = wrapper_types.get(type, 'paragraph')

    wrapper_object = {
        'type':parent_type,
        'content':[]
    }

    eZprint_anything(wrapper_object, DEBUG_KEYS, message = 'parent after transform')

    return wrapper_object


def create_content_node(line, type, level):
    # Create a JSON node based on type, this is a placeholder for actual handler functions
    # maybe this is parent node creator, so if new level then parent node creator v child


    if type == 'heading':
        content_node = handle_heading_item(line, level, DEBUG_KEYS)
    
    elif type == 'listItem':    
        content_node = handle_list_item(line, DEBUG_KEYS)

    elif type == 'taskItem' :
        content_node = handle_task_item(line, DEBUG_KEYS)
    elif type == 'text':
        content_node = handle_text_item(line, DEBUG_KEYS)
    else: 
        content_node = handle_generic_item(line, type, DEBUG_KEYS)

    return content_node



def handle_heading_item(line, level, DEBUG_KEYS):
    eZprint('handling heading item', DEBUG_KEYS)
    heading_json = {'type': 'heading', 
        'attrs':{'level':level},
        'content': [
            {'text':line}
            ]
        }
    eZprint_anything(heading_json, DEBUG_KEYS, message = 'heading json returned')

    return heading_json

def handle_text_item(line, DEBUG_KEYS = DEBUG_KEYS):
    eZprint('handling text item', DEBUG_KEYS)

    text_json = {
        'type': 'text',
        'text': line
    }
    eZprint_anything(text_json, DEBUG_KEYS, message = 'text json returned')
    return text_json

def handle_generic_item(line, type, DEBUG_KEYS = DEBUG_KEYS):
    eZprint('handling generic item', DEBUG_KEYS)
    generic_json = {'type': type, 'content': [
        {
            'type':'text',
            'text': line
        }

    ]}
    eZprint_anything(generic_json, DEBUG_KEYS, message = 'generic json returned')

    return generic_json


def handle_list_item(line, DEBUG_KEYS = DEBUG_KEYS):
    eZprint('handling list item', DEBUG_KEYS)
    list_item_json =  {
            'type':'paragraph',
            'content': [{
                'type': 'text',
                'text' : line
            }]
        }
    eZprint_anything(list_item_json, DEBUG_KEYS, message = 'list json returned')

    return list_item_json

def handle_task_item(line, DEBUG_KEYS = DEBUG_KEYS):
    eZprint('handling task item', DEBUG_KEYS)
    task_item_pattern = r'^- \[(x|X| )\] (.*)'

    match = re.match(task_item_pattern, line.strip())

    if match:

        eZprint_anything(match, DEBUG_KEYS, message = 'handling task item')
        checked_state = match.group(1).strip().lower() == 'x'  # Determine if the task is checked
        task_description = match.group(2).strip()

        task_item_json = {
            'type': "taskItem",
            'attrs': {
                'checked': checked_state
            },
            'content':[{
            'type':'paragraph',
            'content': [{
                'type': 'text',
                'text' : task_description
                }]
            }]
        }

        eZprint_anything(task_item_json, DEBUG_KEYS, message = 'task json returned')
        return task_item_json
    

        
    


    
        

def parse_object_to_markdown(parent_node, level = 0):
    eZprint_anything(parent_node, ['COMMANDS', 'PAGINATE'], message= 'object received to parse , level ' + str(level))
    return_string = ''
    if isinstance(parent_node, dict):
        if 'type' in parent_node:
            eZprint(parent_node['type'] + ' found so transforming', ['COMMANDS', 'PAGINATE'])
            return_string += handle_by_type(parent_node, level)

    if isinstance(parent_node, list):
        eZprint('object is a list so looping',['COMMANDS', 'PAGINATE'])
        for child_object in parent_node:
            eZprint_anything(child_object, ['COMMANDS', 'PAGINATE'], message= 'list object')
            return_string += parse_object_to_markdown(child_object, level)

    eZprint('return string is ' + return_string, ['COMMANDS', 'PAGINATE'])
    return return_string

def handle_by_type(node, level):
    node_type = node.get('type')
    string = ''
    syntax = markdown_syntax_map.get(node_type.lower(), '')
    handler_func_name = 'handle_' + node['type'].lower()
    if handler_func_name in globals():
        handler_function = globals()[handler_func_name]
        string = handler_function(node, level, syntax)
    else:
        if 'content' in node:
            string = parse_object_to_markdown(node['content'], level)
    
    if string == None:
        string = ''
    
    return string

def handle_heading (node, level, syntax):

    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'heading node returned')

    string = ''
    depth = '\n' + ('  ' * level)

    if node.get('attrs',{}).get('level'):
        string = syntax * node.get('attrs',{}).get('level') + " " 

    string = depth + string + parse_object_to_markdown(node.get('content','')) + '\n'
    
    eZprint('return string is ' + string, ['COMMANDS', 'PAGINATE'],)
    return string



def handle_paragraph(node, level, syntax):
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'paragraph node returned')
    # Paragraphs have no special formatting in Markdown
    string = ''
    if 'content' in node:
        string += parse_object_to_markdown(node['content'])
            
    eZprint('return string is ' + string, ['COMMANDS', 'PAGINATE'],)
    return string

def handle_text(node, level, syntax):
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'text node returned')
    # Text nodes have no special formatting, return the text directly
    return node['text'] if 'text' in node else ''

def handle_bulletlist(node, level, syntax):
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'bulletlist node returned')
    # Iterate over list items and add Markdown list item syntax
    string = ''
    depth = '\n' + ('  ' * level)

    for item in node.get('content',[]):
            string += depth + parse_object_to_markdown(item, level + 1) + '\n'
        
    eZprint('return string is ' + string, ['COMMANDS', 'PAGINATE'],)
    return string

def handle_listitem(node, level, syntax):
    string = ''
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'listitem node returned')
    # List items should start with '-'
    string =  syntax + parse_object_to_markdown(node.get('content',''), level) 
    eZprint('return string is ' + string, ['COMMANDS', 'PAGINATE'])

    return string

def handle_tasklist (node, level, syntax):
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'tasklist node returned')
    string = ''
    depth = '\n' + ('  ' * level)

    for item in node.get('content',[]):
        string += depth + parse_object_to_markdown(item, level + 1) +'\n'
    
    eZprint('return string is ' + string, ['COMMANDS', 'PAGINATE'],)
    return string

def handle_taskitem (node, level, syntax):
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'taskitem node returned')

    string = ''
    checked = "x" if node.get('attrs',{}).get('checked') else " "
    syntax = f"{syntax[:3]}{checked}{syntax[4:]} "
    string = syntax + parse_object_to_markdown(node.get('content',''), level)

    eZprint('return string is ' + string, ['COMMANDS', 'PAGINATE'],)
    return string

def handle_orderedlist(node, level, syntax):
    eZprint_anything(node, ['COMMANDS', 'PAGINATE'], message= 'orderedlist node returned')
    markdown_list = ""
    for i, item in enumerate(node['content'], start=1):
        markdown_list += "  " * level + str(i) + '. ' + parse_object_to_markdown(item, level + 1) + '\n'
    return markdown_list