import asyncio
import aiohttp
import aiofiles
import sys
import json
import os
from datetime import datetime
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

# set the event policy to windows if the user is using windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class google_photos():
    def __init__(self,auth_file):
        self.session = aiohttp.ClientSession()

        SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
        API_SERVICE_NAME = 'photoslibrary'
        API_VERSION = 'v2'
        CLIENT_SECRETS_FILE = auth_file
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        self.auth = flow.run_console()
        self.refresh_token = self.auth._refresh_token
        self.access_token = self.auth.token
        self.expire_timestamp = datetime.timestamp(self.auth.expiry)
        self.headers = {"Authorization":"Bearer "+self.access_token}
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

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
        client = google_photos("auth.json")
        print(await client.list_albums())
    finally:
        await client.close_session()

asyncio.run(main())