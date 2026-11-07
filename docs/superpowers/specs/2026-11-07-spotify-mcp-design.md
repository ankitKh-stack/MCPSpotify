# Spotify MCP Server — Design

Date: 2026-11-07
Source PRD: `PRD_ Spotify MCP Server for Claude Code.pdf` (in the user's `#API KEYS/PRD` folder, outside this repo). This doc records the PRD plus every decision made since; where they differ, this doc wins.

## Intent and why

A local MCP server in Python that lets Claude Code control and query the user's Spotify Premium account in natural language ("what's playing?", "skip this", "make me a lo-fi playlist").

The primary purpose is **learning**. The user is new to Python, OAuth and HTTP APIs. A working server matters, but the code being understandable to a beginner matters as much. The user chose the split-module layout specifically because it is more of a learning challenge.

## Goals

- Control playback from Claude Code (play, pause, skip, volume, devices, shuffle, repeat, seek, queue).
- Search Spotify; read library, playlists, top items, recently played, followed artists.
- Create and edit playlists; like/unlike tracks; follow artists.
- The user learns MCP server structure, Python modules, and the Spotify OAuth flow by reading the code and `LEARNING.md`.

## Non-goals

- Hosted or multi-user deployment. One user, local only.
- Any GUI.
- Audio streaming or downloading.
- Stretch goals from the PRD (mood playlist tool, MCP resources, MCP prompts) — deferred until the MVP works; revisit afterwards.

## Anti-goals (failure even if it "works")

- Code the user cannot follow: clever one-liners, heavy abstraction, metaprogramming, undocumented magic.
- Secrets in source code or in git history.
- Anything printed to stdout other than MCP protocol messages (breaks stdio transport).
- Destructive changes to the user's library without an explicit confirm step.
- Returning raw Spotify API JSON dumps to Claude.

## Constraints

### Environment (verified)
- Windows 11; Python 3.14 installed, uv 0.13.7, Node 24 (for MCP Inspector), git 2.52.
- Project root is the existing `MCPSpotify/` folder (not a `spotify-mcp/` subfolder as in the PRD). Not yet a git repo — `git init` happens during scaffolding.
- Pin the project to **Python 3.12** via uv (`requires-python = ">=3.10"`, `.python-version` = 3.12) for library compatibility.

### Spotify API — February 2026 development-mode restrictions (verified 2026-11-07)
The user's app will be a new development-mode app, so all of these apply:
- **Removed:** Get Artist's Top Tracks; `POST /users/{id}/playlists` (use `POST /me/playlists`); Get User's Playlists for arbitrary users (use `GET /me/playlists`); old save/remove/follow endpoints (replaced by `PUT/DELETE /me/library` taking a `uris` array, and `GET /me/library/contains`).
- **Renamed:** playlist `/tracks` endpoints → `/playlists/{id}/items`; playlist object field `tracks` → `items` (and `.track` → `.item`). Album track collections keep `tracks`.
- **Search:** `limit` max 10 (default 5).
- **Removed fields:** `popularity`, `available_markets`, `label`, artist `followers`, user `product`/`email`/`country`. Do not display or depend on them.
- Only the user's *own* playlists return their items; others return metadata only.
- App owner must hold Premium (user does). Max 5 users per dev app (irrelevant — single user).
- Still available: player endpoints, add to queue, get queue, top items, recently played, `GET /me/following`, `GET /me/playlists`, search, get album / album tracks, get artist.
- **spotipy >= 2.26** is required (first release using `/items` and `/me/library`). Where spotipy has no wrapper for a needed endpoint, call it through spotipy's low-level request methods rather than adding another HTTP library.

Sources: developer.spotify.com Feb 2026 changelog and migration guide; spotipy 2.26.0 release notes.

## Approaches considered

| | Layout | Trade-off |
|---|---|---|
| A | PRD's two files: `spotify_client.py` + `server.py` holding all ~30 tools | Fewest concepts; matches MCP tutorials; `server.py` grows to 600–800 lines |
| **B (chosen)** | `spotify_client.py` + `tools/` package split by area + thin `server.py` | Short focused files, easier per-step review; introduces Python packages/imports and multi-file tool registration; deviates from PRD structure |

**User picked B** because it is more of a challenge and therefore more to learn.

## Project structure

```
MCPSpotify/
  server.py              # creates the FastMCP server, registers every tool module, runs stdio
  spotify_client.py      # auth, token cache, device picking, rate-limit retry, error translation
  tools/
    __init__.py
    playback.py          # now_playing, play, pause, next/previous, volume, devices, transfer,
                         # shuffle, repeat, seek, get_queue, add_to_queue
    library.py           # search, get_my_playlists, get_top_items, get_recently_played,
                         # get_saved_tracks, save_current_track, remove_saved_track,
                         # get_artist_tracks, get_album_tracks, follow_artist, get_followed_artists
    playlists.py         # create_playlist, add_to_playlist, remove_from_playlist, get_playlist_tracks
  tests/                 # pytest, mocked spotipy client, one test file per tools module + client
  docs/superpowers/specs/
  .env.example           # blank template; copy to .env and fill in
  .env                   # real secrets (gitignored, never committed)
  .spotify_cache         # login token (gitignored)
  .gitignore             # .env, .spotify_cache, .venv, __pycache__, logs
  pyproject.toml
  README.md
  LEARNING.md
```

**SDK note (verified 2026-11-07):** current `mcp` is 2.3, where `FastMCP` was renamed `MCPServer` (`from mcp.server.mcpserver import MCPServer`). "FastMCP" below means `MCPServer`.

### How the tool modules attach to the server (decided)
Each `tools/*.py` module exposes one function, `register(mcp)`, which defines its tools with `@mcp.tool()` inside it. `server.py` creates the single `FastMCP` instance and calls `playback.register(mcp)`, `library.register(mcp)`, `playlists.register(mcp)`. This avoids circular imports (tool modules never import `server.py`) and makes the wiring visible in one place — a deliberate teaching point.

Tool modules get the Spotify client by calling a function from `spotify_client.py` (e.g. `get_spotify()`), which lazily creates and caches one authenticated spotipy client.

## Tools

All tools: typed parameters and a clear docstring (these become the descriptions Claude reads). Return short human-readable strings or small dicts — never raw API dumps.

### Playback (`tools/playback.py`)
- `now_playing()` — track, artist, album, progress, device.
- `play(query: str | None = None, uri: str | None = None)` — no args resumes; `uri` plays it; `query` searches and plays the best match (track, album or playlist).
- `pause()`, `next_track()`, `previous_track()`
- `set_volume(percent: int)` — validated 0–100.
- `list_devices()`
- `transfer_playback(device: str)` — **accepts a device name or ID** (case-insensitive name match), so "move it to my phone" works. Differs from PRD's `device_id` parameter.
- `shuffle(on: bool)`, `repeat(mode: str)` — mode in track / context / off.
- `seek(position_seconds: int)`
- `get_queue()`, `add_to_queue(uri: str)`

### Search and library (`tools/library.py`)
- `search(query: str, type: str = "track", limit: int = 10)` — types track/artist/album/playlist; limit clamped to 1–10 (API max).
- `get_my_playlists(limit: int = 20)` — via `GET /me/playlists`.
- `get_top_items(type: str = "tracks", time_range: str = "medium_term")`
- `get_recently_played(limit: int = 20)`
- `get_saved_tracks(limit: int = 20)`
- `save_current_track()` — via `PUT /me/library`.
- `remove_saved_track(uri: str, confirm: bool = False)` — destructive, see below.
- **`get_artist_tracks(artist_name: str)`** — replaces the PRD's `get_artist_top_tracks` (endpoint removed). Runs a track search with `artist:"<name>"`, returns up to 10. Docstring must say these are search results, not Spotify's official top tracks.
- `get_album_tracks(album_id: str)`
- `follow_artist(artist_id: str)` — via `PUT /me/library` with the artist URI.
- `get_followed_artists()` — via `GET /me/following`.

### Playlists (`tools/playlists.py`)
- `create_playlist(name: str, description: str = "", public: bool = False)` — via `POST /me/playlists`.
- `add_to_playlist(playlist_id: str, uris: list[str])` — via `/items`.
- `remove_from_playlist(playlist_id: str, uris: list[str], confirm: bool = False)` — destructive.
- `get_playlist_tracks(playlist_id: str, limit: int = 50)` — via `/items`; read `items[].item`.

### Destructive actions
`remove_from_playlist`, `remove_saved_track`, and any future tool that replaces playlist contents take `confirm: bool = False`. With `confirm=False` nothing changes and the tool returns a preview ("This will remove 12 tracks from Late Night Coding. Call again with confirm=true to proceed."). Docstring tells Claude to show the preview to the user and wait for a yes.

**Enforcement (builder's call):** docstring-only, as the PRD specifies — no server-side preview token. Second safety net: Claude Code asks the user to approve each MCP tool call unless they allow it permanently; the README advises not to permanently allow the destructive tools.

**Tool list completeness:** the 28 tools above are the full PRD list (with `get_artist_top_tracks` → `get_artist_tracks`). No unfollow-artist or like-by-URI tool — not in the PRD; can be added later (unfollow would need the confirm rule).

## OAuth and configuration

### Where secrets live (user decision)
`.env` and `.spotify_cache` live in the **project root**, as in the PRD, both gitignored. The path contains `OneDrive`, but checked 2026-11-07: no OneDrive account is signed in on this machine, so the folder does not sync. If the user ever signs into OneDrive, these two files would start uploading — the README notes this.
- Paths are resolved relative to `spotify_client.py`'s own location (not the current working directory), because Claude Code launches the server from elsewhere.
- If `.env` is missing, the error message prints the exact path where it is expected.

### OAuth
- `.env` holds `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback`.
- spotipy `SpotifyOAuth` (Authorization Code flow), token cached at `<project root>\.spotify_cache`, auto-refresh.
- Scopes (exactly these): `user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-modify-private playlist-modify-public user-library-read user-library-modify user-top-read user-read-recently-played user-follow-read user-follow-modify`.
- Running `python spotify_client.py` directly performs the first-time browser login and prints a confirmation (stdout is fine here — it is not running as the MCP server).
- When running as the MCP server, the browser login must not be attempted silently; if no valid token exists, tools return a message telling the user to run `uv run python spotify_client.py`.

## Device handling (in `spotify_client.py`)

1. Use the active device if any (including a phone — do not switch away from it).
2. Otherwise the first device with type `Computer`.
3. Otherwise any available device.
4. None found → "Open Spotify on your laptop or phone and play anything once, then try again."
Commands that need a device pass its ID explicitly. Note in docs: idle devices can vanish from the list until Spotify is reopened.

## Error handling (in `spotify_client.py`)

- No active device → clear message plus the list of available devices.
- Expired token → spotipy refreshes; if refresh fails → explain how to log in again.
- HTTP 429 → wait `Retry-After` seconds, retry once.
- 403 from a restricted endpoint → explain it is a Spotify development-mode restriction, not a bug.
- All logging goes to stderr or a log file. Never stdout.
- Text from Spotify (track names, playlist descriptions) is untrusted data — returned as data, never interpreted as instructions.

## Build plan and pacing

PRD's six steps, with a **hard pause after each** for the user to read and ask questions:
1. Scaffold project, uv, dependencies, git init, `.gitignore`, `.env.example`.
2. Auth in `spotify_client.py`; verify with first-run login. *(User must create the Spotify developer app and fill `.env` here — walk them through it.)*
3. `now_playing`, `play`, `pause`, `next_track`; test in MCP Inspector. **First-win milestone**: register with Claude Code and get "What's playing?" working before step 4.
4. Remaining playback tools, then library tools, then playlist tools.
5. Error handling hardening, pytest suite, README (setup in under 10 steps).
6. End-to-end checks in Claude Code.

**Who writes the code:** Claude writes all code (per the PRD: "Claude Code explains as it builds"). The user reads, asks questions at each pause, and drives the manual steps (Spotify dashboard, `.env`, browser login, Claude Code registration). Execution is live in one session, not handed off.

**Tests timing (builder's call):** follow the PRD order — tools are verified by hand in MCP Inspector during steps 3–4, and the pytest suite is written in step 5. This keeps pytest concepts out of the early teaching load.

## Teaching requirements

- Plain, explicit code; comments explain *why*. No clever one-liners.
- After each file: plain-language explanation of what it does and why it is structured that way.
- Define each new concept the first time it appears, assuming zero background, with an everyday analogy (OAuth, access/refresh tokens, scopes, HTTP status codes, decorators, stdio, Python packages/imports, the `register(mcp)` pattern, rate limits).
- `LEARNING.md`: one entry per build step — what was built, the key idea, what went wrong and how it was fixed, plus a short "words you met this step" glossary.

## Testing

- pytest unit tests per tools module with a mocked spotipy client (including no-device, 429, and confirm=False preview cases).
- Manual: MCP Inspector (`npx @modelcontextprotocol/inspector`).
- End-to-end in Claude Code: "What's playing?", "Skip this", "Make me a 20-song lo-fi focus playlist" (Claude does the searching via `search` + `create_playlist` + `add_to_playlist`; multiple searches needed due to the 10-result cap).

Registration: `claude mcp add spotify -- uv run --directory "<path to MCPSpotify>" python server.py`.

## Acceptance criteria

- All MVP tools work against the user's real Premium account.
- First-run login completes in the browser; later runs need no login.
- Clear errors for no active device and expired auth.
- README explains setup from scratch in under 10 steps.

## Left to the builder

- Exact mcp SDK version and FastMCP import path (verify against current SDK docs at scaffold time).
- Exact spotipy method names for `/me/library` and `/me/playlists` in 2.26+, or low-level calls where no wrapper exists.
- Formatting of tool return strings.
- Test fixture design.
