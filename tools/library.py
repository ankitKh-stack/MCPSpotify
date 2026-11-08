"""
tools/library.py: tools for searching Spotify and reading or changing your
library (Liked Songs, followed artists, top tracks, history).

Same pattern as playback.py: a register(mcp) function that defines each tool
with @mcp.tool() and @spotify_errors. Most tools here only *read*, so they
don't need a device.
"""

from mcp.server.mcpserver import MCPServer

import spotify_client
from spotify_client import format_track, spotify_errors

# Allowed values for parameters that only accept a few options.
SEARCH_TYPES = ("track", "artist", "album", "playlist")
TOP_ITEM_TYPES = ("tracks", "artists")
TIME_RANGES = ("short_term", "medium_term", "long_term")


def clamp(value: int, low: int, high: int) -> int:
    """
    Keep a number between low and high.

    clamp(50, 1, 10) -> 10    clamp(0, 1, 10) -> 1    clamp(5, 1, 10) -> 5
    Used for "limit" parameters, so a request for 500 results quietly
    becomes the most Spotify allows instead of an error.
    """
    return max(low, min(value, high))


def format_item(item: dict, item_type: str) -> str:
    """One line for a search result, depending on what kind of item it is."""
    if item_type == "track":
        return format_track(item)
    if item_type == "album":
        artists = ", ".join(artist["name"] for artist in item["artists"])
        return f"{item['name']} — {artists} · {item['uri']}"
    if item_type == "playlist":
        owner = item["owner"].get("display_name") or item["owner"]["id"]
        return f"{item['name']} (by {owner}) · {item['uri']}"
    # artist
    return f"{item['name']} · {item['uri']}"


def numbered(lines: list[str]) -> str:
    """Number a list of lines: '1. ...', '2. ...'."""
    return "\n".join(f"{n}. {line}" for n, line in enumerate(lines, start=1))


