import aiohttp
import pkce
import json
from webbrowser import open_new
from time import time


class google_api:
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

    def __init__(self, auth_file="auth.json"):
        """
        Creates aiohttp client session for async web requests, and stores auth_file name

        Args:
            auth_file: name of auth file (string)
        Returns:
            None
        """

        self.scopes_file = auth_file
        self.session = aiohttp.ClientSession()

    def load_auth_file(self):
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

    def dump_auth_file(self, dict):
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

    async def auth(self, scope, open_in_browser=True):
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
                + "&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
                + "&code_challenge="
                + code_challenge
                + "&code_challenge_method=S256"
            )

            # open it in a web browser
            if open_in_browser:
                open_new(auth_url)

            # prompt user for code google gives them after they finish the auth steps
            params["code"] = input(
                "Enter\n"
                + auth_url
                + "\ninto a web browser, and paste the code google gives you here: "
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

            # otherwise, there shouldn't be any refresh token in the response
            self.scopes[scope]["access_token"] = resp["access_token"]

            # store the expire timestamp for the access token
            self.scopes[scope]["expires_at"] = round(time() + resp["expires_in"]) - 1

        # save auth information to json file
        self.dump_auth_file({"scopes": self.scopes, "appdata": self.appdata})

    async def request(self, endpoint, scope, params="", headers={}):
        """
        Make a request to a google api endpoint

        Args:
            endpoint: the endpoint to gather data from (to proform a GET request to)
            scope: the scope needed to access that endpoint

        Returns:
            either response as a dictonary, or status code if status code != 200
        """

        if self.scopes[scope]["expires_at"] < time():
            await self.scopes(scope)

        headers = {"Authorization": "Bearer " + self.scopes[scope]["access_token"], **headers}
        async with self.session.get(
            "https://photoslibrary.googleapis.com/v1/" + endpoint, headers=headers, params=params
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return resp.status

    async def close_session(self):
        """
        Closes aiohttp session
        """
        await self.session.close()
