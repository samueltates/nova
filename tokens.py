from prismaHandler import prisma
from prisma import Json
import json
import datetime
from appHandler import app, websocket
from debug import eZprint

async def handle_token_use(userID, model, input_tokens, output_tokens):
    total_tokens = input_tokens + (2 * output_tokens)

    if model.lower() == 'gpt-4':
        coin_cost = (total_tokens / 1000) * 2.5
    elif model.lower() == 'gpt-3.5':
        coin_cost = (total_tokens / 1000) * 0.125
    elif model.lower() == 'gpt-3.5-turbo':
        coin_cost = (total_tokens / 1000) * 0.125
    else:
        raise ValueError('Invalid model name')

    await update_coin_count(userID, coin_cost)

async def check_tokens(userID):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )

    if user:
        blob = json.loads(user.json())['blob']
        print(blob)
       
        if 'tokens_available' in blob:
            print('tokens available found')
            if blob['tokens_available'] > 0:
                return True
            else:
                return False
            
    # await websocket.send(json.dumps({'event':'tokens_left', 'tokens_left': 0}))
            

async def update_coin_count(userID, coins_used):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )

    tokens_left = 0
    if user:
        blob = json.loads(user.json())['blob']
        print(blob)
        if 'tokensUsed' in blob:
            blob['tokensUsed'] += coins_used
        else:
            blob['tokensUsed'] = coins_used

        if 'tokens_available' in blob:
            print('tokens available found')
            tokens_left = blob['tokens_available'] - blob['tokensUsed']
        else:
            print('tokens available not found')
            blob['tokens_available'] = 250 
            tokens_left = 250

        foundUser = await prisma.user.update(
            where={
                'id': user.id
            },
            data= {
                'blob': Json(blob)
            }
        )

    await  websocket.send(json.dumps({'event':'tokens_left', 'tokens_left': tokens_left}))

    return tokens_left




