import utils
import os
import asyncio
import sys
import json
from time import time, mktime
import ciso8601 as datetime
from time import sleep
import aiofiles
from sanitize_filename import sanitize

# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# load config file
with open("config.json") as config:
    config = json.load(config)

# if first run, an auth file will need to be created
if "auth.json" not in os.listdir("utils"):
    with open("utils/auth.json", "w") as auth:
        json.dump(
            {
                "appdata": {
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                },
                "scopes": {},
            },
            auth,
            indent=3,
        )

# if folder layout isn't setup, assume fresh install and setup
if "output" not in os.listdir():
    os.mkdir("output")
    os.mkdir("output/media")
    with open("output/data.json", "w") as data:
        data.write("{}")


async def load_data(lapse: int) -> None:
    """
    Main function.

    1) auths with credentials from auth.json
    2) checks if raw data json is valid, and if it isn't, attempt a restore from backup
    3) pull data from google photos (current list of all photo data)
    4) scan media directory to see what has been downloaded so far
    5) download google photos library to media folder
    6) backup data
    """
    # record start UNIX time
    start = time()

    # load the data from file, or refresh if outdated
    try:
        # create google client object and auth for google photos
        client = utils.google(
            auth_file="utils/auth.json", open_in_browser=config["open_browser_to_auth"]
        )
        await client.auth("photoslibrary.readonly")

        # load data from data file; or from backup if main data file is corrupted
        async with aiofiles.open("output/data.json") as data:
            data = await data.read()
            try:
                data = json.loads(data)
            except json.decoder.JSONDecodeError:
                if data.keys() != ["media", "stats"]:
                    if "data-backup.json" in os.listdir("output"):
                        async with aiofiles.open("output/data-backup.json") as data:
                            data = await data.read()
                            data = json.loads(data)
                else:
                    data = {"stats": {"last_check": {"finished_check_at": 0}}, "media": {}}

        # gather up-to-date data
        data = await fetch_library(client, data)

        # download the images found in data
        data = await download_library(client, data)

        # backup the raw data (since it was not obtained via a direct cancel)
        async with aiofiles.open(
            "output/data.json".replace(".json", "") + "-backup.json", "w"
        ) as final_data:
            await final_data.write(json.dumps(data, indent=3))

    finally:
        # save outputted data
        async with aiofiles.open("output/data.json", "w") as final_data:
            await final_data.write(json.dumps(data, indent=3))

        # print log message
        print(
            "Google Photo Syncing Complete (lapse "
            + str(lapse)
            + ")\n"
            + "Time taken: "
            + str(round(time() - start, 3))
            + " seconds ("
            + str(round((time() - start) / 60, 4))
            + " minutes)"
        )

        # close aiohttp session
        await client.close_session()


async def download_library(client, data: dict) -> dict:
    """
    Function to download entire google photos library, skipping over already downloaded photos.

    Args:
        client: google_api client object
        data: data in the structure as outputted to data.json example: {"stats":{<stat-data>,"media":{<media-type-1>:{<photo-data>}}}
    """
    progress_tracker = utils.progress.bar(
        "Downloading media... ", total=len(data["media"])
    )

    async def current_download_data(data):
        """Yields current baseurl for photo to download."""
        for media, media_data in data["media"].items():
            # if flagged as not yet downloaded
            if not media_data["downloaded"]:
                # if the media base_url is expired generate a new one
                if media_data["last_checked_at"] > time() + 50 * 60:
                    media_data = await client.request(
                        "mediaItems/" + media, "photoslibrary.readonly"
                    )
                # yield the data
                yield media, media_data

    download_tasks = []
    async for media, media_data in current_download_data(data):
        progress_tracker.next()

        if "video" in media_data["type"]:
            media_data["url"] += "=dv"
        else:
            media_data["url"] += "=d"

        download_tasks.append(
            asyncio.ensure_future(
                client.download_file(
                    media_data["filename"],
                    media_data["url"],
                    download_path="output/media/",
                )
            )
        )
        data["media"][media]["downloaded"] = True

        if len(download_tasks) == config["concurrent_downloads"]:
            download_tasks = await asyncio.wait(download_tasks)
            download_tasks = []

    if len(download_tasks) > 0:
        await asyncio.wait(download_tasks)

    progress_tracker.finish("Finished downloading media.")

    # switch to progress spinner's ending message
    return data


