import os
import openai
from datetime import date, datetime
import atexit

openai.api_key = "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"

start_sequence = "\nNova:"
restart_sequence = "\nSam: "

#creating initial prompt to get summary
starterPrompt = "Nova and Sam are working together to explore ways to make art and stories."
getSummaryPrompt = "\nThis is a summary of conversations created by Nova after reading each conversation:\n"
summaryFile = open('summary.txt')
summary = summaryFile.read()
#loading last convo to create summary - could be saved at end of session instead? Bit less hokey at the start
lastConvoText = ""
chats = os.listdir('./chatlogs/')
ls = []
for chat in chats:
    ls.append(chat)
    
lastChat = max(ls)
file = open('./chatlogs/'+lastChat)

#constructing prompt to get summary - handles if convo goes over what it can handle, need to make 'get summary' more abstracted
makeSummaryPrompt = "Before the conversation begins, read the last conversation and summarise it, your answer will be added to this prompt."
lastConvoText = file.read()

if len(lastConvoText) < 10000:
    lastConvoPrompt = "\nOur last conversation went like this : \n" + lastConvoText + " \nplease summarise it as succintly as possible. "
    getSummaryPrompt = "\nThis is a summary of conversations created by Nova after reading each conversation:\n"

    aiStarter = "\nNova: "

    runningPrompt = starterPrompt + getSummaryPrompt + makeSummaryPrompt + lastConvoPrompt + aiStarter
    print ('\n-----------------\n Chat Summary Prompt Sent : \n' + runningPrompt + '\n-----------------\n')

    #sending prompt
    response = openai.Completion.create(
    model="text-davinci-003",
    prompt = runningPrompt,
    temperature=0.9,
    max_tokens=150,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0.6,
    stop=[" Sam:", " Nova:"]
    )

    answer = '\n'+lastChat+"-"+response["choices"][0]["text"]
    summaryFile = open('summary.txt','a')
    summaryFile.write(answer)
    summaryFile.close()

    print(aiStarter+answer)


