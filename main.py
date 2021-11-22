import asyncio
import aiohttp
import sys

# set the event policy to windows if the user is using windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    print("go")

asyncio.run(main())