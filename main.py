import asyncio
import sys
from google_api import google_api

# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    try:
        client = google_api()
        await client.auth("photoslibrary.readonly")
        data = await client.request("mediaItems","photoslibrary.readonly")
        print(data)
    finally:
        await client.close_session()


asyncio.run(main())
