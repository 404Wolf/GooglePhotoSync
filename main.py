from google import google
import asyncio
import sys
import json
from progress.bar import Bar as bar
from progress.spinner import Spinner as spinner
from time import time, mktime
import ciso8601 as datetime
import os


refresh_library_interval = 6  # in hours

# set the event policy to prevent windows bugs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    """
    Main function (async script)

    Args:
        None
    Returns:
        None
    """

    start = time()
    try:
        client = google(auth_file="auth.json", debug=True)
        await client.auth("photoslibrary.readonly")

        with open("output/raw_data.json") as data:
            data = json.load(data)
        if (
            data["stats"]["last_check"]["finished_check_at"]
            + 60 * 60 * refresh_library_interval
            < time()
        ):
            data = await fetch_library(
                client, ("VIDEO", "PHOTO"), output_file="output.json", debug=True
            )
        else:
            data = data["media"]

        async def current_download_data():
            media_types = list(data.keys())

            for media_type in media_types:
                download_data_progress = spinner("Downloading "+media_type.lower()+"s... ")
                download_data_progress.next()

                present_files = os.listdir("output/" + media_type + "s")

                for photo in data[media_type]:
                    if data[media_type][photo]["name"] not in present_files:
                        photo_data = await client.request(
                            "mediaItems/" + photo, "photoslibrary.readonly"
                        )
                        # example: ([video,mp4], https://example.com)
                        yield [
                            photo_data["mimeType"].split("/"),
                            photo_data["baseUrl"],
                            photo_data["filename"],
                        ]

                        download_data_progress.next()

                print()

        async for download_data in current_download_data():
            if download_data[0][0] == "video":
                download_data[1] += "=dv"

            file_name = download_data[2]
            file_name = file_name.split(".")
            file_name = file_name[:-1]
            file_name = "".join(file_name)
            file_name += "."+download_data[0][1]
            await client.download_file( #name,url
                file_name,
                download_data[1],
                download_path="output/" + download_data[0][0] + "s/",
            )

    finally:
        # close aiohttp session
        print(
            "Finished."
            + "\n"
            + "Time taken: "
            + str(round(time() - start, 3))
            + " seconds ("
            + str(round((time() - start) / 60, 4))
            + " minutes)"
        )

        await client.close_session()


async def fetch_library(client, media_types, output_file="output.json", debug=False):
    """
    Function to pull data for every single photo, and store it as a json

    Args:
        client: google_api client object
    Returns:
        None
    """

    start = time()

    # predefine variables
    output = {}

    for media_type in media_types:
        output[media_type.lower() + "s"] = {}

        next_page = ""

        if debug:
            # create progress bar
            progress_reset_counter = 0
            batch = 1
            progress_bar = bar(
                "Working on batch #" + str(batch) + "'s " + media_type.lower() + "s...",
                fill="#",
                suffix="%(percent).1f%% - %(eta)ds",
            )

        # begin pagation
        while True:
            if debug:
                # progress the progress bar
                progress_bar.next()
                progress_reset_counter += 1
                if progress_reset_counter == 100:
                    progress_reset_counter = 0
                    batch += 1
                    print()
                    progress_bar = bar(
                        "Working on batch #"
                        + str(batch)
                        + "'s "
                        + media_type.lower()
                        + "s...",
                        fill="#",
                        suffix="%(percent).1f%% - %(eta)ds",
                    )

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

                # gather new page key
                next_page = data["nextPageToken"]

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
                    output[media_type.lower() + "s"][entry["id"]] = {
                        "name": entry["filename"],
                        "type": entry["mimeType"],
                        "metadata": entry["mediaMetadata"],
                    }

            # page itteration is complete
            except KeyError:
                if "nextPageToken" in data:
                    next_page = data["nextPageToken"]
                else:
                    break

        print()

    if debug:
        progress_bar.finish()

    end = time()

    count_stats = {}
    for media_type in media_types:
        count_stats[media_type.lower() + "s_found"] = len(output["media_type"])

    output = {
        "stats": {
            "last_check": {
                "started_check_at": round(start),
                "finished_check_at": round(end),
                "time_taken": round(end - start),
            }
        },
        **count_stats,
        "media": output,
    }

    # disable memory buffering to reduce ram usage
    with open(output_file, "w") as final_data:
        json.dump(output, final_data, indent=3)


# run main script
asyncio.run(main())
