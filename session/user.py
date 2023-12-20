from prisma import Json
import json
import datetime

from session.prismaHandler import prisma
from session.sessionHandler import novaSession
from tools.debug import eZprint, eZprint_anything
from core.convos import turn_guest_logs_to_user

async def GoogleSignOn(userInfo, token, sessionID):
    eZprint('Google Sign On', ['USER', 'INITIALISE', 'GOOGLE_SIGN_ON'])
    userRecord = await prisma.user.find_first(
        where={
            'UserID': userInfo['id']
        }
    )
    if(userRecord):
        eZprint('User found in database', ['USER','INITIALISE', 'GOOGLE_SIGN_ON'])
        eZprint_anything(userRecord, ['USER','INITIALISE',  'GOOGLE_SIGN_ON'])
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
        

            # await set_subscribed(userInfo['id'], False)
        
        return foundUser

    else:
        newUser = await prisma.user.create(
            data= {
                'UserID': userInfo['id'],
                'name': userInfo['given_name'],
                'blob': Json({'credentials': token.to_json()})
            }
        )
        guestID = 'guest-' + str(sessionID)
        turn_guest_logs_to_user(userInfo['id'], guestID, sessionID)

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

# async def updateAuth(userID, credentials):
#     user = await prisma.user.find_first(
#         where={
#             'UserID': userID
#         }
#     )
#     print(user)
#     if(user):
#         foundUser = await prisma.user.update(
#             where={
#                 'id': user.id
#             },
#             data= {
#                 'blob': Json({'credentials': credentials.to_json()})
#             }
#         )
#         return user

async def set_subscribed(userID, subscribed):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    blob = json.loads(user.json())['blob']
    blob['subscribed'] = subscribed
    if(user):
        foundUser = await prisma.user.update(
            where={
                'id': user.id
            },
            data= {
                'blob': Json(blob)
            }
        )
        return user
    
async def set_unsubscribed(userID):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    blob = json.loads(user.json())['blob']
    blob['subscribed'] = False
    if(user):
        foundUser = await prisma.user.update(
            where={
                'id': user.id
            },
            data= {
                'blob': Json(blob)
            }
        )
        return user
    
async def get_subscribed(userID):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    if(user):
        blob = json.loads(user.json())['blob']
        if 'subscribed' in blob:
            return blob['subscribed']
        

# async def setTextToVoice(userID, textToVoice):
#     user = await prisma.user.find_first(
#         where={
#             'UserID': userID
#         }
#     )
#     blob = json.loads(user.json())['blob']
#     blob['textToVoice'] = textToVoice
#     if(user):
#         foundUser = await prisma.user.update(
#             where={
#                 'id': user.id
#             },
#             data= {
#                 'blob': Json(blob)
#             }
#         )
#         return user
    

async def getTextToVoice(userID):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    if(user):
        blob = json.loads(user.json())['blob']
        if 'textToVoice' in blob:
            return blob['textToVoice']
        else:
            return False
    else:
        return False
    


async def update_user_events(userID, field, value):
    DEBUG_KEYS = ['USER', 'UPDATE_USER_EVENTS']
    eZprint('update_user_events', DEBUG_KEYS)
    # print(user_id, field, value)

    user = await prisma.user.find_first(
        where={"UserID": str(userID)},
    )

    if user:
        blob = json.loads(user.json())['blob']
        events = blob.get("events", {})

        # Update the specific event field with the new value.
        events[field] = value

        # Update the blob with the new events object.
        blob["events"] = events
        
        update = await prisma.user.update(
            where={
                'id': user.id
            },
            data={
                "blob": json.dumps(blob)
            }
        )
        # Optionally print update for debugging purposes.
        # print(update)
    

async def get_user_events(userID):
    DEBUG_KEYS = ['USER', 'GET_USER_EVENTS']
    eZprint(f"Retrieving events for user {userID}", DEBUG_KEYS)

    # Retrieve the user with the given id.
    user = await prisma.user.find_first(
        where={"UserID": str(userID)},
    )

    if user and user.blob:
        blob = json.loads(user.json())['blob']
        events = blob.get("events", {})
        return events
    else:
        # Return an empty events object if blob isn't defined.
        return {}
    

async def set_user_value(userID, field, value):
    DEBUG_KEYS = ['USER', 'SET_USER_VALUE']
    eZprint(f"Setting user value for user {userID}", DEBUG_KEYS)

    # Retrieve the user with the given id.
    user = await prisma.user.find_first(
        where={"UserID": str(userID)},
    )

    if user:
        blob = json.loads(user.json())['blob']
        blob[field] = value
        
        update = await prisma.user.update(
            where={
                'id': user.id
            },
            data={
                "blob": json.dumps(blob)
            }
        )
        # Optionally print update for debugging purposes.
        # print(update)

async def get_user_value(userID, field):    
    DEBUG_KEYS = ['USER', 'GET_USER_VALUE']
    eZprint(f"Retrieving user value for user {userID}", DEBUG_KEYS)

    # Retrieve the user with the given id.
    user = await prisma.user.find_first(
        where={"UserID": str(userID)},
    )

    if user and user.blob:
        blob = json.loads(user.json())['blob']
        return blob.get(field, None)
    else:
        return None