import asyncio
import sys
from types import new_class
from google_api import google_api
import json

# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    with open("output/current.json") as current_save:
        next_page = json.load(current_save)["next_page"]
    with open("output/raw_data.json") as previous_data:
        previous_data = json.load(previous_data)
    data = []

    try:
        # create client object and auth the account for the google photo scope
        client = google_api()
        await client.auth("photoslibrary.readonly")

        i = 0
        firstLapse = True
        while True:
            # attempt page itteration
            try:
                # set up params for api request
                params = {"pageSize": "100"}
                if bool(next_page):
                    params["pageToken"] = next_page

                # request google photos data from google
                data = await client.request(
                    "mediaItems", "photoslibrary.readonly", params=params
                )

                # gather new page key
                next_page = data["nextPageToken"]

                # extract media items
                data = data["mediaItems"]

                if not firstLapse:
                    data = previous_data + data

                firstLapse = False
                previous_data = data

            # page itteration is complete
            except KeyError:
                if "nextPageToken" in data:
                    next_page = data["nextPageToken"]
                else:
                    break

            i += 100
            print("On image #"+str(i))

            # store data to output/raw_data.json file
            with open("output/raw_data.json", "w") as final_data:
                json.dump(data, final_data, indent=3)

    finally:
        # close aiohttp session
        await client.close_session()

        # save status
        with open("output/current.json", "w") as current_save:
            pending_save = {"next_page": next_page}
            json.dump(pending_save, current_save, indent=3)


# run main script
asyncio.run(main())
