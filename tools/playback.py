"""
tools/playback.py: tools that control what's playing.

Every tool here follows the same pattern:
  1. get the Spotify connection with spotify_client.get_spotify()
  2. pick the device to control (for commands that need one)
  3. ask Spotify to do something
  4. return one short sentence describing what happened

The docstring of each tool matters more than usual: the MCP library sends it
to Claude as the tool's description. It's how Claude decides when to use the
tool and what to pass in.
"""

from mcp.server.mcpserver import MCPServer

# We import the *module* and call spotify_client.get_spotify(), rather than
# "from spotify_client import get_spotify". The tests in Task 5 rely on this:
# they can swap the real Spotify connection for a fake one in one place.
import spotify_client
from spotify_client import spotify_errors


def format_time(milliseconds: int) -> str:
    """Turn milliseconds into minutes:seconds, e.g. 65000 -> '1:05'."""
    total_seconds = milliseconds // 1000  # // divides and drops the remainder
    minutes = total_seconds // 60
    seconds = total_seconds % 60  # % gives the remainder
    return f"{minutes}:{seconds:02d}"  # :02d pads to two digits, e.g. 5 -> 05


def artist_names(track: dict) -> str:
    """Join a track's artists into one string, e.g. 'Daft Punk, Pharrell'."""
    return ", ".join(artist["name"] for artist in track["artists"])


def play_track(sp, device_id: str, track: dict) -> None:
    """
    Play one track by playing its album, starting at that track.

    Why not just ask Spotify to play the track on its own
    (start_playback(uris=[track_uri]))? We tried it during the build: Spotify
    accepted the request, but the desktop app then played nothing. Playing
    the track inside its album works reliably, and when the song ends the
    album carries on, like clicking a song in the Spotify app.
    """
    sp.start_playback(
        device_id=device_id,
        context_uri=track["album"]["uri"],
        offset={"uri": track["uri"]},
    )


def register(mcp: MCPServer) -> None:
    """
    Add this file's tools to the server.

    server.py calls this once at startup. The tools are defined *inside* this
    function so that "@mcp.tool()" can refer to the server passed in. That
    way this file never has to import server.py, which avoids two files
    importing each other in a loop.
    """

    # @mcp.tool() registers the function below it as a tool Claude can call.
    # @spotify_errors (from spotify_client.py) turns errors into friendly
    # replies. Decorators apply from the bottom up: spotify_errors wraps the
    # function first, then mcp.tool registers the wrapped version.
    @mcp.tool()
    @spotify_errors
    def now_playing() -> str:
        """
        Show what's playing on Spotify right now: the track, artists, album,
        progress through the track, and which device it's playing on.
        """
        sp = spotify_client.get_spotify()
        playback = sp.current_playback()

        # Spotify returns nothing when no device has played anything
        # recently, and item is empty during ads or private sessions.
        if not playback or not playback.get("item"):
            return "Nothing is playing right now."

        track = playback["item"]
        progress = format_time(playback.get("progress_ms") or 0)
        duration = format_time(track["duration_ms"])
        device = playback["device"]["name"]

        text = (
            f"{track['name']} — {artist_names(track)} "
            f"(album {track['album']['name']}) · {progress} / {duration} "
            f"· on {device}"
        )
        if not playback["is_playing"]:
            text += " (paused)"
        return text

    @mcp.tool()
    @spotify_errors
    def play(query: str | None = None, uri: str | None = None) -> str:
        """
        Start or resume playback on Spotify.

        - No arguments: resume whatever was playing.
        - uri: play that exact Spotify item. A track URI looks like
          "spotify:track:...". An album, playlist or artist URI plays that
          whole collection.
        - query: search for a track by name (and optionally artist) and play
          the best match, e.g. "bohemian rhapsody queen".

        Use uri when you already know it (for example from search results);
        use query for a quick "play X" request.
        """
        sp = spotify_client.get_spotify()
        device_id = spotify_client.get_target_device_id(sp)

        if uri:
            if uri.startswith("spotify:track:"):
                # Look the track up to find its album, then play it there.
                track = sp.track(uri)
                play_track(sp, device_id, track)
                return f"Playing {track['name']} by {artist_names(track)}."
            else:
                # Albums, playlists and artists are a "context": Spotify
                # plays through the whole collection.
                sp.start_playback(device_id=device_id, context_uri=uri)
            return f"Playing {uri}."

        if query:
            results = sp.search(q=query, type="track", limit=1)
            tracks = results["tracks"]["items"]
            if not tracks:
                return f"I couldn't find anything for '{query}'."
            track = tracks[0]
            play_track(sp, device_id, track)
            return f"Playing {track['name']} by {artist_names(track)}."

        # No query and no uri: just resume.
        sp.start_playback(device_id=device_id)
        return "Resumed playback."

    @mcp.tool()
    @spotify_errors
    def pause() -> str:
        """Pause Spotify playback."""
        sp = spotify_client.get_spotify()
        device_id = spotify_client.get_target_device_id(sp)
        sp.pause_playback(device_id=device_id)
        return "Paused."

    @mcp.tool()
    @spotify_errors
    def next_track() -> str:
        """Skip to the next track."""
        sp = spotify_client.get_spotify()
        device_id = spotify_client.get_target_device_id(sp)
        sp.next_track(device_id=device_id)
        return "Skipped to the next track."
