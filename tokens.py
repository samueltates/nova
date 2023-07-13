from prismaHandler import prisma
from prisma import Json
import json
import datetime
from appHandler import app, websocket
from debug import eZprint

async def handle_token_use(userID, model, input_tokens, output_tokens):
    dollars_per_NovaCoin = 0.04 # As 250 Nova Coin equals to $10


    if model.lower() == 'gpt-4':
        coin_cost = ((input_tokens / 1000) * 0.03) / dollars_per_NovaCoin
        coin_cost += ((output_tokens / 1000) * 0.06) / dollars_per_NovaCoin
    elif model.lower() == 'gpt-4-32k':
        coin_cost = ((input_tokens / 1000) * 0.06) / dollars_per_NovaCoin
        coin_cost += ((output_tokens / 1000) * 0.12) / dollars_per_NovaCoin
    elif model.lower() == 'gpt-3.5-turbo':
        coin_cost = ((input_tokens / 1000) * 0.0015) / dollars_per_NovaCoin
        coin_cost += ((output_tokens / 1000) * 0.002) / dollars_per_NovaCoin
    elif model.lower() == 'gpt-3.5-turbo-16k':
        coin_cost = ((input_tokens / 1000) * 0.003) / dollars_per_NovaCoin
        coin_cost += ((output_tokens / 1000) * 0.004) / dollars_per_NovaCoin
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
        # print(blob)

        if 'tokens_available' in blob and 'tokensUsed' in blob:
            # print('tokens available found')
            if blob['tokens_available'] - blob['tokensUsed'] > 0:

                return True
            else:
                await websocket.send(json.dumps({'event':'tokens_left', 'tokens_left':  blob['tokens_available'] - blob['tokensUsed']}))
                return False
    else:
        return True
            
    # await websocket.send(json.dumps({'event':'tokens_left', 'tokens_left': 0}))
            

async def update_coin_count(userID, coins_used):
    # print('update coin count called')
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )

    tokens_left = 0
    if user:
        blob = json.loads(user.json())['blob']
        # print(blob)
        if 'tokensUsed' in blob:
            blob['tokensUsed'] += coins_used
        else:
            blob['tokensUsed'] = coins_used

        if 'tokens_available' in blob:
            # print('tokens available found')
            tokens_left = blob['tokens_available'] - blob['tokensUsed']
        else:
            print('tokens available not found')
            blob['tokens_available'] = 100 
            tokens_left = 100

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




