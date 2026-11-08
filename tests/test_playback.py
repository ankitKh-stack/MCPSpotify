"""
Tests for tools/playback.py.

`fake_sp` is the fake Spotify from conftest.py and `tools` holds every tool
by name. Two MagicMock features show up a lot here:
  - fake_sp.X.return_value = ...  decides what fake_sp.X() hands back.
  - fake_sp.X.assert_called_once_with(...) / fake_sp.X.assert_not_called()
    check how the tool used Spotify.
"""

from conftest import make_track


def test_now_playing_nothing(fake_sp, tools):
    fake_sp.current_playback.return_value = None
    assert tools["now_playing"]() == "Nothing is playing right now."


def test_now_playing_formats(fake_sp, tools):
    fake_sp.current_playback.return_value = {
        "item": make_track("Feather", "Nujabes"),
        "progress_ms": 65_000,
        "is_playing": True,
        "device": {"name": "My Laptop"},
    }
    result = tools["now_playing"]()
    assert "Feather" in result
    assert "Nujabes" in result
    assert "1:05 / 3:30" in result
    assert "My Laptop" in result


def test_play_query_no_results(fake_sp, tools):
    fake_sp.search.return_value = {"tracks": {"items": []}}
    result = tools["play"](query="asdfqwer")
    assert "couldn't find" in result
    fake_sp.start_playback.assert_not_called()


def test_play_query_plays_track_inside_its_album(fake_sp, tools):
    # Playing a lone track did nothing on the desktop app, so we play its
    # album starting at that track instead. This test keeps it that way.
    track = make_track("One More Time", "Daft Punk", uri="spotify:track:omt")
    fake_sp.search.return_value = {"tracks": {"items": [track]}}

    result = tools["play"](query="one more time")

    assert result == "Playing One More Time by Daft Punk."
    fake_sp.start_playback.assert_called_once_with(
        device_id="laptop-id",
        context_uri="spotify:album:a1",
        offset={"uri": "spotify:track:omt"},
    )


def test_play_uri_album_uses_context(fake_sp, tools):
    tools["play"](uri="spotify:album:x")
    fake_sp.start_playback.assert_called_once_with(
        device_id="laptop-id", context_uri="spotify:album:x"
    )


def test_no_device_message(fake_sp, tools):
    fake_sp.devices.return_value = {"devices": []}
    assert tools["pause"]() == (
        "Open Spotify on your laptop or phone and play anything once, "
        "then try again."
    )
    fake_sp.pause_playback.assert_not_called()


def test_set_volume_rejects_150(fake_sp, tools):
    assert tools["set_volume"](150) == "Volume must be between 0 and 100."
    fake_sp.volume.assert_not_called()


def test_transfer_by_name_case_insensitive(fake_sp, tools):
    fake_sp.devices.return_value = {
        "devices": [
            {"id": "laptop-id", "name": "My Laptop", "type": "Computer"},
            {"id": "phone-id", "name": "My Phone", "type": "Smartphone"},
        ]
    }
    result = tools["transfer_playback"]("my PHONE")
    assert result == "Moved playback to My Phone."
    fake_sp.transfer_playback.assert_called_once_with("phone-id", force_play=True)


def test_transfer_unknown_lists_devices(fake_sp, tools):
    fake_sp.devices.return_value = {
        "devices": [
            {"id": "laptop-id", "name": "My Laptop", "type": "Computer"},
            {"id": "phone-id", "name": "My Phone", "type": "Smartphone"},
        ]
    }
    result = tools["transfer_playback"]("Kitchen Speaker")
    assert "My Laptop" in result
    assert "My Phone" in result
    fake_sp.transfer_playback.assert_not_called()
