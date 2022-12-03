import os
import openai
from datetime import date, datetime
import atexit


openai.api_key = "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"

start_sequence = "\nNova:"
restart_sequence = "\nSam: "

#creating initial prompt to get summary
starterPrompt = "The following is a conversation between a digital intelligence named nova, and a human named sam. They are working together to make creative tools forto express and help make art and stories."
makeSummaryPrompt = "Before the conversation begins, read the last conversation and summarise it, your answer will be added to this prompt."

#loading last convo to create summary - could be saved at end of session instead? Bit less hokey at the start
lastConvoText = ""
chats = os.listdir('./chatlogs/')
ls = []
for chat in chats:
    ls.append(chat)
lastChat = max(ls)
file = open('./chatlogs/'+lastChat)

#constructing prompt to get summary
lastConvoText = file.read()
lastConvoPrompt = "\nOur last conversation went like this : \n" + lastConvoText + " \nplease summarise it as succintly as possible. "
getSummaryPrompt = "\nThis is a summary of conversations created by Nova after reading each conversation:\n"
conversationStarter = "\nNow you've got the summaries, ask Sam a question to understand what he's working on, see how he's doing, and connect!"
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

id = datetime.now().strftime("%Y%m%d%H%M%S")
chatFilePath = 'chatlogs/' + id + '.txt'
answer = '\n'+id+"-"+response["choices"][0]["text"]

print('\n-----------------\n Summary of last conversation is : \n' + answer + '\n-----------------\n')

summaryFile = open('summary.txt','a')
summaryFile.write(answer)
summaryFile.close()
summaryFile = open('summary.txt')
summary = summaryFile.read()

runningPrompt = starterPrompt + getSummaryPrompt +'\n'+ summary + conversationStarter + aiStarter

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
file.write(answer)
file.close()
runningPrompt+=answer

running = 1

while running == 1:
    file = open(chatFilePath,'a')
    humanInput = input('\nSam: ')
    file.write(humanInput)
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
    print('\nNova: ' + answer)
    runningPrompt+=answer
    file.write('\nNova:' + answer)
    file.close()


def exit_handler():
    summariseConvo()

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

atexit.register(exit_handler)