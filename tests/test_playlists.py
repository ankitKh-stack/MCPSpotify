"""Tests for tools/playlists.py, plus a check that all 28 tools exist."""

from conftest import make_track, spotify_error


def test_remove_from_playlist_preview(fake_sp, tools):
    fake_sp.playlist.return_value = {"name": "Late Night Coding"}
    uris = [f"spotify:track:{n}" for n in range(12)]

    result = tools["remove_from_playlist"]("p1", uris)

    assert result == (
        "This will remove 12 tracks from Late Night Coding. "
        "Call again with confirm=true to proceed."
    )
    fake_sp.playlist_remove_all_occurrences_of_items.assert_not_called()


def test_remove_from_playlist_preview_says_1_track(fake_sp, tools):
    fake_sp.playlist.return_value = {"name": "Mix"}
    result = tools["remove_from_playlist"]("p1", ["spotify:track:1"])
    assert result.startswith("This will remove 1 track from Mix.")


def test_remove_from_playlist_confirm(fake_sp, tools):
    fake_sp.playlist.return_value = {"name": "Mix"}
    tools["remove_from_playlist"]("p1", ["spotify:track:1"], confirm=True)
    fake_sp.playlist_remove_all_occurrences_of_items.assert_called_once_with(
        "p1", ["spotify:track:1"]
    )


def test_get_playlist_tracks_reads_item_field(fake_sp, tools):
    fake_sp.playlist_items.return_value = {
        "items": [
            {"item": make_track("Feather", "Nujabes")},
            {"item": None},  # a song that was removed from Spotify
        ]
    }
    result = tools["get_playlist_tracks"]("p1")
    assert result == "1. Feather — Nujabes · spotify:track:1"


def test_get_playlist_tracks_someone_elses_playlist(fake_sp, tools):
    fake_sp.playlist_items.side_effect = spotify_error(403, "Forbidden")
    result = tools["get_playlist_tracks"]("p1")
    assert "belongs to someone else" in result


def test_create_playlist_uses_me_endpoint(fake_sp, tools):
    fake_sp.current_user_playlist_create.return_value = {"name": "Focus", "id": "p9"}
    result = tools["create_playlist"]("Focus")
    assert result == "Created private playlist 'Focus' · id p9"
    fake_sp.user_playlist_create.assert_not_called()


def test_all_28_tools_registered(tools):
    assert len(tools) == 28
    assert "get_artist_tracks" in tools
    assert "get_artist_top_tracks" not in tools
