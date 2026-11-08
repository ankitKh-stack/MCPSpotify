"""Tests for tools/library.py."""

from conftest import make_track


def test_search_clamps_limit(fake_sp, tools):
    fake_sp.search.return_value = {"tracks": {"items": [make_track()]}}
    tools["search"]("lofi", limit=50)
    # We always ask Spotify for 10, its maximum, whatever limit was given.
    assert fake_sp.search.call_args.kwargs["limit"] == 10


def test_search_skips_empty_slots(fake_sp, tools):
    # Spotify sometimes sends None instead of a result, mostly for playlists.
    fake_sp.search.return_value = {
        "playlists": {
            "items": [
                None,
                {
                    "name": "Lo-fi Focus",
                    "uri": "spotify:playlist:p1",
                    "owner": {"id": "someone", "display_name": "Someone"},
                },
                None,
            ]
        }
    }
    result = tools["search"]("lofi", type="playlist")
    assert result == "1. Lo-fi Focus (by Someone) · spotify:playlist:p1"


def test_search_respects_smaller_limit(fake_sp, tools):
    tracks = [make_track(f"Song {n}", uri=f"spotify:track:{n}") for n in range(5)]
    fake_sp.search.return_value = {"tracks": {"items": tracks}}
    result = tools["search"]("songs", limit=2)
    assert result.count("\n") == 1  # two lines
    assert "Song 2" not in result


def test_get_artist_tracks_keeps_only_that_artist(fake_sp, tools):
    fake_sp.search.return_value = {
        "tracks": {
            "items": [
                make_track("Around the World", "Daft Punk", "spotify:track:1"),
                make_track("A Cover", "Some Band", "spotify:track:2"),
                make_track("Get Lucky", "DAFT PUNK", "spotify:track:3"),
            ]
        }
    }
    result = tools["get_artist_tracks"]("daft punk")
    assert "Around the World" in result
    assert "Get Lucky" in result  # capitals don't matter
    assert "A Cover" not in result


def test_remove_saved_track_preview_changes_nothing(fake_sp, tools):
    fake_sp.track.return_value = make_track("Redbone", "Childish Gambino")
    result = tools["remove_saved_track"]("spotify:track:1")
    assert "confirm=true" in result
    assert "Redbone by Childish Gambino" in result
    fake_sp.current_user_saved_tracks_delete.assert_not_called()


def test_remove_saved_track_confirm(fake_sp, tools):
    fake_sp.track.return_value = make_track("Redbone", "Childish Gambino")
    result = tools["remove_saved_track"]("spotify:track:1", confirm=True)
    assert result == "Removed Redbone by Childish Gambino from your Liked Songs."
    fake_sp.current_user_saved_tracks_delete.assert_called_once_with(
        ["spotify:track:1"]
    )
