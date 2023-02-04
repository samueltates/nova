import os
import openai
import json
import asyncio
from prisma import Prisma

import datetime


from http.server import BaseHTTPRequestHandler

openai.api_key = "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"

runningPrompts = dict()
availableCartridges = dict()
allLogs = dict()
responses = dict()
logs = dict()
userName = "sam"
agentName = "nova"
functionsRunning = 0
prisma = Prisma()


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


def parseInput(input):
    # here it handles the UIID / persistence and orchestrates the convo
    print('parse input')
    match input["action"]:
        case "getPrompts":
            print('get prompts triggered')
            initialiseCartridges()
            loadCartridges(input)
            functionsRunning = 1
        case "sendInput":
            print('send input triggered')
            print(input)
            updateCartridges(input)
            asyncio.run(logMessage(input['UUID'], userName, input['message']))
            logs.setdefault(input['UUID'], []).append(
                {"name": userName,
                 "message": input['message']
                 })
            constructChatPrompt(input['UUID'])
        case "addCartridge":
            print('add cartridge triggered')

            # issue or concern here is that i'm basically replacing the whole array, this is due to the fact that i'm making all prompts editable fields, so when you send the message it just sends with that prompt. So basicaly no confirmation state in prompts, so interface really is where its stored. Only difference in 'data driven' is that updates from UI go direct to the python server, but whats the point? So really python just ingests the data, but its mostly held in the front end? Not sure.


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
    print('load cartridges complete')
    asyncio.run(runMemory(input))

    # print(runningPrompts)


def updateCartridges(input):
    print('updating cartridges')
    runningPrompts[input['UUID']] = input['prompts']


def addCartridge(input):
    print('adding cartridge')
    # idea here is to detect when new cartridge is added, and if it is a function then handle it
    match input['type']:
        case "function":
            runFunction(input)


# def runFunction(input):
#     print('running function')


def sendPrompt(promptString):
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
    return response


def constructChatPrompt(UUID):

    promptString = ""
    print("sending prompt")
    print(runningPrompts)
    for promptObj in runningPrompts[UUID]:
        print('found prompt, adding to string')
        print(promptObj)
        promptString += " "+promptObj['cartridge']['prompt']+"\n"

    for chat in logs[UUID]:
        promptString += " "+chat['name']+": "+chat['message']+"\n"

    promptString += " "+agentName+": "
    print("prompt string")
    print(promptString)
    response = sendPrompt(promptString)
    print(response)
    asyncio.run(logMessage(UUID, userName, response["choices"][0]["text"]))

    logs.setdefault(UUID, []).append(
        {"name": agentName,
         "message": response["choices"][0]["text"]})


async def logMessage(UUID, name, message):
    functionsRunning = 1
    await prisma.connect()

    print('logging message')
    message = await prisma.message.create(
        data={
            "SessionID": UUID,
            "name": name,
            "UserID": 'Sam',
            "timestamp": datetime.datetime.now(),
            "body": message,
        }
    )
    await prisma.disconnect()

    functionsRunning = 0


async def runMemory(input):
    await prisma.connect()
    print('running memory')
    logs = await prisma.log.find_many()
    summaryStringChunks = [""]
    id = 0
    allLogs.setdefault(
        input['UUID'], logs)
    for log in allLogs[input['UUID']]:
        print('printing log from database, summary is:')
        # print(log)
        print(log.summary)
        if (len(summaryStringChunks[id]) > 5000):
            summaryStringChunks.append("")
            id += 1
        summaryStringChunks[id] += "On date: " + \
            log.date+" "+log.summary + "\n"

        if (log.summary == "" or log.summary == ''):
            print('no summary, getting summary from OPENAI')
            log.summary = getSummary(log.body)
            print('summary is: '+log.summary)
            updatedLog = await prisma.log.update(
                where={'id': log.id},
                data={'summary': log.summary}
            )

    functionsRunning = 0

    overallSummary = ""
    for summaryStrings in summaryStringChunks:
        print(summaryStrings)
        overallSummary += getSummary(summaryStrings)

    print(overallSummary)
    summaryCartridge = {'label': 'starter',
                        'type': 'prompt',
                        'description': 'a text only prompt that gives an instruction',
                        'prompt': overallSummary,
                        'stops': ['Nova:', 'Sam:'],
                        'enabled': 'true'}
    runningPrompts.setdefault(input['UUID'], []).append(
        {'cartridge': summaryCartridge})

    await prisma.disconnect()


def getSummary(textToSummarise):
    initialPrompt = "Summarise this text as succintly as possible to retain as much information that CHAT GPT can use to reference the conversation:"
    stopString = "\n Summary:"
    prompt = initialPrompt + textToSummarise
    response = sendPrompt(prompt)
    return response["choices"][0]["text"]
