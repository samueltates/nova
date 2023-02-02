import os
import openai
import json

from http.server import BaseHTTPRequestHandler

openai.api_key = "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"

runningPrompts = dict()
availableCartridges = dict()
allLogs = dict()
responses = dict()
logs = dict()
userName = "sam"
agentName = "nova"


# def parseCartridgeAction(action):
#     print('parse cartridge action  ' + action['action'])
#     print(runningPrompts)
#     match action["action"]:
#         case "get":
#             print('get prompt triggered')
#             initialiseCartridges()
#             loadCartridges(action)
#         case "set":
#             print('set prompt triggered')
#             print(action)
#             updateCartridges(action)
#         case _:
#             initialiseCartridges()
#             loadCartridges(action)


def initialiseCartridges():
    path = 'cartridges.json'
    if os.path.exists(path) is False:
        cartridges = {'cartridge':
                      {'label': 'starter',
                       'type': 'prompt',
                       'description': 'a text only prompt that gives an instruction',
                       'prompt': 'Nova and Sam are working together to make art, stories and tools.',
                       'stops': ['Nova:', 'Sam:'],
                       'enabled': 'true'}
                      }
        with open("cartridges.json", "a") as cartridgesBox:
            json.dump(cartridges, cartridgesBox)


def loadCartridges(input):
    with open("cartridges.json", "r") as cartridgesBox:
        availableCartridges.setdefault(
            input['UUID'], json.load(cartridgesBox))
        for cartKey, cartVal in availableCartridges[input['UUID']].items():
            print('printing cartridges in first format')
            print(cartKey, cartVal)
            if cartVal['enabled']:
                runningPrompts.setdefault(input['UUID'], []).append(
                    {cartKey: cartVal})
    print(runningPrompts)
    print('load cartridges complete')
    # print(runningPrompts)


def parseInput(input):
    # here it handles the UIID / persistence and orchestrates the convo
    print('parse input')
    match input["action"]:
        case "getPrompts":
            print('get prompts triggered')
            initialiseCartridges()
            loadCartridges(input)
        case "sendInput":
            print('send input triggered')
            print(input)
            updateCartridges(input)
            logs.setdefault(input['UUID'], []).append(
                {"name": userName,
                 "message": input['message']
                 })
            sendPrompt(input['UUID'])
        case "addCartridge":
            print('add cartridge triggered')

            # issue or concern here is that i'm basically replacing the whole array, this is due to the fact that i'm making all prompts editable fields, so when you send the message it just sends with that prompt. So basicaly no confirmation state in prompts, so interface really is where its stored. Only difference in 'data driven' is that updates from UI go direct to the python server, but whats the point? So really python just ingests the data, but its mostly held in the front end? Not sure.


def updateCartridges(input):
    print('updating cartridges')
    runningPrompts[input['UUID']] = input['prompts']
    print(runningPrompts)


def addCartridge(input):
    print('adding cartridge')
    # idea here is to detect when new cartridge is added, and if it is a function then handle it
    match input['type']:
        case "function":
            runFunction(input)


def runFunction(input):
    print('running function')


def runMemory(input):
    print('running memory')
    with open("logs.json", "a") as logsJson:
        allLogs.setdefault(
            input['UUID'], json.load(logsJson))
        for log in allLogs[input['UUID']]:
            print(log)


def sendPrompt(UUID):

    promptString = ""
    print("sending prompt")
    print(runningPrompts)
    for promptObj in runningPrompts[UUID]:
        print('found prompt, adding to string')
        print(promptObj)
        promptString += " "+promptObj['cartridge']['prompt']+"\n"

    for chat in logs[UUID]:
        promptString += " "+chat['name']+": "+chat['message']+"\n"

    print("prompt string")
    print(promptString)

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=promptString,
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.6,
        stop=[" Sam:", " Nova:"]
    )

    print(response)
    logs.setdefault(UUID, []).append(
        {"name": agentName,
         "message": response["choices"][0]["text"]})
    # parseResponse(UUID)
    # return "wow great point"
    # parseResponse("wow great point")


def parseResponse(UUID):
    # this is being parsed in parse input, doesn;'t need to be a return
    logs.setdefault(UUID, []).append(
        {"name": agentName,
         "message":  "wow great point"})

    # logs.setdefault(UUID, []).append(responses[UUID]["choices"][0]["text"])
