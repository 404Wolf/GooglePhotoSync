from google import google
import asyncio
import sys
import json
from time import time, mktime
import ciso8601 as datetime
from progress import progress
from time import sleep
from os import listdir

# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with open("config.json") as config:
    config = json.load(config)

# locate backup path (same directory and file type but has -backup)
config["raw_data_backup_output_path"] = config["raw_data_output_path"].split(".")
config["raw_data_backup_output_path"] = (
    config["raw_data_backup_output_path"][0]
    + "-backup"
    + "."
    + config["raw_data_backup_output_path"][1]
)


async def load_data(lapse):
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
        try:
            for path in (
                config["raw_data_output_path"],
                config["raw_data_backup_output_path"]
            ):
                with open(path) as data:
                    data = json.load(data)
                    if ("stats" not in data) or ("media" not in data):
                        raise Exception
                    break
        except:
            data = {"stats": {"last_check": {"finished_check_at": 0}}, "media": {}}

        data = await fetch_library(client, data)

        # double check what is and isn't downloaded
        progress_spinner = progress(
            "Scanning media output directory... ",
            "Finished scanning media output directory.",
        )

        already_downloaded = listdir(config["media_output_path"])
        for media, media_data in tuple(data["media"].items()):
            if media_data["filename"] not in already_downloaded:
                data["media"][media]["downloaded"] = False
            else:
                data["media"][media]["downloaded"] = True
            progress_spinner.next()
        progress_spinner.finish()

        # download the images found in data
        data = await download_library(client, data)

        # backup the raw data (since it was not obtained via a direct cancel)
        with open(
            config["raw_data_output_path"].replace(".json", "") + "-backup.json", "w"
        ) as final_data:
            json.dump(data, final_data, indent=3)

    finally:
        # save outputted data
        with open(config["raw_data_output_path"], "w") as final_data:
            json.dump(data, final_data, indent=3)

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


async def download_library(client, data):
    """
    Function to download entire google photos library, skipping over already downloaded photos

    Args:
        client: google_api client object
        data: data in the structure as outputted to data.json example: {"stats":{<stat-data>,"media":{<media-type-1>:{<photo-data>}}}
    """

    progress_spinner = progress("Downloading media... ", "Finished downloading media.")

    async def current_download_data(data):

        for media, media_data in data["media"].items():

            # if flagged as not yet downloaded
            if not media_data["downloaded"]:

                # if the media base_url is expired generate a new one
                if media_data["last_checked_at"] > time() + 50 * 60:
                    media_data = await client.request(
                        "mediaItems/" + media, "photoslibrary.readonly"
                    )
                    print("regen")

                # yield the data
                yield media, media_data

    download_tasks = []
    async for media, media_data in current_download_data(data):
        if "video" in media_data["type"]:
            media_data["url"] += "=dv"
        else:
            media_data["url"] += "=d"

        download_tasks.append(
            asyncio.ensure_future(
                client.download_file(
                    media_data["filename"],
                    media_data["url"],
                    download_path=config["media_output_path"],
                )
            )
        )
        data["media"][media]["downloaded"] = True

        if len(download_tasks) == config["concurrent_downloads"]:
            download_tasks = await asyncio.wait(download_tasks)
            download_tasks = []
            progress_spinner.next()  # tick progress spinner

    if len(download_tasks) > 0:
        await asyncio.wait(download_tasks)

    # switch to progress spinner's ending message
    progress_spinner.finish()
    return data


async def fetch_library(client, data, media_types=("VIDEO", "PHOTO")):
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

    # create progress spinner
    progress_spinner = progress("Fetching media... ", "Finished fetching media.")

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
                response_data = await client.request(
                    "mediaItems:search",
                    "photoslibrary.readonly",
                    method="post",
                    data=request_data,
                )

                for entry in response_data["mediaItems"]:
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

                    try:
                        downloaded = data["media"][entry["id"]]["downloaded"]
                    except KeyError:
                        downloaded = False

                    # only keep needed data when dumping to output
                    data["media"][entry["id"]] = {
                        "url": entry["baseUrl"],
                        "filename": entry["filename"].replace(" ", "_"),
                        "type": entry["mimeType"],
                        "metadata": entry["mediaMetadata"],
                        "last_checked_at": int(time()),
                        "downloaded": downloaded,
                    }

                # gather new page key
                next_page = response_data["nextPageToken"]

            # page itteration is complete
            except KeyError:
                break

    # switch to progress spinner's ending message
    progress_spinner.finish()

    # record end UNIX time
    end = time()

    # create output dict to dump to file
    data["stats"] = {
        "last_check": {
            "started_check_at": round(start),
            "finished_check_at": round(end),
            "time_taken": round(end - start),
        },
        "items_found": len(data),
    }

    return data


# run main script every specified interval (in hours)
lapse = 1
while True:
    asyncio.run(load_data(lapse))
    lapse += 1
    print("\nWaiting "+str(config["scan_library_interval"])+" hours until next lapse.")
    sleep(config["scan_library_interval"] * 60 * 60)
