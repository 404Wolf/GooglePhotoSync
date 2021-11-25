from google import google
import asyncio
import sys
import json
from progress.bar import Bar as bar
import aiofiles
from colorama import init 
init()

# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    """
    Main function async script

    Args:
        None
    Returns:
        None
    """

    client = google()
    await client.auth("photoslibrary.readonly")
    await gather_photo_data(client)


async def gather_photo_data(client):
    """
    Function to pull data for every single photo, and store it as a json

    Args:
        client: google_api client object
    Returns:
        None
    """

    # create progress bar
    progress_reset_counter = 0
    batch = 1
    progress_bar = progress_bar = progress_bar = bar(
        "Working on batch #" + str(batch) + "'s images...",
        fill="@",
        suffix="%(percent).1f%% - %(eta)ds",
    )

    # scope for google photos view perms
    scope = "photoslibrary.readonly"

    # figure out where script left off if it crashed on the last run
    async with aiofiles.open("output/current.json") as current_save:
        next_page = json.loads(await current_save.read())["next_page"]
    async with aiofiles.open("output/raw_data.json") as previous_data:
        previous_data = json.loads(await previous_data.read())
    output = []

    progress_bar.next()
    # begin pagation
    try:
        while True:
            # progress the progress bar
            progress_bar.next()
            progress_reset_counter += 1
            if progress_reset_counter == 99:
                progress_reset_counter = 0
                batch += 1
                print()
                progress_bar = progress_bar = bar(
                    "Working on batch #" + str(batch) + "'s images...",
                    fill="@",
                    suffix="%(percent).1f%% - %(eta)ds",
                )

            # attempt page itteration
            try:
                # set up params for api request
                params = {"pageSize": "100"}
                if bool(next_page):
                    params["pageToken"] = next_page

                # request google photos data from google
                data = await client.request("mediaItems", scope, params=params)

                # gather new page key
                next_page = data["nextPageToken"]

                # extract media items
                data = data["mediaItems"]

                # combine previous data with new data
                data = previous_data + data 

                # save previous data
                previous_data = data

                # update output with the data
                output += data

            # page itteration is complete
            except KeyError:
                if "nextPageToken" in data:
                    next_page = data["nextPageToken"]
                else:
                    break
    finally:
        # close aiohttp session
        await client.close_session()

    #disable memory buffering to reduce ram usage
    with open("output/raw_data.json", "w", 0) as final_data:
        await final_data.write(json.dumps(output, indent=3))

    # save status of script
    with open("output/current.json", "w") as current_save:
        await current_save.write(json.dumps({"next_page": next_page}, indent=3))

# run main script
asyncio.run(main())
