import os
import openai
from datetime import date, datetime
import atexit
import json

from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        print("in python function")
        # print(recieved)
        initialiseCartridges()
        loadCartridges()
        data = self.rfile

        # gets body from message, needs length of file and reads that length
        # not sure why this is so it doesn't go forever I guess
        content_len = int(self.headers['content-length'])
        post_body = self.rfile.read(content_len)
        post_body_py = json.loads(post_body)
        parseInput(post_body_py['message'])
        # recieved = json.load(self)
        # print(data)
        chatLog = json.dumps(log)

        content = bytes(chatLog, 'utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)
        return content


openai.api_key = "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"

runningPrompts = dict()
availableCartridges = dict()
log = []
userName = ""
agentName = ""


def initialiseCartridges():
    path = 'cartridges.json'
    if os.path.exists(path) is False:
        cartridges = {
            'starter':
                {
                    'prompt': 'Nova and Sam are working together to make art, stories and tools.',
                    'stops': ['Nova:', 'Sam:'],
                    'enabled': 'true'
                }
        }
        with open("cartridges.json", "a") as cartridgesBox:
            json.dump(cartridges, cartridgesBox)


def loadCartridges():
    with open("cartridges.json", "r") as cartridgesBox:
        availableCartridges = json.load(cartridgesBox)
        # print('available cartridges are ,' .join(availableCartridges))

        for cartKey, cartVal in availableCartridges.items():
            if cartVal['enabled']:
                runningPrompts.update({cartKey: cartVal})
            # if cart['enabled']:
            #     print('enabled cartridges are,' + cart)
        # updateUI(availableCartridges)


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
    log.append(userName + ': ' + input)
    sendPrompt()


def parseResponse(response):
    # log.append(response["choices"][0]["text"])
    log.append(response)
    print(log)


def sendPrompt():
    promptString = ""

    for promptKey, promptVal in runningPrompts.items():
        print('found prompt, adding to string')
        print(promptVal['prompt'])
        promptString += promptVal['prompt']

    promptString += ''.join(log)

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
    parseResponse("wow great point")
