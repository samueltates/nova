import os
import openai
import json
import asyncio
from pathlib import Path
import os
import sys

path_root = Path(__file__).parents[1]
sys.path.append((str(path_root)))
from prisma import Prisma
# from prisma import Prisma
os.system('prisma generate')
from datetime import datetime
openai.api_key = os.getenv('OPENAIKEY', default=None)

runningPrompts = dict()
availableCartridges = dict()
allLogs = dict()
responses = dict()
logs = dict()
userName = "guest"
agentName = "nova"
functionsRunning = 0
prisma = Prisma()
logCreated = 0

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
    eZprint('parse input')
    if (input["action"] == "getPrompts"):
        eZprint('get prompts triggered')
        initialiseCartridges()
        loadCartridges(input)
        functionsRunning = 1
    if (input["action"] == "sendInput"):
        eZprint('send input triggered')
        print(input)
        updateCartridges(input)
        asyncio.run(logMessage(
            input['sessionID'], input['userName'], input['message']))
        logs.setdefault(input['sessionID'], []).append(
            {"userName": input['userName'],
             "message": input['message']
             })
        constructChatPrompt(input)
    if (input["action"] == "addCartridge"):
        eZprint('add cartridge triggered')

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
            input['sessionID'], json.load(cartridgesBox))
        for cartKey, cartVal in availableCartridges[input['sessionID']].items():
            eZprint('printing cartridges in first format')
            print(cartKey, cartVal)
            if cartVal['enabled']:
                runningPrompts.setdefault(input['sessionID'], []).append(
                    {cartKey: cartVal})
    eZprint('load cartridges complete')
    asyncio.run(runMemory(input))

    # print(runningPrompts)


def updateCartridges(input):
    eZprint('updating cartridges')
    runningPrompts[input['sessionID']] = input['prompts']


def addCartridge(input):
    print('adding cartridge')
    # idea here is to detect when new cartridge is added, and if it is a function then handle it
    # match input['type']:
    #     case "function":
    #         # runFunction(input)


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

    eZprint('promptSent')
    print(response)
    return response


def constructChatPrompt(input):

    promptString = ""
    eZprint("sending prompt")
    eZprint(runningPrompts)
    for promptObj in runningPrompts[input['sessionID']]:
        print('found prompt, adding to string')
        print(promptObj)
        promptString += " "+promptObj['cartridge']['prompt']+"\n"

    for chat in logs[input['sessionID']]:
        promptString += " "+chat['userName']+": "+chat['message']+"\n"

    promptString += " "+agentName+": "
    eZprint(promptString)
    response = sendPrompt(promptString)
    eZprint(response)
    asyncio.run(logMessage(input['sessionID'], agentName,
                response["choices"][0]["text"]))

    logs.setdefault(input['sessionID'], []).append(
        {"userName": agentName,
         "message": response["choices"][0]["text"]})


# async def createNewLog(UUID, userName):
#     await prisma.connect()

#     log = await prisma.log.create(
#         data={
#             "SessionID": UUID,
#             "UserID": userName,
#             "date": datetime.now().strftime("%Y%m%d%H%M%S"),
#             "summary": "",
#             "body": "",
#             "batched": False,
#         }
#     )

#     await prisma.disconnect()


