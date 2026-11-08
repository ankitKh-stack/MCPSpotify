"""
Tests for spotify_client.py: picking a device, login checks, and the
error safety net (spotify_errors).

Every test follows the same three steps, often called Arrange-Act-Assert:
  1. Arrange: set up the situation (fake data, fake Spotify replies).
  2. Act: call the code being tested.
  3. Assert: check the result. `assert x == y` makes the test fail if not.
"""

from unittest.mock import MagicMock

import pytest
from spotipy.exceptions import SpotifyOauthError

import spotify_client
from conftest import spotify_error
from spotify_client import SpotifyToolError, pick_device, spotify_errors

# ---------------------------------------------------------------------------
# pick_device
# ---------------------------------------------------------------------------


def test_pick_device_prefers_active():
    devices = [
        {"type": "Computer", "is_active": False},
        {"type": "Smartphone", "is_active": True},
    ]
    assert pick_device(devices)["type"] == "Smartphone"


def test_pick_device_falls_back_to_computer():
    devices = [
        {"type": "Smartphone", "is_active": False},
        {"type": "Computer", "is_active": False},
    ]
    assert pick_device(devices)["type"] == "Computer"


def test_pick_device_empty_returns_none():
    assert pick_device([]) is None


# ---------------------------------------------------------------------------
# Login and settings
# ---------------------------------------------------------------------------


def test_get_spotify_not_logged_in(monkeypatch):
    # A fake login helper whose saved token is unusable (None).
    fake_auth = MagicMock()
    fake_auth.validate_token.return_value = None
    monkeypatch.setattr(spotify_client, "build_auth_manager", lambda: fake_auth)
    # Make sure no connection from an earlier run is reused.
    monkeypatch.setattr(spotify_client, "_spotify", None)

    # pytest.raises checks that the code inside raises this error.
    with pytest.raises(SpotifyToolError) as caught:
        spotify_client.get_spotify()
    assert "uv run python spotify_client.py" in str(caught.value)


def test_missing_env_names_path(monkeypatch, tmp_path):
    # tmp_path is a fixture built into pytest: an empty temporary folder.
    missing = tmp_path / "no-such.env"
    monkeypatch.setattr(spotify_client, "ENV_PATH", missing)

    with pytest.raises(SpotifyToolError) as caught:
        spotify_client.build_auth_manager()
    assert str(missing) in str(caught.value)


# ---------------------------------------------------------------------------
# spotify_errors: rate limits (429)
# ---------------------------------------------------------------------------


def test_retry_on_short_429(monkeypatch):
    sleeps = []
    # Replace time.sleep so the test doesn't actually wait; just record it.
    monkeypatch.setattr(spotify_client.time, "sleep", sleeps.append)
    calls = []

    @spotify_errors
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise spotify_error(429, headers={"Retry-After": "1"})
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 2  # first try + one retry
    assert sleeps == [1]


def test_long_429_gives_message(monkeypatch):
    sleeps = []
    monkeypatch.setattr(spotify_client.time, "sleep", sleeps.append)
    calls = []

    @spotify_errors
    def limited():
        calls.append(1)
        raise spotify_error(429, headers={"Retry-After": "7200"})

    result = limited()
    assert "7200" in result
    assert sleeps == []  # never waited two hours
    assert len(calls) == 1


def test_second_429_in_a_row_gives_message(monkeypatch):
    monkeypatch.setattr(spotify_client.time, "sleep", lambda seconds: None)
    calls = []

    @spotify_errors
    def always_limited():
        calls.append(1)
        raise spotify_error(429, headers={"Retry-After": "2"})

    assert "try again in 2 seconds" in always_limited()
    assert len(calls) == 2  # retried once, then gave up


# ---------------------------------------------------------------------------
# spotify_errors: other errors
# ---------------------------------------------------------------------------


def test_refresh_failure_explains_relogin(fake_sp, tools):
    fake_sp.current_playback.side_effect = SpotifyOauthError("refresh failed")
    assert "uv run python spotify_client.py" in tools["now_playing"]()


def test_403_explains_dev_mode(fake_sp, tools):
    fake_sp.current_user_top_tracks.side_effect = spotify_error(403, "Forbidden")
    assert "development mode" in tools["get_top_items"]()


def test_403_restriction_violated_explained(fake_sp, tools):
    fake_sp.pause_playback.side_effect = spotify_error(
        403, "Player command failed: Restriction violated"
    )
    assert "already paused" in tools["pause"]()
