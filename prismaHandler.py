from prisma import Prisma
prisma = Prisma()
import logging
logging.basicConfig()


async def prismaConnect():
    await prisma.connect()
    # logging.getLogger('prisma').setLevel(logging.DEBUG)
async def prismaDisconnect():
    await prisma.disconnect()
