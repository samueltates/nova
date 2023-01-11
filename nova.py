import os
import openai
import json

from http.server import BaseHTTPRequestHandler

openai.api_key = "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"

runningPrompts = dict()
availableCartridges = dict()
logs = dict()
userName = "sam"
agentName = "nova"


def parseCartridgeAction(action):

    match action["action"]:
        case "get":
            initialiseCartridges()
            loadCartridges(action)
        case "set":
            print(action)
        case _:
            initialiseCartridges()
            loadCartridges(action)


def initialiseCartridges():
    path = 'cartridges.json'
    if os.path.exists(path) is False:
        cartridges = {'cartridge':
                      {'label': 'starter',
                       'prompt': 'Nova and Sam are working together to make art, stories and tools.',
                       'stops': ['Nova:', 'Sam:'],
                       'enabled': 'true'}
                      }
        with open("cartridges.json", "a") as cartridgesBox:
            json.dump(cartridges, cartridgesBox)


def loadCartridges(action):
    with open("cartridges.json", "r") as cartridgesBox:
        availableCartridges = json.load(cartridgesBox)
        # print('available cartridges are ,' .join(availableCartridges))
        for cartKey, cartVal in availableCartridges.items():
            if cartVal['enabled']:
                runningPrompts.setdefault(action['UUID'], []).append(
                    {cartKey: cartVal})


def addCartridgetoPrompt(cartridge):
    # UI sends string with name, that gets added to prompt
    runningPrompts.update(cartridge)


def removeCartridgeFromPrompt(cartridge):
    # UI sends prompt to dic to remove
    cartridge
    # del runningPrompts("cartridge")


def updateUI():
    # takes available cartridges and displays them
    availableCartridges


def parseInput(input):
    # here it handles the UIID / persistence and orchestrates the convo
    logs.setdefault(input['UUID'], []).append(
        {"name": userName,
         "message": input['message']
         })

    response = sendPrompt()

    logs.setdefault(input['UUID'], []).append(
        {"name": agentName,
         "message": response
         })

# def parseResponse(response):
# this is being parsed in parse input, doesn;'t need to be a return
#     # log.append(response["choices"][0]["text"])
#     log.append(
#         {"name": agentName,
#          "message": response
#          })
#     print(log)


def sendPrompt():
    promptString = ""

    for promptKey, promptVal in runningPrompts.items():
        print('found prompt, adding to string')
        print(promptVal['prompt'])
        promptString += promptVal['prompt']

    # log.map()
    # promptString += ''.join(log)

    # response = openai.Completion.create(
    #     model="text-davinci-003",
    #     prompt = promptString,
    #     temperature=0.9,
    #     max_tokens=150,
    #     top_p=1,
    #     frequency_penalty=0,
    #     presence_penalty=0.6,
    #     stop=[" Sam:", " Nova:"]
    # )

    # parseResponse(response)
    return "wow great point"
    parseResponse("wow great point")
