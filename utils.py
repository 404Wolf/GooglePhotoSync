import pkce
import json
from webbrowser import open_new
from aiohttp_retry import RetryClient, ExponentialRetry
from time import time
import aiohttp
import aiofiles


class google:
    """
    Class to access google api endpoints with aiohttp and asyncio.

    Includes functions for gathering auth information/authing the account, and for accessing endpoints

    Attributes:
        appdata:
            appdata["client_id"]: client id for google app
            appdata["project_id"]: project id for google app
            appdata["client_secret"]: client secret for google app
        auth: a dict with information for authing the account.
            "scope" indicates which scope auth information is for
            auth["https://www.googleapis.com/auth/this.is.a.scope"]["access_token"]: for sending requests to google api
            auth["https://www.googleapis.com/auth/this.is.a.scope"]["refresh_token"]: for regenerating access tokens on the fly
            auth["https://www.googleapis.com/auth/this.is.a.scope"]["expires_at"]: UNIX timestamp for when the access_token for the given scope expires
    """

    def __init__(
        self, debug=False, auth_file="auth.json", open_in_browser=True
    ) -> None:
        """
        Creates aiohttp client session for async web requests, and stores auth_file name

        Args:
            auth_file: name of auth file (string)
            debug: print status messages to aid in debugging
        Returns:
            None
        """

        # set object attributes
        self.debug = debug
        self.scopes_file = auth_file
        self.open_in_browser = open_in_browser

        # create a session, which auto retries if request times out
        retry_options = ExponentialRetry(attempts=3)
        retry_client = RetryClient(raise_for_status=False, retry_options=retry_options)
        self.session = retry_client

    def load_auth_file(self) -> dict:
        """
        Reads the auth_file and returns it's contents as a json

        Args:
            None

        Returns:
            dict of the read auth_file

        Raises:
            FileNotFoundError: file with the name of auth_file no longer exists
        """
        return json.load(open(self.scopes_file))

    def dump_auth_file(self, dict: dict) -> None:
        """
        Dump a dict to the auth file json

        Args:
            dict

        Returns:
            None

        Raises:
            FileNotFoundError: file with the name of auth_file no longer exists
        """
        json.dump(dict, open(self.scopes_file, "w"), indent=3)

    async def auth(self, scope: str) -> None:
        """
        Update the self.scopes attribute (obtain valid access_tokens for accessing google api)

        Either uses the already existent refresh_token in the <auth_file>.json, or gathers a new one, and then
        uses it to generate an access token for a given scope.

        Args:
            scope: the google authentication scope to get an access_token for
            open_in_browser: whether to open a web broswer on the user's pc if a new refresh token is needed

        Returns:
            None (updates class attributes and auth file)
        """

        if self.debug:
            print("Authing google account for scope " + scope + "...", end="\r")

        # load the auth file data
        auth_file = self.load_auth_file()
        self.appdata = auth_file["appdata"]
        self.scopes = auth_file["scopes"]

        if scope not in self.scopes:
            self.scopes[scope] = {}

        # pkce token to secure requests
        code_verifier = pkce.generate_code_verifier(length=128)
        code_challenge = pkce.get_code_challenge(code_verifier)

        # once user finishes auth steps provided by google's website, they will be given a code direcly with this uri
        redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

        # set up params for request to get token
        params = {
            "client_id": self.appdata["client_id"],
            "client_secret": self.appdata["client_secret"],
        }

        if "refresh_token" not in self.scopes[scope]:
            params["code_verifier"] = code_verifier
            params["grant_type"] = "authorization_code"
            params["redirect_uri"] = redirect_uri

            # generate a url for the user to go to to auth their account
            auth_url = (
                "https://accounts.google.com/o/oauth2/v2/auth"
                + "?client_id="
                + self.appdata["client_id"]
                + "&scope=https://www.googleapis.com/auth/"
                + scope
                + "&response_type=code"
                + "&redirect_uri="
                + redirect_uri
                + "&code_challenge="
                + code_challenge
                + "&code_challenge_method=S256"
            )

            # open it in a web browser
            if self.open_in_browser:
                open_new(auth_url)

            # prompt user for code google gives them after they finish the auth steps
            params["code"] = input(
                auth_url
                + "\n"
                + "Please go to the above url into a web browser, and paste the code google gives you here: "
            )
        else:
            params["refresh_token"] = self.scopes[scope]["refresh_token"]
            params["grant_type"] = "refresh_token"

        # make request to google to get token
        async with self.session.post(
            "https://oauth2.googleapis.com/token", params=params
        ) as resp:

            resp = await resp.json()
            # if this is a new request with a user provided code, then store the refresh_token
            if "refresh_token" not in self.scopes[scope]:
                self.scopes[scope]["refresh_token"] = resp["refresh_token"]

            try:
                # otherwise, there shouldn't be any refresh token in the response
                self.scopes[scope]["access_token"] = resp["access_token"]
            except KeyError:
                raise Exception("Account failed to auth")

            # store the expire timestamp for the access token
            self.scopes[scope]["expires_at"] = round(time() + resp["expires_in"]) - 1

        # save auth information to json file
        self.dump_auth_file({"scopes": self.scopes, "appdata": self.appdata})

        if self.debug:
            print("Authed google account for scope " + scope + " " * 5)

    async def request(
        self, endpoint: str, scope: str, method="get", data=None, params="", headers={}
    ) -> dict:
        """
        Make a request to a google api endpoint

        Args:
            endpoint: the endpoint to gather data from (to proform a GET request to)
            scope: the scope needed to access that endpoint
            method: the http method to send the request with (get, post, patch, ext.)
            data: request body
            params: params for requeust
            headers: headers for request

        Returns:
            either response dict, or status code if status code != 200
        """

        # reauth if access token is expired expired
        try:
            if self.scopes[scope]["expires_at"] < time():
                await self.auth(scope)
        except KeyError:
            await self.auth(scope)

        # create auth headers + extra headers
        headers = {
            "Authorization": "Bearer " + self.scopes[scope]["access_token"],
            **headers,
        }

        if method == "get":
            resp = await self.session.get(
                "https://photoslibrary.googleapis.com/v1/" + endpoint,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(6),
            )

        if method == "post":
            resp = await self.session.post(
                "https://photoslibrary.googleapis.com/v1/" + endpoint,
                headers=headers,
                params=params,
                json=data,
                timeout=aiohttp.ClientTimeout(6),
            )

        resp_dict = await resp.json()  # await the response dict

        if resp.status == 200:  # 200 -> successful response
            return resp_dict  # return the response's dict

        elif resp.status == 429:  # 429 -> ratelimited
            print(json.dumps(resp_dict, indent=3))
            raise Exception("Ratelimited")  # raise exception

        elif resp.status == 400:  # 400 -> bad request
            print(json.dumps(resp_dict, indent=3))
            raise Exception("Invalid form body")  # raise exception
        else:
            return resp.status

    async def download_file(self, name: str, url: str, download_path="/") -> None:
        """
        Function to download a file from a google base url

        Args:
            name: name to store the file as (saved in the download_path directory)
            download_path: path to store downloaded files to (includes trailing slash; example: "C:\Windows\System32\")
        """

        headers = {
            "Authentication": "Bearer "
            + self.scopes["photoslibrary.readonly"]["access_token"]
        }
        async with self.session.get(url, headers=headers) as resp:
            async with aiofiles.open(download_path + name, "wb", 0) as photo:
                await photo.write(await resp.read())

    async def close_session(self):
        """
        Closes aiohttp session
        """
        await self.session.close()
