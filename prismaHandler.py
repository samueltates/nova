from prisma import Prisma
prisma = Prisma()
import logging
logging.basicConfig()

async def prismaConnect():
    await prisma.connect()
    logging.getLogger('prisma').setLevel(logging.DEBUG)
    # cartridges = await prisma.cartridge.find_many()
