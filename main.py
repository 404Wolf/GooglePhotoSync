from google import google
import asyncio
import sys
import json
from progress.spinner import Spinner as spinner
from time import time, mktime
import ciso8601 as datetime
import os


override = False  # force a refresh
refresh_library_interval = 6  # in hours


# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class progress:
    def __init__(self, msg, endmsg):
        self.states = ["/", "|", "\\", "-"]
        self.state = 0
        self.msg = msg
        self.endmsg = endmsg
        print(self.msg + self.states[self.state], end="\r")

    def next(self):
        self.state += 1
        if self.state == 4:
            self.state = 0
        print(self.msg + self.states[self.state], end="\r")

    def finish(self):
        print(" " * (len(self.msg) + 1), end="\r")
        print(self.endmsg)


async def load_data():
    """
    Main function (async script)

    Args:
        None
    Returns:
        None
    """

    # record start UNIX time
    start = time()

    # load the data from file, or refresh if outdated
    try:
        # create google client object and auth for google photos
        client = google(auth_file="auth.json")
        await client.auth("photoslibrary.readonly")

        # load data from data file
        with open("output/raw_data.json") as data:
            data = json.load(data)

        # if data is outdated, reload it
        if (
            data["stats"]["last_check"]["finished_check_at"] < time() + 60 * 40
            or override
        ):
            data = await fetch_library(client, output_file="output/raw_data.json")

        # download the images found in data
        await download_library(client, data)

    finally:
        # print log message
        print()
        print(
            "Google Photo Sync Tool Finished.\n"
            + "Time taken: "
            + str(round(time() - start, 3))
            + " seconds ("
            + str(round((time() - start) / 60, 4))
            + " minutes)"
        )
        # close aiohttp session
        await client.close_session()


async def download_library(client, data, download_path="output/media"):
    """
    Function to download entire google photos library, skipping over already downloaded photos

    Args:
        client: google_api client object
        data: data in the structure as outputted to data.json example: {"stats":{<stat-data>,"media":{<media-type-1>:{<photo-data>}}}
        download_path: path of where to output to
    """

    async def current_download_data(data):
        progress_spinner = progress("Downloading media...","Finished downloading media.")
        progress_spinner.next()

        # fetch list of already downloaded files
        present_files = os.listdir(download_path)

        for media, media_data in data["media"].items():

            # download media only if it isn't already there
            if media_data["filename"] not in present_files:

                # if the media base_url is expired generate a new one
                if media_data["last_checked_at"] > time() + 50 * 60:
                    media_data = await client.request(
                        "mediaItems/" + media, "photoslibrary.readonly"
                    )

                progress_spinner.next()
                yield media_data

        progress_spinner.finish()

    download_tasks = []
    async for media_data in current_download_data(data):
        if "video" in media_data["type"]:
            media_data["baseUrl"] += "=dv"

        file_name = media_data["filename"]
        file_name = file_name.split(".")
        file_name = file_name[:-1]
        file_name = "".join(file_name)
        file_name += "." + media_data["type"].split("/")[-1]
        download_tasks.append(
            asyncio.ensure_future(
                client.download_file(
                    file_name, media_data["url"], download_path="output/media/"
                )
            )
        )

        if len(download_tasks) == 6:
            download_tasks = await asyncio.wait(download_tasks)
            download_tasks = []

    await asyncio.wait(download_tasks)


async def fetch_library(
    client, media_types=("VIDEO", "PHOTO"), output_file="output.json"
):
    """
    Function to pull data for every single photo, and store it as a json

    Args:
        client: google_api client object
        media_types: list of types of media to download (options are noted on google's api documentation)
    Returns:
        None
    """

    # record start UNIX time
    start = time()

    # predefine variables
    output = {}

    # create progress spinner
    progress_spinner = progress("Fetching media...","Finished fetching media.")

    for media_type in media_types:
        next_page = ""

        # begin pagation
        while True:
            # progress the progress bar
            progress_spinner.next()

            # attempt page itteration
            try:
                request_data = {
                    "pageSize": 100,
                    "filters": {
                        "mediaTypeFilter": {
                            "mediaTypes": [media_type]  # ALL_MEDIA or VIDEO or PHOTO
                        }
                    },
                }

                if bool(next_page):
                    request_data["pageToken"] = next_page

                # request google photos data from google
                data = await client.request(
                    "mediaItems:search",
                    "photoslibrary.readonly",
                    method="post",
                    data=request_data,
                )

                for entry in data["mediaItems"]:
                    # convert timestring to timestamp
                    entry["mediaMetadata"]["creationTime"] = datetime.parse_datetime(
                        entry["mediaMetadata"]["creationTime"]
                    )

                    entry["mediaMetadata"]["creationTime"] = int(
                        mktime(entry["mediaMetadata"]["creationTime"].timetuple())
                    )

                    # convert image size values to integers
                    entry["mediaMetadata"]["width"] = int(
                        entry["mediaMetadata"]["width"]
                    )
                    entry["mediaMetadata"]["height"] = int(
                        entry["mediaMetadata"]["height"]
                    )

                    # only keep needed data when dumping to output
                    output[entry["id"]] = {
                        "url": entry["baseUrl"],
                        "filename": entry["filename"],
                        "type": entry["mimeType"],
                        "metadata": entry["mediaMetadata"],
                        "last_checked_at": int(time()),
                    }

                # gather new page key
                next_page = data["nextPageToken"]

            # page itteration is complete
            except KeyError:
                if "nextPageToken" in data:
                    next_page = data["nextPageToken"]
                else:
                    break

    progress_spinner.finish()

    # record end UNIX time
    end = time()

    # create output dict to dump to file
    output = {
        "stats": {
            "last_check": {
                "started_check_at": round(start),
                "finished_check_at": round(end),
                "time_taken": round(end - start),
            },
            "items_found": len(output),
        },
        "media": output,
    }

    # dump dict to file as a json
    with open(output_file, "w") as final_data:
        json.dump(output, final_data, indent=3)

    return output


# run main script
asyncio.run(load_data())
