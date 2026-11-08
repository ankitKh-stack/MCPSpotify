"""
tests/conftest.py: shared setup for every test file.

pytest reads this file automatically. Each function marked @pytest.fixture
is a *fixture*: a piece of setup that a test asks for by naming it as a
parameter. For example, `def test_x(fake_sp, tools):` gets both fixtures
below, freshly made for that one test.

The big idea: the tests never talk to the real Spotify. Instead they use a
fake ("mock") Spotify connection that we control completely. That makes the
tests fast, repeatable, and safe: they can't skip your song or delete a
playlist, and they work without internet or a login.
"""

from unittest.mock import MagicMock

import pytest
from spotipy.exceptions import SpotifyException

import spotify_client
from tools import library, playback, playlists

# The device most tests pretend is available.
LAPTOP = {
    "id": "laptop-id",
    "name": "My Laptop",
    "type": "Computer",
    "is_active": True,
    "volume_percent": 50,
}


@pytest.fixture
def fake_sp(monkeypatch):
    """
    A fake Spotify connection, swapped in for the real one.

    MagicMock is an object that accepts *any* method call and remembers it.
    fake_sp.pause_playback(...) does nothing, but afterwards a test can ask
    "was pause_playback called, and with what?". A test can also choose what
    a method returns, e.g. fake_sp.current_playback.return_value = None.

    monkeypatch temporarily replaces spotify_client.get_spotify so it returns
    our fake. pytest puts the real one back after each test. This works only
    because the tools call spotify_client.get_spotify() through the module.
    """
    sp = MagicMock()
    sp.devices.return_value = {"devices": [LAPTOP]}
    monkeypatch.setattr(spotify_client, "get_spotify", lambda: sp)
    return sp


class CollectingServer:
    """
    A stand-in for the MCP server that just collects the tools.

    The tool files call @mcp.tool() on whatever server they're given. Here,
    tool() hands back a decorator that stores the function in a dictionary
    by its name and returns it unchanged, so tests can call tools directly.
    """

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


@pytest.fixture
def tools():
    """Every tool, by name: tools["pause"]() calls the pause tool."""
    server = CollectingServer()
    playback.register(server)
    library.register(server)
    playlists.register(server)
    return server.tools


def spotify_error(status, msg="error", headers=None):
    """Build the kind of error spotipy raises when Spotify replies badly."""
    return SpotifyException(status, -1, msg, headers=headers or {})


def make_track(name="Song", artist="Artist", uri="spotify:track:1"):
    """A small track dictionary shaped like the ones Spotify sends."""
    return {
        "type": "track",
        "name": name,
        "uri": uri,
        "duration_ms": 210_000,  # 3:30
        "artists": [{"name": artist}],
        "album": {"name": "Album", "uri": "spotify:album:a1"},
    }