def register(mcp: MCPServer) -> None:
    """Add this file's tools to the server (called once by server.py)."""

    @mcp.tool()
    @spotify_errors
    def search(query: str, type: str = "track", limit: int = 10) -> str:
        """
        Search Spotify.

        query: what to look for, e.g. "lo-fi beats" or "radiohead". Filters
          work too, e.g. 'artist:"Daft Punk"' or 'genre:jazz'.
        type: "track", "artist", "album" or "playlist".
        limit: how many results, 1 to 10 (Spotify's maximum per search). To
          gather more, search again with different words.

        Each result ends with its Spotify URI, which other tools accept.
        """
        if type not in SEARCH_TYPES:
            return f"type must be one of: {', '.join(SEARCH_TYPES)}."

        sp = spotify_client.get_spotify()
        # Always ask for the maximum (10). Spotify sends some results back as
        # empty slots (None), especially playlists, so asking for exactly
        # `limit` could leave us with fewer real results, or none at all.
        results = sp.search(q=query, type=type, limit=10)

        # Spotify puts results under the plural key: "tracks", "albums"...
        # Drop the empty slots, then keep only as many as were asked for.
        items = [item for item in results[type + "s"]["items"] if item]
        items = items[: clamp(limit, 1, 10)]
        if not items:
            return f"No {type}s found for '{query}'."
        return numbered([format_item(item, type) for item in items])

    @mcp.tool()
    @spotify_errors
    def get_my_playlists(limit: int = 20) -> str:
        """
        List your playlists (ones you made and ones you follow), with the
        number of tracks and the playlist ID to use with other tools.
        """
        sp = spotify_client.get_spotify()
        results = sp.current_user_playlists(limit=clamp(limit, 1, 50))
        my_id = sp.current_user()["id"]

        lines = []
        for playlist in results["items"]:
            line = playlist["name"]
            # Say whose playlist it is: Spotify only lets this app read or
            # change the tracks of playlists you created.
            if playlist["owner"]["id"] == my_id:
                line += " [yours]"
            else:
                owner = playlist["owner"].get("display_name") or playlist["owner"]["id"]
                line += f" [by {owner}]"
            # Since Spotify's 2026 changes the track count is under "items".
            # It can be missing for playlists you follow but don't own.
            total = (playlist.get("items") or {}).get("total")
            if total is not None:
                line += f" ({total} tracks)"
            line += f" · id {playlist['id']}"
            lines.append(line)

        if not lines:
            return "You don't have any playlists yet."
        return numbered(lines)

    @mcp.tool()
    @spotify_errors
    def get_top_items(type: str = "tracks", time_range: str = "medium_term") -> str:
        """
        Your most-played tracks or artists.

        type: "tracks" or "artists".
        time_range: "short_term" (about the last 4 weeks), "medium_term"
          (about 6 months) or "long_term" (about a year).
        """
        if type not in TOP_ITEM_TYPES:
            return 'type must be "tracks" or "artists".'
        if time_range not in TIME_RANGES:
            return f"time_range must be one of: {', '.join(TIME_RANGES)}."

        sp = spotify_client.get_spotify()
        if type == "tracks":
            items = sp.current_user_top_tracks(limit=20, time_range=time_range)["items"]
            lines = [format_track(track) for track in items]
        else:
            items = sp.current_user_top_artists(limit=20, time_range=time_range)["items"]
            lines = [format_item(artist, "artist") for artist in items]

        if not lines:
            return "Spotify doesn't have enough listening history for that yet."
        return numbered(lines)

    @mcp.tool()
    @spotify_errors
    def get_recently_played(limit: int = 20) -> str:
        """The tracks you played most recently, newest first (up to 50)."""
        sp = spotify_client.get_spotify()
        results = sp.current_user_recently_played(limit=clamp(limit, 1, 50))
        lines = [format_track(entry["track"]) for entry in results["items"]]
        if not lines:
            return "No recently played tracks."
        return numbered(lines)

    @mcp.tool()
    @spotify_errors
    def get_saved_tracks(limit: int = 20) -> str:
        """Your Liked Songs, most recently liked first (up to 50)."""
        sp = spotify_client.get_spotify()
        results = sp.current_user_saved_tracks(limit=clamp(limit, 1, 50))
        lines = [format_track(entry["track"]) for entry in results["items"]]
        if not lines:
            return "You don't have any Liked Songs yet."
        return numbered(lines)

    @mcp.tool()
    @spotify_errors
    def save_current_track() -> str:
        """Add the currently playing track to your Liked Songs."""
        sp = spotify_client.get_spotify()
        playback = sp.current_playback()
        if not playback or not playback.get("item"):
            return "Nothing is playing right now."
        track = playback["item"]
        sp.current_user_saved_tracks_add([track["uri"]])
        return f"Added {track['name']} to your Liked Songs."

    @mcp.tool()
    @spotify_errors
    def remove_saved_track(uri: str, confirm: bool = False) -> str:
        """
        Remove a track from your Liked Songs. This is a destructive action.

        uri: the track's Spotify URI.
        confirm: leave false first. The tool then changes nothing and returns
          a preview. Show that preview to the user and wait for them to say
          yes. Only then call again with confirm=true to actually remove it.
        """
        sp = spotify_client.get_spotify()
        track = sp.track(uri)  # look up the name for a clear preview
        name = f"{track['name']} by {track['artists'][0]['name']}"

        if not confirm:
            return (
                f"This will remove {name} from your Liked Songs. "
                "Call again with confirm=true to proceed."
            )

        sp.current_user_saved_tracks_delete([uri])
        return f"Removed {name} from your Liked Songs."

    @mcp.tool()
    @spotify_errors
    def get_artist_tracks(artist_name: str) -> str:
        """
        Find up to 10 tracks by an artist.

        These are search results filtered to that artist, roughly their best
        known songs. They are not Spotify's official "top tracks" list,
        which Spotify no longer offers to apps like this one.
        """
        sp = spotify_client.get_spotify()
        # We search for the artist's name, then keep only tracks where one
        # of the credited artists has that name. (Spotify's stricter filter,
        # artist:"Name", was tried first but found only 5 Daft Punk tracks.)
        results = sp.search(q=artist_name, type="track", limit=10)
        wanted = artist_name.casefold()
        tracks = []
        for track in results["tracks"]["items"]:
            names = [artist["name"].casefold() for artist in track["artists"]]
            if wanted in names:
                tracks.append(track)
        if not tracks:
            return f"No tracks found for artist '{artist_name}'."
        return numbered([format_track(track) for track in tracks])

    @mcp.tool()
    @spotify_errors
    def get_album_tracks(album_id: str) -> str:
        """
        List the tracks on an album.

        album_id: the album's ID or URI (e.g. "spotify:album:...", from
          search results).
        """
        sp = spotify_client.get_spotify()
        album = sp.album(album_id)
        tracks = album["tracks"]["items"]
        header = f"{album['name']} ({len(tracks)} tracks):"
        return header + "\n" + numbered([format_track(track) for track in tracks])

    @mcp.tool()
    @spotify_errors
    def follow_artist(artist_id: str) -> str:
        """
        Follow an artist on Spotify.

        artist_id: the artist's ID or URI (e.g. "spotify:artist:...", from
          search results with type "artist").
        """
        sp = spotify_client.get_spotify()
        artist = sp.artist(artist_id)
        sp.user_follow_artists([artist_id])
        return f"You're now following {artist['name']}."

    @mcp.tool()
    @spotify_errors
    def get_followed_artists() -> str:
        """List the artists you follow (up to 50)."""
        sp = spotify_client.get_spotify()
        artists = sp.current_user_followed_artists(limit=50)["artists"]["items"]
        if not artists:
            return "You don't follow any artists yet."
        return numbered([format_item(artist, "artist") for artist in artists])
