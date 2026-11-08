# Spotify MCP server

A small local server that lets Claude Code control and query your Spotify
account. You can ask "What's playing?", "Turn it down to 30%", or "Make me a
20-song lo-fi focus playlist" and Claude uses the tools here to do it.

It runs only on your computer, talks to Claude Code over stdio, and uses
your own Spotify developer app. You need **Spotify Premium**, because Spotify
only allows playback control for Premium accounts.

## Setup

1. **Install uv**, the tool that runs the project and its Python:
   `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows
   (see [docs.astral.sh/uv](https://docs.astral.sh/uv/) for other systems).
2. **Get the project** into a folder that is *not* synced to the cloud , then open a terminal in that folder.
3. **Install the dependencies:** `uv sync`
4. **Create a Spotify app** at
   [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
   → *Create app*. Tick **Web API**.
5. **Add the redirect URI** in the app's settings, exactly:
   `http://127.0.0.1:8888/callback` (use `127.0.0.1`, not `localhost`).
6. **Fill in `.env`:** copy `.env.example` to `.env` and paste your app's
   Client ID and Client Secret into it. Never share or commit this file.
7. **Log in once:** `uv run python spotify_client.py`. Your browser opens;
   approve access. It prints "Logged in as …" and saves your login to
   `.spotify_cache`.
8. **Register the server with Claude Code** (use your own folder path):
   `claude mcp add spotify --scope user -- uv run --directory "C:\path\to\MCPSpotify" python server.py`
9. **Check it:** in Claude Code, run `/mcp` and look for *spotify ✓ connected*.
10. **Try it:** open Spotify, play anything, and ask Claude "What's playing?"

## Running the tests

```
uv run pytest -v
```

The tests use a fake Spotify connection, so they run in under a second and
never touch your account.

## Troubleshooting

| What you see | What to do |
|---|---|
| `INVALID_CLIENT` or "redirect URI mismatch" during login | The redirect URI in the dashboard must match `.env` exactly: `http://127.0.0.1:8888/callback`. Also check the Client ID and Secret in `.env`. |
| "Open Spotify on your laptop or phone and play anything once…" | Spotify can only be controlled when one of your devices has the app open. Open it and press play once. |
| Your device disappears after a while | Spotify drops idle devices after a few minutes of no playback. Play something in the app again. |
| "Spotify blocked this request… development mode" | Apps in development mode can't use some features, such as reading other people's playlists. That's Spotify's rule, not a bug. |
| "Your Spotify login expired…" or you want to log in as someone else | Delete `.spotify_cache` and run `uv run python spotify_client.py` again. |
| Something else went wrong | Full error details are in `spotify_mcp.log` in the project folder. |
| New tools don't show up after a code change | In Claude Code, run `/mcp` and reconnect the spotify server. |

## Safety note

- **Don't choose "always allow" for `remove_from_playlist` or
  `remove_saved_track`.** These tools show a preview first and only act when
  called again with `confirm=true`. Approving each call yourself keeps a
  person in the loop before anything is deleted.

## Tools (28)

**Playback:** `now_playing`, `play` (resume, a URI, or a search), `pause`,
`next_track`, `previous_track`, `set_volume`, `list_devices`,
`transfer_playback`, `shuffle`, `repeat`, `seek`, `get_queue`, `add_to_queue`

**Search and library:** `search`, `get_my_playlists`, `get_top_items`,
`get_recently_played`, `get_saved_tracks`, `save_current_track`,
`remove_saved_track`, `get_artist_tracks`, `get_album_tracks`,
`follow_artist`, `get_followed_artists`

**Playlists:** `create_playlist`, `add_to_playlist`, `remove_from_playlist`,
`get_playlist_tracks`

### Limits from Spotify (February 2026 rules for development-mode apps)

- Search returns at most 10 results at a time, so building a 20-song
  playlist takes a few searches.
- You can only read the tracks of playlists you created yourself.
- Spotify's official "top tracks of an artist" list is gone;
  `get_artist_tracks` uses filtered search results instead.

## Files

- `server.py`: starts the MCP server and registers the tools
- `spotify_client.py`: login, choosing a device, and friendly error messages
- `tools/`: the tools, grouped into playback, library and playlists
- `tests/`: the automated tests
- `LEARNING.md`: notes on what was built and learned at each step