async def fetch_library(client, data: dict) -> dict:
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

    # progress spinner
    progress_tracker = utils.progress.spinner("Fetching media... ")

    # emtpy dict for data google will send back
    response_data = {"nextPageToken": ""}

    # next page pagation token
    next_page = ""

    # begin pagation
    while "nextPageToken" in response_data:
        # pageSize is 100 to maximize efficiency; includeArchivedMedia is enabled because by default it is false
        request_data = {"pageSize": 100, "filters": {"includeArchivedMedia": True}}

        if bool(
            next_page
        ):  # if not first run, apply page token (bool() is used rather than len() > 0)
            request_data["pageToken"] = next_page

        # gather new page key from last runthrough of page
        next_page = response_data["nextPageToken"]

        # request google photos data from google
        response_data = await client.request(
            "mediaItems:search",
            "photoslibrary.readonly",
            method="post",
            data=request_data,
        )

        if "mediaItems" in response_data:
            for entry in response_data["mediaItems"]:
                # convert timestring to timestamp
                entry["mediaMetadata"]["creationTime"] = datetime.parse_datetime(
                    entry["mediaMetadata"]["creationTime"]
                )

                entry["mediaMetadata"]["creationTime"] = int(
                    mktime(entry["mediaMetadata"]["creationTime"].timetuple())
                )

                # convert size values to integers
                if ("height" in entry["mediaMetadata"]) and (
                    "width" in entry["mediaMetadata"]
                ):
                    entry["mediaMetadata"]["width"] = int(
                        entry["mediaMetadata"]["width"]
                    )
                    entry["mediaMetadata"]["height"] = int(
                        entry["mediaMetadata"]["height"]
                    )

                # set video status to bool
                if "video" in entry["mediaMetadata"]:
                    try:
                        entry["mediaMetadata"]["video"]["status"] = (
                            entry["mediaMetadata"]["video"]["status"] == "READY"
                        )  # change status to bool
                        entry["mediaMetadata"]["video"]["fps"] = round(
                            entry["mediaMetadata"]["video"]["fps"], 2
                        )  # round fps
                    except KeyError:
                        entry["mediaMetadata"]["video"][
                            "status"
                        ] = None  # otherwise set status to null

                # flag as downloaded if already flagged as downloaded, otherwise flag as not downloaded
                if (entry["id"] in data) and (
                    "downloaded" in data["media"][entry["id"]]
                ):
                    downloaded = data["media"][entry["id"]]["downloaded"]
                else:
                    downloaded = False

                # split mimetype to array
                entry["mimeType"] = entry["mimeType"].split("/")

                # only keep needed data when dumping to output
                data["media"][entry["id"]] = {
                    "url": entry["baseUrl"],
                    "filename": sanitize(entry["id"] + "." + entry["mimeType"][1]),
                    "type": entry["mimeType"][0],
                    "extension": entry["mimeType"][1],
                    "metadata": entry["mediaMetadata"],
                    "last_checked_at": int(time()),
                    "downloaded": downloaded,
                }

        progress_tracker.next()  # tick progress tracker

    # switch to progress spinner's ending message
    progress_tracker.finish("Finished fetching media")

    # record end UNIX time
    end = time()

    # create output dict to dump to file
    data["stats"] = {
        "last_check": {
            "started_check_at": round(start, 3),
            "finished_check_at": round(end, 3),
            "time_taken": round(end - start, 3),
        },
        "items_found": len(data["media"]),
    }

    return data


# run main script every specified interval (in hours)
lapse = 1
while True:
    asyncio.run(load_data(lapse))
    lapse += 1
    print(
        "\nWaiting " + str(config["scan_library_interval"]) + " hours until next lapse."
    )
    sleep(config["scan_library_interval"] * 60 * 60)
