"""
tools/playlists.py: tools for creating playlists and changing what's in them.

Note on Spotify's 2026 changes: the tracks in a playlist are now called
"items" (the old name was "tracks"), and each entry holds its song under
"item". You can only read the contents of playlists you own; for other
people's playlists Spotify returns just the name and description.
"""

from mcp.server.mcpserver import MCPServer
from spotipy.exceptions import SpotifyException

import spotify_client
from spotify_client import format_track, spotify_errors
from tools.library import clamp, numbered


def register(mcp: MCPServer) -> None:
    """Add this file's tools to the server (called once by server.py)."""

    @mcp.tool()
    @spotify_errors
    def create_playlist(name: str, description: str = "", public: bool = False) -> str:
        """
        Create a new, empty playlist in your account.

        public: false (the default) makes it private. Returns the new
        playlist's ID, which add_to_playlist needs.
        """
        sp = spotify_client.get_spotify()
        playlist = sp.current_user_playlist_create(
            name, public=public, description=description
        )
        privacy = "public" if public else "private"
        return f"Created {privacy} playlist '{playlist['name']}' · id {playlist['id']}"

    @mcp.tool()
    @spotify_errors
    def add_to_playlist(playlist_id: str, uris: list[str]) -> str:
        """
        Add tracks to one of your playlists.

        playlist_id: the playlist's ID or URI.
        uris: the tracks' Spotify URIs, e.g. ["spotify:track:...", ...]
          (up to 100 per call). Get them from search results.
        """
        if not uris:
            return "No tracks given, so nothing was added."
        sp = spotify_client.get_spotify()
        sp.playlist_add_items(playlist_id, uris)
        return f"Added {len(uris)} track(s) to the playlist."

    @mcp.tool()
    @spotify_errors
    def remove_from_playlist(
        playlist_id: str, uris: list[str], confirm: bool = False
    ) -> str:
        """
        Remove tracks from one of your playlists. This is a destructive action.

        playlist_id: the playlist's ID or URI.
        uris: the Spotify URIs of the tracks to remove.
        confirm: leave false first. The tool then changes nothing and returns
          a preview. Show that preview to the user and wait for them to say
          yes. Only then call again with confirm=true to actually remove them.
        """
        if not uris:
            return "No tracks given, so nothing was removed."
        sp = spotify_client.get_spotify()
        # fields="name" asks Spotify for just the name, not the whole playlist.
        name = sp.playlist(playlist_id, fields="name")["name"]

        # "1 track" but "2 tracks": pick the right word for the count.
        tracks_word = "track" if len(uris) == 1 else "tracks"

        if not confirm:
            return (
                f"This will remove {len(uris)} {tracks_word} from {name}. "
                "Call again with confirm=true to proceed."
            )

        sp.playlist_remove_all_occurrences_of_items(playlist_id, uris)
        return f"Removed {len(uris)} track(s) from {name}."

    @mcp.tool()
    @spotify_errors
    def get_playlist_tracks(playlist_id: str, limit: int = 50) -> str:
        """
        List the tracks in one of your playlists (up to 50), with their URIs.

        playlist_id: the playlist's ID or URI (from get_my_playlists).
        Only works for playlists you own; Spotify hides the contents of
        other people's playlists from apps like this one.
        """
        sp = spotify_client.get_spotify()
        try:
            results = sp.playlist_items(playlist_id, limit=clamp(limit, 1, 50))
        except SpotifyException as error:
            if error.http_status == 403:
                # Tested during the build: playlists you made can be read,
                # every playlist someone else made returns 403.
                return (
                    "Spotify only lets this app see the tracks of playlists "
                    "you created. This one belongs to someone else."
                )
            raise  # any other error: let spotify_errors handle it

        lines = []
        for entry in results["items"]:
            # Since 2026 the song is under "item" (it used to be "track").
            # It can be None (a song removed from Spotify), or a podcast
            # episode, which isn't a track; we skip both.
            item = entry.get("item")
            if item and item.get("type") == "track":
                lines.append(format_track(item))

        if not lines:
            return "That playlist has no tracks."
        return numbered(lines)
