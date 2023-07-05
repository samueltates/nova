from prismaHandler import prisma
from prisma import Json
import json

import datetime
async def GoogleSignOn(userInfo, token):
    userRecord = await prisma.user.find_first(
        where={
            'UserID': userInfo['id']
        }
    )
    if(userRecord):
        blob = json.loads(userRecord.json())['blob']
        blob['credentials'] = token.to_json()
        foundUser = await prisma.user.update(
            where={
                'id': userRecord.id
            },
            data= {
                'blob': Json(blob)
            }
        )
        return foundUser
    else:
        newUser = await prisma.user.create(
            data= {
                'UserID': userInfo['id'],
                'name': userInfo['given_name'],
                'blob': Json({'credentials': token.to_json()})
            }
        )
        return newUser


async def addAuth(userID, credentials):
    print(credentials.to_json())
    credentials = await prisma.user.create(
        data= {
            'UserID': userID,
            'name': 'sam',
            'blob': Json({'credentials': credentials.to_json()})
        }
    )
    return credentials

async def getAuth(userID):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    print(user)
    if(user): 
        parsedUser = json.loads(user.json())
        print(parsedUser)
        parsedCred = dict()
        parsedCred = json.loads(parsedUser['blob']['credentials'])
        return parsedCred
    else:
        return None

async def updateAuth(userID, credentials):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    print(user)
    if(user):
        foundUser = await prisma.user.update(
            where={
                'id': user.id
            },
            data= {
                'blob': Json({'credentials': credentials.to_json()})
            }
        )
        return user