else: 
    n = len(lastConvoText)
    firstHalf = ""
    secondHalf = ""
    if n%2 == 0:
        firstHalf=lastConvoText[0:n//2]
        secondHalf = lastConvoText[n//2:]
    else:
        firstHalf=lastConvoText[0:(n//2+1)]
        secondHalf = lastConvoText[(n//2+1):]
        
    lastConvoPrompt = "\nOur last conversation was long, the first half was  : \n" + firstHalf + " \nplease summarise it as succintly as possible. "
    getSummaryPrompt = "\nThis is a summary of conversations created by Nova after reading each conversation:\n"

    aiStarter = "\nNova: "

    runningPrompt = starterPrompt + makeSummaryPrompt + lastConvoPrompt + aiStarter
    print ('\n-----------------\n Chat Summary Prompt Sent : \n' + runningPrompt + '\n-----------------\n')

    #sending prompt
    response = openai.Completion.create(
    model="text-davinci-003",
    prompt = runningPrompt,
    temperature=0.9,
    max_tokens=150,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0.6,
    stop=[" Sam:", " Nova:"]
    )

    answer = '\n'+lastChat+"pt1-"+response["choices"][0]["text"]

    summaryFile = open('summary.txt','a')
    summaryFile.write(answer)
    summaryFile.close()

    lastConvoPrompt = "\nOur last conversation was long, the second half was  : \n" + secondHalf + " \nplease summarise it as succintly as possible. "

    aiStarter = "\nNova: "

    runningPrompt = starterPrompt + makeSummaryPrompt + lastConvoPrompt + aiStarter
    print ('\n-----------------\n Chat Summary Prompt Sent : \n' + runningPrompt + '\n-----------------\n')

    #sending prompt
    response = openai.Completion.create(
    model="text-davinci-003",
    prompt = runningPrompt,
    temperature=0.9,
    max_tokens=150,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0.6,
    stop=[" Sam:", " Nova:"]
    )

    answer = '\n'+lastChat+"pt2-"+response["choices"][0]["text"]

    summaryFile = open('summary.txt','a')
    summaryFile.write(answer)
    summaryFile.close()

    print('\n-----------------\n Summary of last conversation is : \n' + answer + '\n-----------------\n')

id = datetime.now().strftime("%Y%m%d%H%M%S")
chatFilePath = 'chatlogs/' + id + '.txt'

summaryFile = open('summary.txt')
summary = summaryFile.read()

toolAccessOverview = "\nYou can access terminal commands by writing `terminal:` followed by any python function. \nExample syntax would be :\n'terminal:open(filename.txt,a)`\n`terminal:read(filename.txt)`\n`terminal:write('string to be added')`"
conversationStarter = "\nNow you've got the summaries, and terminal access, you can talk to sam, run commands, and make things together. Say something to get started."

runningPrompt = starterPrompt + getSummaryPrompt +'\n'+ summary + toolAccessOverview + conversationStarter + aiStarter

print('\n-----------------\nnew prompt is  ' + runningPrompt)
response = openai.Completion.create(
    model="text-davinci-003",
    prompt = runningPrompt,
    temperature=0.9,
    max_tokens=150,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0.6,
    stop=[" Sam:", " Nova:"]
)

answer = response["choices"][0]["text"]
print(answer)
file = open(chatFilePath,'a')
file.write(aiStarter+answer)
file.close()
runningPrompt+=answer

running = 1

while running == 1:
    file = open(chatFilePath,'a')
    humanInput = input('\nSam: ')
    file.write('\nSam: ' + humanInput)
    runningPrompt+=humanInput+'\nNova: '
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt = runningPrompt,
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.6,
        stop=[" Sam:", " Nova:"]
    )
    answer = response["choices"][0]["text"]
    parsedAnswer = answer.split('`')
    # print('\nparsed answer : \n')
    # print(parsedAnswer)

    commands = []
    for chunk in parsedAnswer:        
        if chunk.startswith('terminal'):
            print('\nterminal command found')
            id = 0
            parsedCommand = chunk.split(':')
            for command in parsedCommand:
                if (id%2) != 0:
                    
                    print('\ncommand is ' + command)
                    try:
                        result = exec(command)
                    except Exception as e: 
                        result=e
                    commands.append('\nterminal:'+command)
                    commands.append('\nresult is')
                    commands.append(result)
                id+=1

    if(len(commands)>0):
        file.write('\nterminal logs')
        runningPrompt+='\nterminal logs'
        for command in commands:
            if(command):
                file.write(command)
                runningPrompt+=command
        runningPrompt+= aiStarter
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt = runningPrompt,
            temperature=0.9,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0.6,
            stop=[" Sam:", " Nova:"]
        )

    
    print('\nNova: ' + answer)
    runningPrompt+=answer
    file.write('\nNova:' + answer)
    file.close()


def exit_handler():
    summariseConvo()

atexit.register(exit_handler)

def summariseConvo():
    global runningPrompt 
    runningPrompt += '\nSam: Ok thanks Nova! Please summarise this conversation as succinctly as possible in a way that will give you the best context later on. This summary will be added to future conversations for context.\nNova: '

    print ('\n-----------------\n SummarisingConvo on quit \n-----------------\n')

    #sending prompt
    response = openai.Completion.create(
    model="text-davinci-003",
    prompt = runningPrompt,
    temperature=0.9,
    max_tokens=150,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0.6,
    stop=[" Sam:", " Nova:"]
    )

    
    id = datetime.now().strftime("%Y%m%d%H%M%S")
    answer = '\n'+id+'-'+response["choices"][0]["text"]

    print('\n-----------------\n Summary of conversation is : \n' + answer + '\n-----------------\n')

    summaryFile = open('summary.txt','a')
    summaryFile.write(answer)
    summaryFile.close()

