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


async def get_tokens_left(userID):
    eZprint('get tokens left called')
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )

    tokens_left = 0
    if user:
        blob = json.loads(user.json())['blob']
        print(blob)
        month_year = datetime.datetime.now().strftime("%B-%Y")
        if month_year in blob:
            print('month year found')
            if 'tokens_available' in blob[month_year]:
                print('tokens available found')
                tokens_left = blob[month_year]['tokens_available'] - blob[month_year]['tokensUsed']
            else:
                print('tokens available not found')
                tokens_left = 250
        else:
            print('month year not found')
            tokens_left = 250
    await  websocket.send(json.dumps({'event':'tokens_left', 'tokens_left': tokens_left}))

    return tokens_left

async def update_coin_count(userID, coins_used):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )

    tokens_left = 0
    if user:
        blob = json.loads(user.json())['blob']

        month_year = datetime.datetime.now().strftime("%B-%Y")
        if month_year in blob:
            blob[month_year]['tokensUsed'] += coins_used
        else:
            blob[month_year] = {'tokensUsed': coins_used}

        if 'tokens_available' in blob[month_year]:
            print('tokens available found')
            tokens_left = blob[month_year]['tokens_available'] - blob[month_year]['tokensUsed']
        else:
            print('tokens available not found')
            blob[month_year]['tokens_available'] = 250 

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




