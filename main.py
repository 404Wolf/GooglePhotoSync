import asyncio
import aiohttp
import aiofiles
import sys
import json

# set the event policy to windows if the user is using windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class googlePhotos():
    def __init__(self,client_id,client_secret,project_id):
        self.client_id = client_id
        self.client_secret = client_secret
        self.project_id = project_id
        self.headers = {
            "client_id":self.client_id,
            "client_secret":self.client_secret,
            "project_id":self.project_id
        }
        self.session = aiohttp.ClientSession()

    async def auth_account(self):
        async with self.session.put("https://www.googleapis.com/auth/photoslibrary.readonly",headers=self.headers) as resp:
            print(await resp.text())

    async def list_albums(self):
        async with self.session.get("https://photoslibrary.googleapis.com/v1/albums",headers=self.headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return resp.status

    async def close_session(self):
        await self.session.close()

async def main():
    with open("auth.json") as auth_file:
        auth_file = json.load(auth_file)

    try:
        client = googlePhotos(auth_file["client_id"],auth_file["client_secret"],auth_file["project_id"])
        await client.auth_account()
        # albums = await client.list_albums()
        # print(albums)

    finally:
        await client.close_session()

asyncio.run(main())