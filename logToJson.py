import json
import os
import io

directory = './chatlogs/'

convoDict = []

for filename in os.listdir(directory):
    f = os.path.join(directory, filename)
    print(f)
    convo = io.open(f, encoding="utf8").read()
    date = filename.split('.')[0]
    # file = open('./chatlogs/' + filename)
    convoObject = {"date": date, "summary": "", "log": convo}
    convoDict.append(convoObject)

print(convoDict)
summaries = io.open('./summary1.txt', encoding="utf8").readlines()
for line in summaries:
    date = line.split('.')[0]
    summary = line.split('- ')[1]
    lastdiff = int()
    for convo in convoDict:
        print(convo['date'] + ' ' + date)
        try:
            diff = abs(int(convo['date']) - int(date))
        except:
            print('diff didnt work')
        print(diff)
        if diff < lastdiff:
            lastdiff = diff
            convo['summary'] = summary
        if convo['date'] == date:
            convo['summary'] = summary

with open("./logs.json", "a") as convoJson:
    json.dump(convoDict, convoJson)
