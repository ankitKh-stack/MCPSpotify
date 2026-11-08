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

import os
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth


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
