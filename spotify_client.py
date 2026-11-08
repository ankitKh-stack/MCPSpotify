"""
spotify_client.py: everything about *connecting* to Spotify lives here.

This file has two jobs:

1. When you run it directly (`uv run python spotify_client.py`), it logs you in.
   A browser window opens, you approve access, and your login token is saved
   to a file called .spotify_cache. You only need to do this once.

2. When the MCP server runs, the tool files call `get_spotify()` from here to
   get a ready-to-use, logged-in connection to Spotify.

Keeping all the login details in one file means the tool files never have to
think about passwords, tokens or settings. They just ask for a connection.
"""

import functools
import logging
import os
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import CacheFileHandler
from spotipy.exceptions import SpotifyException, SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth

# A logger writes messages to the log file (set up in server.py) instead of
# the screen. We use it to record full error details for debugging, while
# you and Claude see only the short, friendly version.
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------
# __file__ is the path of *this* file. .parent is the folder it sits in, which
# is the project folder.
#
# Why not just write ".env"? A bare ".env" means "look in whatever folder the
# program was started from". When Claude Code starts the server, it may start
# it from a different folder, and then .env would not be found. Building the
# path from this file's own location always points to the right place.
PROJECT_DIR = Path(__file__).parent
ENV_PATH = PROJECT_DIR / ".env"
CACHE_PATH = PROJECT_DIR / ".spotify_cache"

# Scopes are the list of permissions we ask Spotify for. On the login page you
# will see Spotify describe each one. We ask only for what our tools need.
SCOPES = " ".join(
    [
        # See and control what is playing
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        # Read and edit playlists
        "playlist-read-private",
        "playlist-modify-private",
        "playlist-modify-public",
        # Liked Songs: read and change
        "user-library-read",
        "user-library-modify",
        # Listening history
        "user-top-read",
        "user-read-recently-played",
        # Followed artists: read and change
        "user-follow-read",
        "user-follow-modify",
    ]
)

# The three settings that must be in .env.
REQUIRED_SETTINGS = [
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SPOTIFY_REDIRECT_URI",
]


class SpotifyToolError(Exception):
    """
    An error whose message is written for a human and safe to show as-is.

    When something goes wrong that the user can fix (not logged in, no
    device open, and so on), we raise this with a friendly message. Later,
    the tools turn it into a plain reply instead of crashing.
    """


def build_auth_manager() -> SpotifyOAuth:
    """
    Read the settings from .env and build spotipy's login helper.

    The "auth manager" is spotipy's object that handles OAuth for us: it knows
    our app's ID and secret, which permissions (scopes) to ask for, and where
    to save the login token.
    """
    if not ENV_PATH.exists():
        raise SpotifyToolError(
            f"I can't find your settings file. Expected it here: {ENV_PATH}\n"
            "Copy .env.example to .env in that folder and fill in your "
            "Spotify Client ID and Client Secret."
        )

    # load_dotenv reads each NAME=value line in .env and makes it available
    # through os.getenv("NAME"), as if it were a setting of your computer.
    load_dotenv(ENV_PATH)

    for name in REQUIRED_SETTINGS:
        if not os.getenv(name):
            raise SpotifyToolError(
                f"{name} is missing or empty in {ENV_PATH}. "
                "Open that file and fill it in."
            )

    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SCOPES,
        cache_handler=CacheFileHandler(cache_path=str(CACHE_PATH)),
        # IMPORTANT: keep this True.
        # If the saved token ever disappears while the server is running,
        # spotipy tries to log in again. With True, it opens your browser and
        # catches Spotify's reply on 127.0.0.1:8888. With False, it would
        # instead wait for you to *type* something. The MCP server can't type
        # anything, so it would freeze forever.
        open_browser=True,
    )


# The one shared Spotify connection, created the first time it's needed.
# It starts as None, meaning "not created yet".
_spotify = None


def get_spotify() -> spotipy.Spotify:
    """
    Return a logged-in Spotify connection, creating it on first use.

    Every tool calls this. Creating the connection once and reusing it is
    faster than logging in again for each tool call.
    """
    global _spotify  # we want to change the variable above, not make a new one

    if _spotify is not None:
        return _spotify

    auth = build_auth_manager()

    # Check for a saved, valid token *before* creating the connection.
    # validate_token returns None when there's no saved token (or it can't be
    # used). It also refreshes an expired token automatically.
    #
    # Why check here? Without a token, spotipy would try to start a login
    # inside the MCP server, where nobody is around to approve it. A clear
    # message telling you what to run is much better.
    token = auth.validate_token(auth.cache_handler.get_cached_token())
    if token is None:
        raise SpotifyToolError(
            "You're not logged in to Spotify yet. In a terminal in the project "
            "folder, run: uv run python spotify_client.py"
        )

    # retries=0 and status_retries=0 turn off spotipy's automatic retrying.
    # When Spotify says "too many requests, wait N seconds", spotipy would
    # obey even if N is hours, which would freeze the tool. We handle waiting
    # ourselves later (Task 4) and only wait for short delays.
    _spotify = spotipy.Spotify(auth_manager=auth, retries=0, status_retries=0)
    return _spotify