async def logMessage(sessionID, name, message):
    functionsRunning = 1
    await prisma.disconnect()

    await prisma.connect()
    log = await prisma.log.find_first(
        where={'SessionID': sessionID}
    )
    # need better way to check if log or create if not as this checks each message? but for some reason I can't story the variable outside the function
    if log == None:
        log = await prisma.log.create(
            data={
                "SessionID": sessionID,
                "UserID": name,
                "date": datetime.now().strftime("%Y%m%d%H%M%S"),
                "summary": "",
                "body": "",
                "batched": False,
            }
        )

    eZprint('logging message')
    message = await prisma.message.create(
        data={
            "SessionID": sessionID,
            "name": name,
            "UserID": name,
            "timestamp": datetime.now(),
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

def eZprint(string):
    print('\n _____________ \n')
    print(string)
    print('\n _____________ \n')


async def runMemory(input):
    await prisma.disconnect()

    await prisma.connect()
    eZprint('running memory')
    logs = await prisma.log.find_many()
    newLogSummaries = []
    logSummaryBatches = []
    overallSummary = ""
    lastDate = ""
    summaryBatchID = 0

    # unbatchedMessages   = await prisma.message.find_many(
    #     where={'batched': False}
    # )

    # orphanedMessagelogs = [] 
    # currentParentID = ""
    # for message in unbatchedMessages:

    #     if (message.SessionID != currentParentID):
    #         currentParentID = message.SessionID
    #         orphanedMessagelogs.append({message.SessionID : ""})
        
    #     orphanedMessagelogs[message.SessionID] += message.body + " "
        

    
    allLogs.setdefault(
        input['sessionID'], logs)
    for log in allLogs[input['sessionID']]:
        if (input['userID'] == "guest"):
            return
        # Checks if log has summary, if not, gets summary from OPENAI
        if (log.summary == "" or log.summary == ''):
            eZprint('no summary, getting summary from OPENAI')
            sessionID = log.SessionID
            messageBody = ""
            # Gets messages with corresponding ID
            messages = await prisma.message.find_many(
                where={'SessionID': sessionID})
            
            updateMessages = await prisma.message.update(
                where={'SessionID': sessionID},
                data={'batched': True}
            )

            # makes sure messages aren't zero (this should be blocked as log isn't created until first message now)
            if (len(messages) != 0):
                messageBody += "Chat on " + str(messages[0].timestamp) + "\n"

                for message in messages:
                    messageBody += "timestamp:\n"+str(message.timestamp) + \
                        message.name + ":" + message.body + "\n"

                eZprint('printing   messageBody')
                eZprint(messageBody)

                messageSummary = getSummary(messageBody)
                eZprint('summary is: '+messageSummary)
                updatedLog = await prisma.log.update(
                    where={'id': log.id},
                    data={'summary': messageSummary,
                          'body': messageBody
                          }
                )
        # Checks if log has been batched, if not, adds it to the batch
        
    eZprint('starting log batching')

    # theory here but realised missing latest summary I think, so checking the remote DB getting all logs again and then running summary based on if summarised (batched)
    updatedLogs = await prisma.log.find_many()
    for log in updatedLogs:
        if (input['userID'] == "guest"):
            return
        if (log.batched == False):
            eZprint('unbatched log found')

            ############################
            # STARTBATCH - setting start of batch #
            # if no batch, and ID is 0, creates new batch, when ID ticks over this is triggered again as batch ## == ID, until new batch added, etc
            if (len(logSummaryBatches) == summaryBatchID):
                logSummaryBatches.append(
                    {'startDate': "", 'endDate': "", 'summaries': "", 'idList': []})
                logSummaryBatches[summaryBatchID]['startDate'] = log.date
                eZprint('log: ' + str(log.id) + ' is start of batch')
            ############################

            ############################
            # EVERYBATCH - adding actual log sumamry to batch
            # this happens every loop, book ended by start / end
            logSummaryBatches[summaryBatchID]['summaries'] += "On date: " + \
                log.date+" "+log.summary + "\n"
            logSummaryBatches[summaryBatchID]['idList'].append(
                log.id)
            eZprint('added logID: '+str(log.id) + ' batchID: ' + str(summaryBatchID) +
                    ' printing logSummaryBatches')
            # eZprint(logSummaryBatches[summaryBatchID])
            lastDate = log.date
            ############################

            ############################
            # ENDBATCH -- setting end of batch
            if (len(logSummaryBatches[summaryBatchID]['summaries']) > 2000):
                eZprint(' log: '+str(log.id)+' is end of batch')
                logSummaryBatches[summaryBatchID]['endDate'] = lastDate

                # log.batched = True
                # to do this shouldn't be marked as batched till it's been summarised
                # updatedLog = await prisma.log.update(
                #     where={'id': log.id},
                #     data={
                #         'batched': log.batched
                #     }
                # )

                summaryBatchID += 1

    functionsRunning = 0

    # END OF SUMMARY BATCHING AND PRINT RESULTS
    eZprint('END OF SUMMARY BATCHING AND PRINT RESULTS')
    batchID = 0
    for logBatch in logSummaryBatches:
        eZprint('printing batch for batch ID ' +
                str(batchID))
        print(logBatch)
        batchID += 1
    # return
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

    multiBatchRangeStart = ""
    multiBatchRangeEnd = ""

    multiBatchSummary = ""

    remoteBatches = await prisma.batch.find_many()
    eZprint('starting summary batch sumamarisations')

    # checks if there is any remote batches that haven't been summarised
    if (len(remoteBatches) > 0):
        eZprint('remote batches found ')
        for batch in remoteBatches:
            if (batch.batched == False):
                eZprint('remote unsumarised batches found ')
                batchRangeStart = batch.dateRange.split(":")[0]
                runningBatches.append(batch)
                runningBatchedSummaries += batch.summary

    # goes through the new batches of summaries, and summarises them
    for batch in logSummaryBatches:
        if (batch['endDate'] == ""):
            eZprint('no end log batch found so not summarising ')
            latestLogs = batch['summaries']
            break
        if (batchRangeStart == ""):
            batchRangeStart = batch['startDate']
            eZprint('batch with full range found so summarising ')

        eZprint('batch with date range: ' +
                batch['startDate']+":" + batch['endDate'] + ' about to get summarised')

        batchSummary = getSummary(batch['summaries'])
        runningBatchedSummaries += batchSummary + "\n"
        eZprint('batch summary is: ' + batchSummary)
        eZprint('running batched summary is: ' + runningBatchedSummaries)

        batchRemote = await prisma.batch.create(
            data={'dateRange': batch['startDate']+":" + batch['endDate'],
                  'summary': batchSummary, 'batched': False, })

        runningBatches.append(batchRemote)

        # goes through logs that were in that batch and marked as batched (summarised)

        for id in batch['idList']:
            eZprint('session ID found to mark as batched : ' +
                    str(sessionID) + ' id: ' + str(id))
            try:
                updatedLog = await prisma.log.update(
                    where={'id': id},
                    data={
                        'batched': True
                    }
                )
                eZprint('updated log as batched' + str(sessionID))
            except Exception as e:
                eZprint('error updating log as batched' + str(sessionID))
                eZprint(e)

        if len(runningBatchedSummaries) > 1000:
            if (multiBatchRangeStart == ""):
                multiBatchRangeStart = batch['startDate']

            multiBatchRangeEnd = batch['endDate']
            batchRangeEnd = batch['endDate']
            eZprint('summaries of batches ' + batchRangeStart +
                    batchRangeEnd+' is too long, so summarising')

            summaryRequest = "between " + batchRangeStart + " and " + \
                batchRangeEnd + " " + runningBatchedSummaries
            eZprint('summary request is: ' + summaryRequest)

            batchSummary = getSummary(summaryRequest)
            multiBatchSummary += batchSummary

            batchBatch = await prisma.batch.create(
                data={'dateRange': batch['startDate']+":" + batch['endDate'],
                      'summary': batchSummary, 'batched': False, })

            for batch in runningBatches:
                updateBatch = await prisma.batch.update(
                    where={'id': batch.id},
                    data={'batched': True, })

            runningBatchedSummaries = ""
            batchRangeStart = ""
            runningBatches = []

    overallSummary = "Summary of chat log: \n"

    if (multiBatchSummary != ""):
        overallSummary += "Oldest: Between " + multiBatchRangeStart + \
            " & " + multiBatchRangeEnd + " - " + multiBatchSummary + " \n"

    if (runningBatchedSummaries != ""):
        overallSummary += "Recent: Between " + batchRangeStart + \
            " & " + batchRangeEnd + runningBatchedSummaries + " \n"

    if (latestLogs != ""):
        overallSummary += "Most recently" + latestLogs + " \n"

    eZprint("overall summary is: " + overallSummary)
    summaryCartridge = {'label': 'starter',
                        'type': 'prompt',
                        'description': 'a text only prompt that gives an instruction',
                        'prompt': overallSummary,
                        'stops': ['Nova:', 'Guest:'],
                        'enabled': 'true'}

    runningPrompts.setdefault(input['sessionID'], []).append(
        {'cartridge': summaryCartridge})

    await prisma.disconnect()


def welcomeGuest(sessionID, userName):

    promptString = ""
    eZprint("sending prompt")
    eZprint(runningPrompts)
    for promptObj in runningPrompts[sessionID]:
        print('found prompt, adding to string')
        print(promptObj)
        promptString += " "+promptObj['cartridge']['prompt']+"\n"

    response = sendPrompt(promptString)

    eZprint(response)
    asyncio.run(logMessage(sessionID, userName,
                response["choices"][0]["text"]))

    logs.setdefault(sessionID, []).append(
        {"userName": agentName,
         "message": response["choices"][0]["text"]})


def getSummary(textToSummarise):
    initialPrompt = "Summarise this text as succintly as possible to retain as much information that CHAT GPT can use to reference the conversation.\nTEXT TO SUMMARISE:\n"
    stopString = "\n Summary:"
    prompt = initialPrompt + textToSummarise + stopString
    response = sendPrompt(prompt)

    return response["choices"][0]["text"]
