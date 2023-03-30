from prisma import Prisma
from prisma import Json
import asyncio
import json
from gptindex import queryIndex, indexGoogleDoc
import nova



prisma = Prisma()
def main() -> None:
    asyncio.run(fakeIndexQuerier())


async def fakeindexCreator():
    indexGoogleDoc('sam',['1r7a23KY8gbvMT3wtkV-Q9iiINVWGXk8igp-uWgpd0no'],'creativeSession')


async def fakeIndexQuerier():
    await prisma.connect()
    cartridge = await prisma.cartridge.find_first(
        where={ "id": 62 }
    )
    dbRecord = json.loads(cartridge.json())
    # print (dbRecord)
    localCartridge = dbRecord['blob']
    for cartKey, cartVal in localCartridge.items():
        index = cartVal['index']

    nova.eZprint('printing fake cartridge loader index')
    print(index)
    queryIndex ('what are the key points in this text', index)


   
if __name__ == '__main__':
    main()