# ---------------------------------------------------------------------------
# Choosing which device to control
# ---------------------------------------------------------------------------
NO_DEVICE_MESSAGE = (
    "Open Spotify on your laptop or phone and play anything once, then try again."
)


def pick_device(devices: list[dict]) -> dict | None:
    """
    Choose which Spotify device commands should go to.

    The rules, in order:
      1. A device that is currently active (playing or last used), even if
         it's your phone. We don't steal playback away from it.
      2. Otherwise, a computer (your laptop's Spotify app).
      3. Otherwise, whatever device is available.
      4. No devices at all: return None.

    This function only looks at the list it's given and never talks to
    Spotify, which makes it easy to test.
    """
    for device in devices:
        if device.get("is_active"):
            return device

    for device in devices:
        if device.get("type") == "Computer":
            return device

    if devices:
        return devices[0]

    return None


def get_target_device_id(sp: spotipy.Spotify) -> str:
    """Ask Spotify for your devices and return the ID of the one to control."""
    devices = sp.devices()["devices"]
    device = pick_device(devices)
    if device is None:
        raise SpotifyToolError(NO_DEVICE_MESSAGE)
    return device["id"]


def describe_devices() -> str:
    """A short list of your device names, used inside error messages."""
    try:
        devices = get_spotify().devices()["devices"]
    except Exception:
        # We're already reporting a different problem; don't let this one
        # hide it.
        return ""
    if not devices:
        return ""
    names = ", ".join(f"{d['name']} ({d['type']})" for d in devices)
    return f" Available devices: {names}."


# ---------------------------------------------------------------------------
# Turning errors into friendly replies
# ---------------------------------------------------------------------------
def spotify_errors(func):
    """
    A *decorator* that wraps a tool so errors become friendly messages.

    A decorator is a function that takes another function and returns a new,
    wrapped version of it. Writing @spotify_errors above a tool means:
    "whenever this tool runs, run it inside this safety net."

    Without it, a Spotify error would crash the tool call and Claude would see
    a confusing technical error. With it, Claude gets a sentence it can pass
    on to you, like "Open Spotify on your laptop...".
    """

    # functools.wraps copies the tool's name, docstring and parameter list
    # onto the wrapper. This matters: the MCP library reads those to tell
    # Claude what the tool is and which parameters it takes. Without wraps,
    # every tool would look like a nameless function with no parameters.
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except SpotifyToolError as error:
            # Our own errors already have a friendly message.
            return str(error)

        except SpotifyOauthError:
            # The saved token couldn't be refreshed (for example, you removed
            # the app's access in your Spotify account settings).
            logger.exception("Spotify login error in %s", func.__name__)
            return (
                "Your Spotify login expired and couldn't be refreshed. In a "
                "terminal in the project folder, run: "
                "uv run python spotify_client.py"
            )

        except SpotifyException as error:
            # An error reply from Spotify's API. Log the full details for
            # debugging, then turn it into one short sentence.
            logger.exception("Spotify API error in %s", func.__name__)
            status = error.http_status
            message = str(error.msg)

            if status == 404 and (
                "NO_ACTIVE_DEVICE" in message or "Device not found" in message
            ):
                return NO_DEVICE_MESSAGE + describe_devices()

            if status == 403 and "Restriction violated" in message:
                # Spotify says this when a player command doesn't make sense
                # right now, such as pausing something already paused.
                return (
                    "Spotify refused that playback command, usually because "
                    "it doesn't apply right now (for example, pausing when "
                    "already paused)."
                )

            if status == 403:
                return (
                    "Spotify blocked this request. Some features are "
                    "restricted for apps in development mode, so this may "
                    "not be a bug."
                )

            return f"Spotify error {status}: {message}"

    return wrapper


def login() -> None:
    """
    Log in to Spotify and save the token. Run this once from a terminal.

    The first time, your browser opens to Spotify's approval page. After you
    approve, Spotify sends you back to http://127.0.0.1:8888/callback, spotipy
    catches that, and saves your token to .spotify_cache. On later runs the
    saved token is reused, so no browser opens.
    """
    auth = build_auth_manager()
    auth.get_access_token(as_dict=False)

    # Prove it worked by asking Spotify who we are.
    me = spotipy.Spotify(auth_manager=auth).current_user()
    name = me.get("display_name") or me.get("id")

    # print() is fine here: this is a normal terminal program, not the MCP
    # server. (The server must never print, as you'll see in Task 3.)
    print(f"Logged in as {name}")
    print(f"Token saved to {CACHE_PATH}")


# This block runs only when you start this file directly
# (uv run python spotify_client.py), not when another file imports it.
if __name__ == "__main__":
    try:
        login()
    except SpotifyToolError as error:
        print(error)
        raise SystemExit(1)  # exit code 1 tells the terminal "this failed"
