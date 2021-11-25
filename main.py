import asyncio
import aiohttp
import aiofiles
import sys
import json
import os
import requests
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

        try:
            with open(auth_file) as auth_file_contents:
                auth_file_contents = json.load(auth_file_contents)
            self.client_id = auth_file_contents["installed"]["client_id"]
            self.client_secret = auth_file_contents["installed"]["client_secret"]
            self.refresh_token = auth_file_contents["refresh_token"]
            self.refresh_client()
        except:
            SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
            API_SERVICE_NAME = 'photoslibrary'
            API_VERSION = 'v2'
            CLIENT_SECRETS_FILE = auth_file
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            auth = flow.run_console()
            self.client_id = auth._client_id
            self.client_secret = auth._client_secret
            self.refresh_token = auth._refresh_token
            self.access_token = auth.token
            self.expire_timestamp = datetime.timestamp(auth.expiry)
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            with open(auth_file) as auth_file_contents:
                auth_file_contents = json.load(auth_file_contents)
                auth_file_contents["refresh_token"] = self.refresh_token
            with open(auth_file,"w") as auth_file_contents_out:
                json.dump(auth_file_contents,auth_file_contents_out,indent=3)

    def refresh_client(self):
        headers = {
            "client_id":self.client_id,
            "client_secret":self.client_secret,
            "code":self.refresh_token,
            "grant_type":"authorization_code"
        }
        resp = requests.post("https://oauth2.googleapis.com/token",headers=headers).json()
        print(resp)
        self.access_token = resp["access_token"]
        self.expire_timestamp = resp["expires_in"]

    async def list_albums(self):
        headers = {"Authorization":"Bearer "+self.access_token}
        async with self.session.get("https://photoslibrary.googleapis.com/v1/albums",headers=headers) as resp:
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