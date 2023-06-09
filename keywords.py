from debug import eZprint
import asyncio
from prismaHandler import prisma
import json

async def get_keywords():
    summaries = await prisma.summary.find_many(
        where={ 
            "UserID": '110327569930296986874'
        },
    )

    keywords_available = {}
    notes_available = {}

    for summary in summaries:
        blob = json.loads(summary.json())['blob']
        for key, val in blob.items():
            if val['summarised'] == False:
                # # print(summary)
                keywords = val['keywords']
                for keyword in keywords:
                    if keyword not in keywords_available:
                        keywords_available[keyword] = []
                    keywords_available[keyword].append({'title':val['title'], 'body':val['body'],'sourceID':summary.id})
                

                for key in val.keys():
                    if key == 'key' or key == 'overview' or key == 'timestamp' or key == 'first-doc' or key == 'last-doc' or key == 'body' or key == 'title' or key == 'meta' or key == 'epoch':
                        continue
                    if key not in notes_available:
                        print('creating record for ' + key+ '\n')
                        notes_available[key] = []
                    if isinstance(val[key], str):
                        print('adding line ' + val[key] + ' to ' + key + '\n')
                        notes_available[key].append({'line':val[key], 'timestamp': val['timestamp'], 'sourceID':summary.id} )
                    elif isinstance(val[key], dict):
                        for subKey, subVal in val[key].items():
                            if subKey == 'key' or subKey == 'overview' or subKey == 'timestamp' or subKey == 'first-doc' or key == 'last-doc' or subKey == 'body' or subKey == 'title' or subKey == 'meta' or subKey == 'epoch' or subKey == ' notes' or subKey == 'insights':
                                continue
                            if subKey not in notes_available:
                                print('creating record for ' + subKey + '\n')
                                notes_available[subKey] = []
                            print('adding sub line ' + subVal + ' to ' + subKey+ '\n' )

                            notes_available[subKey].append({'line':subVal, 'timestamp':val['timestamp'], 'sourceID':summary.id})
          
    print('keywords')
    for keywords in keywords_available:
        print('--'+keywords)
        for keyword in keywords_available[keywords]:
            print(keyword['title'] + ': ' + keyword['body'])
      
    # print('notes')
    for key, val in notes_available.items():
        print('--'+key) 
        for note in val:
            print(note['line'] + ' from ' + str(note['sourceID']) + ' at ' + str(note['timestamp']))


async def main() -> None:
    await prisma.connect()
    eZprint('running main')
    await get_keywords()

if __name__ == '__main__':
    asyncio.run(main())