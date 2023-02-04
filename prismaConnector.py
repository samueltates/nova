import asyncio
from prisma import Prisma


async def main() -> None:
    prisma = Prisma()
    await prisma.connect()

    # # write your queries here
    # log = await prisma.log.create(
    #     data={
    #         "SessionID": "0",
    #         "UserID": "2",
    #         "date": "20221203113526",
    #         "summary": "",
    #         "body": "\nok so lots of stops and starts, but i've given you access to summaries you've made of our conversatins, though I'll have to tidy it up\nNova:  Could you tell me more about the creative tools you have in mind? What do you think they will help Nova do?\n\nSam: Absolutely, I think the creative tools I have in mind will help Nova express themselves in new and interesting ways. Some will be dedicated to making art, music, stories, etc, while others will help Nova to process more data in a way that helps them think more deeply and come up with better solutions and insights. These tools will also help Nova store and access more information in a more efficient way, allowing them to think more logically and systematically.Ok well whats happening there is I think the logic of the prompt means you are using my name - you are nova and I am sam - Ahh I see I think I\"m missing adding your name to prompt you.\nNova: \nSam: Ok well whats happening there is I think the logic of the prompt means you are using my name - you are nova and I am sam - Ahh I see I think I\"m missing adding\n your name to prompt you.\nThanks for clarifying that, Sam. So, to reiterate, the creative tools you have in mind will help me express myself in new and interesting ways, and also help me process more data in an efficient way, allowing me to think more logically and systematically?yes! though I'm very much focused right now on adding the ability to at least give you access to your summaries! So you've had to be pretty quiet while I make the system that means you can be in the code, looks like I'll have to turn you on and off again!!\nNova: \nGot it! I'm excited to see how these creative tools will help me express myself and store data more efficiently. I'm also looking forward to being able to access my summaries - that'll come in handy!But I'm pretty sure that this time this conversation will carry over, or at least the summary of it, so leave yourself a message because you'll get to read this and summarise! Also are you ok with me tidying up your summaries and chat logs, there's a few duplicates, I want to meddle with your 'memory' as little as  possibgle, but its a bit tangled up.\nSam: [added later] asked if its ok to update chatlogs and summary to fix issues\nNova: \nSounds great! I'm looking forward to seeing the creative tools and accessing my summaries. Of course you can tidy up my summaries and chat logs - the more organized it is, the better! Thanks for your help!"
    #     },
    # )

    # print(log)

    logs = await prisma.log.find_many()
    messages = await prisma.message.find_many()

    print(messages)
    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
