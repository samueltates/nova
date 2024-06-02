from session.appHandler import app, websocket
from core.services import transcribe_file
from chat.chat import handle_message, user_input, return_to_GPT
from tools.debug import eZprint
from core.commands import handle_commands
import json

DEBUG_KEYS = ['WORKFLOWS']

async def check_for_workflow(triggers, source, sessionID, convoID, loadout):
    eZprint('workflow check', DEBUG_KEYS)

    outputs = []      
    trigger_count = 0
    outputs.append(source)
    for trigger in triggers:
        for workflow in dummy_workflows:
            if trigger.get('type') == workflow.get('trigger'):
                trigger_count += 1
                response = ''
                if workflow.get('action') == 'transcribe':
                    # status as transcriubing should come from action (ie updating user)
                    await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'whisper', 'state': ''}, 'convoID': convoID}))
                    target = trigger.get('target')
                    if target == 'source':
                        # maybe should get passed to commands from here and tap into that worfkflow ..
                        target = outputs[-1]
                        command = {'name':'transcribe', 'args':{'file_key':target['cartKey'], 'file_name':target['file_name'], 'file_type':target['file_type'] }}
                        response = await handle_commands(command, convoID, 0, loadout)
                        if response.get('status') == 'Success':
                            outputs.append(target['file_name'] + '_transcript')
                        response = response.get('message')
                if workflow.get('action') == 'read':
                    if target == 'source':
                        #target as source (for now) being initial trigger file ... 
                        target = outputs[-1]
                        command = {"name": "read", "args": {"name": target}}
                        response = await handle_commands(command, convoID, 0, loadout)
                        outputs.append(response)
                if workflow.get('action') == 'message':
                    response = workflow['content']

                # could possibly just be actions as well ...
                if workflow.get('print'):
                    await handle_message(convoID, response, 'function', '', None,0, meta = 'terminal', function_name='file_handler')
                if workflow.get('return'):
                    await return_to_GPT(convoID, 0)



# dummy_trigger = {
#     {'type':'upload',
#      'target': 'source'
#      },
#      {'type':'transcribe',
#       }
# }

action_modiier = """

    To note
    - B-roll must illustrate the transcript's key events, objects, locations or activities.
    - B-roll must not illustrate specific people or animals named in the transcript.
    - Do not place b-roll in the first 3 seconds of any video.
    - B-roll must appear every 5 seconds and be held for a total of 4 seconds.
    - B-roll must appear on screen 1 second before its prompting word or phrase.

    IMPORTANT : Return the ‘overlay_b_roll’ function immediately upon receiving the transcript.
    IMPORTANT : Do not return b_roll in the first 3 seconds.
    IMPORTANT : All b_roll must be synchronised with its prompting word or phrase.
    IMPORTANT : Do not run ‘overlay_b_roll’ a second time after receiving a result.
    IMPORTANT : Use A b-roll clip at least every 10 seconds, so a one minute video should have at least 6 b-roll clips, and a 30 minute video should have at least 180 b-roll clips.

    """

# idea here being that it runs through in order, so transforms can compound, though can do different like eg async means doesn't wait
dummy_workflows = [
    {
        'trigger':'upload',
        'action':'transcribe',
        'print': True, # add as message to queue
        'return': False # send to gpt (ends cycle) 
     },
     {
        'trigger': 'transcribe',
        'action' : 'read',
        'print': True, # add as message to queue
        'return': False # send to gpt (ends cycle)
     },
     {
        'trigger': 'read',
        'action' : 'message',
        'content' : action_modiier,
        'print': True, # add as message to queue
        'return': True # send to gpt (ends cycle) 
        # maybe assumption here is that actually thats handled like any function
      }

]
