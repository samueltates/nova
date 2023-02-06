import os
import openai
import json
import asyncio

from prisma import Prisma

from datetime import date, datetime


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


#  def startSession(input):
#     functionsRunning = 1
#     print('starting session')
#     log = await prisma.log.create(
#         data={
#             "SessionID": input['UUID'],
#             "timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
#             "name": input['name'],
#             "UserID": 'Sam',
#         }
#     )
#     functionsRunning = 0


async def runMemory(input):
    await prisma.connect()
    print('running memory')
    log = await prisma.log.create(
        data={
            "SessionID": input['UUID'],
            "UserID": 'Sam',
            "date": datetime.now().strftime("%Y%m%d%H%M%S"),
            "summary": "",
            "body": "",
            "batched": False,
        }
    )

    print('log created for session')

    logs = await prisma.log.find_many()
    logSummaryBatches = []
    overallSummary = ""
    id = 0
    allLogs.setdefault(
        input['UUID'], logs)
    for log in allLogs[input['UUID']]:

        # Checks if log has summary, if not, gets summary from OPENAI
        if (log.summary == "" or log.summary == ''):
            print('no summary, getting summary from OPENAI')

            logID = log.SessionID
            messageBody = ""
            messages = await prisma.message.find_many(
                where={'SessionID': logID})
            print(messages)
            messageBody += "Chat on " + messages[0].date + "\n"

            for messsage in messages:
                messageBody += "timestamp:\n"+messageBody.timestamp + \
                    "message: \n" + messsage.body + "\n"
            print(messageBody)
            log.body = messageBody
            log.summary = getSummary(messageBody)
            print('summary is: '+log.summary)
            updatedLog = await prisma.log.update(
                where={'id': log.id},
                data={'summary': log.summary,
                      'body': log.body
                      }
            )
        lastDate = ""
        # Checks if log has been batched, if not, adds it to the batch
        if (log.batched == False):
            print('printing log from database, summary is:' + log.summary)
            logSummaryBatches.append(
                {'startDate': "", 'endDate': "", 'summaries': ""})
            # print(log)
            print(log.summary)
            print(logSummaryBatches)
            if (logSummaryBatches[id]['startDate'] == ""):
                logSummaryBatches[id]['startDate'] = log.date
            if (len(logSummaryBatches[id]['summaries']) > 2000):
                print('batch is too long, creating new batch')
                logSummaryBatches[id]['endDate'] = lastDate
                log.batched = True
                updatedLog = await prisma.log.update(
                    where={'id': log.id},
                    data={'summary': log.summary,
                          'body': log.batched
                          }
                )
                id += 1
            logSummaryBatches[id]['summaries'] += "On date: " + \
                log.date+" "+log.summary + "\n"
            lastDate = log.date

    functionsRunning = 0

    # summarises each batch if that isn't summarised, and adds to summary
    # how do we know if the batch has been created and summarised
    # so a batch is only being created if there's lots of logs, and then it's being summarised
    # the 'stored' batch summaries shouldn't overlap with the new batch summaries
    # so will need to add the new batch summaries to remote, access those, then add the unbatched logs -
    # will also need to check remote and any batches that get too big .. wll need to be batched... I'm confused

    runningBatchedSummaries = ""
    runningBatches = []
    latestLogs = ""
    batchRangeStart = ""
    batchRangeEnd = ""
    multiBatchSummary = ""

    remoteBatches = await prisma.batch.find_many()
    if (len(remoteBatches) > 0):
        print('remote batches found ')
        for batch in remoteBatches:
            if (batch.batched == False):
                batchRangeStart = batch.dateRange.split(":")[0]
                runningBatches.append(batch)
                runningBatchedSummaries += batch.summary

    for batch in logSummaryBatches:
        if (batch['endDate'] == ""):
            latestLogs = batch['summaries']
            break
        print(batch)
        if (batchRangeStart == ""):
            batchRangeStart = batch['startDate']
        batchSummary = getSummary(batch['summaries'])
        runningBatchedSummaries += batchSummary
        runningBatches.append(batch)
        print('batch summary is: ' + batchSummary)

        batchRemote = await prisma.batch.create(
            data={'dateRange': batch['startDate']+":" + batch['endDate'],
                  'summary': batchSummary, 'batched': False, })

        if runningBatchedSummaries > 1000:
            print('batch is too long, creating new batch')
            summaryRequest = "between " + batchRangeStart + " and " + \
                batchRangeEnd + " " + runningBatchedSummaries

            multiBatchSummary += getSummary(summaryRequest)
            batchRangeEnd = batch['endDate']

            batchBatch = await prisma.batch.create(
                data={'dateRange': batch['startDate']+":" + batch['endDate'],
                      'summary': multiBatchSummary, 'batched': False, })

            for batch in runningBatches:
                updateBatch = await prisma.batch.update(
                    data={'batched': True, })

            runningBatchedSummaries = ""
            runningBatches = []

    overallSummary = "previously:" + multiBatchSummary + "more recently" + \
        runningBatchedSummaries + "and most recently" + latestLogs

    print("overall summary is: " + overallSummary)
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
