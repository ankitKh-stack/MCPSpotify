# Learning Log

One entry per build step: what was built, the key idea, what went wrong and how it was fixed, and the new words you met.

---

## Step 1 — Scaffolding the project

**What was built**
- A git repository, so every change is saved with a message and can be undone.
- A Python project managed by **uv**: `pyproject.toml`, `.python-version` and `uv.lock`, plus the libraries we need (`mcp`, `spotipy`, `python-dotenv`, and `pytest` for tests).
- `.gitignore`, which lists files git must never save, especially `.env` and `.spotify_cache`.
- `.env.example`, a blank template for your secrets file.
- An empty `tools/__init__.py`, which turns the `tools` folder into a package we can import from.

**Key idea**
A project is code *plus* a description of what it needs to run. `pyproject.toml` is that description: anyone with uv can run `uv sync` and get exactly the same setup. Secrets are kept *out* of the code and out of git, so the code can be shared safely.

**What went wrong and how it was fixed**
- `uv init` assumed the newest Python on this machine (3.14) and wrote `requires-python = ">=3.14"`. Then `uv python pin 3.12` refused, because 3.12 is lower than 3.14. Fix: change the line to `>=3.10`, as the design says, then pin 3.12.
- The plan's check used `spotipy.__version__`, but spotipy doesn't provide that. Fix: ask Python's package records instead with `importlib.metadata.version("spotipy")`.

**Words you met**
- **Library / package:** code someone else wrote that you can reuse. `spotipy` talks to Spotify for us; `mcp` lets us talk to Claude.
- **Python package (folder):** a folder of `.py` files containing an `__init__.py`, so you can write `from tools import playback`.
- **Virtual environment (`.venv`):** a private box of libraries for this one project. Other projects on your computer can't break it, and it can't break them.
- **uv:** the tool that creates that box, installs libraries into it, and runs your code inside it (`uv run ...`).
- **`pyproject.toml`:** the project's ID card: its name, Python version and the libraries it needs.
- **`uv.lock`:** the exact versions uv installed, written down so the setup can be repeated identically.
- **`.python-version`:** tells uv which Python to use here (3.12). uv downloaded it for us.
- **git / repository / commit:** git saves snapshots of your files. A repository is the project folder plus its history. A commit is one saved snapshot with a message.
- **`.gitignore`:** a list of files git should pretend don't exist.

---

## Step 2 — Logging in to Spotify (`spotify_client.py`)

**What was built**
- `spotify_client.py`, which reads your settings from `.env`, logs you in through Spotify's approval page, and saves your login token to `.spotify_cache`.
- `get_spotify()`, which the tools will call to get one shared, logged-in connection.
- Friendly errors for a missing `.env`, an empty setting, or not being logged in yet.

**Key idea**
Our program never sees your Spotify password. You approve our app on Spotify's own site, and Spotify gives the program a **token**: a limited, expiring pass that only allows what you approved (the scopes). The token is saved, so you approve once and later runs just reuse it.

**What went wrong and how it was fixed**
Nothing broke this step. Both error messages were tested before you created the app: no `.env` at all, and a `.env` with blank values.

**Words you met**
- **API:** a set of web addresses a service offers so programs can ask it for things ("what's playing?") or tell it to do things ("pause").
- **HTTP request / status code:** each question to the API is a request. The answer comes with a number: 200 means OK, 401 means not logged in, 403 means not allowed, 404 means not found, 429 means "too many requests, slow down".
- **OAuth:** the standard way to let an app act for you without giving it your password. It's like a **valet key**: the valet can drive and park the car, but can't open the trunk.
- **Client ID / Client Secret:** your app's username and password with Spotify. They identify the *app*, not you. The secret stays in `.env`.
- **Scopes:** the specific permissions the token carries. We ask for 12, which you saw listed on the approval page.
- **Redirect URI:** where Spotify sends your browser after you approve (`http://127.0.0.1:8888/callback`). `127.0.0.1` means "this computer". spotipy briefly listens there to catch the reply.
- **Access token / refresh token:** the access token is the short-lived pass, valid for about an hour. The refresh token lets the program quietly get a new access token without asking you again. Both live in `.spotify_cache`, so treat that file like a password.
- **Environment variable:** a named setting available to a program (`SPOTIFY_CLIENT_ID=...`). `load_dotenv` reads `.env` and turns each line into one.
- **`Path(__file__).parent`:** "the folder this file is in". Using it means `.env` is found no matter which folder the program was started from.
- **Exception / `raise`:** how Python signals "something went wrong, stop here". `SpotifyToolError` is our own kind, carrying a message that's safe to show you.
- **`if __name__ == "__main__":`:** code under this line runs only when you start the file directly, not when another file imports it.

---

## Step 3 — First win: the MCP server and four tools

**What was built**
- `server.py`: creates the MCP server, asks `tools/playback.py` to add its tools, and runs over stdio.
- `tools/playback.py`: `now_playing`, `play`, `pause`, `next_track`.
- In `spotify_client.py`: `pick_device` (laptop or phone?), `get_target_device_id`, and the `spotify_errors` decorator that turns errors into friendly sentences.
- The server is registered with Claude Code (`claude mcp add --scope user spotify ...`), and asking "What's playing?" in Claude Code returned the right song.

**Key idea**
An MCP server is a menu of tools. Claude reads each tool's name, docstring and parameters, then decides which one to call. Our code only has to *do* things and describe them clearly. Claude handles understanding what you asked for.

**What went wrong and how it was fixed**
- **Playing a single track did nothing.** Spotify accepted `start_playback(uris=[track])`, but the desktop app stayed silent. Albums, resume and skip all worked. We tested one cause at a time: three different songs all failed, so it wasn't the song. Playing the track *inside its album, starting at that song* worked every time, so `play` now does that. Side effect: the album keeps playing after the song ends.
- **Pausing twice** made Spotify answer with a 403 error ("Restriction violated"). Our first message wrongly blamed development-mode limits, so we added a specific, accurate message.
- **Searching for nonsense still plays something.** Spotify's search always finds a closest match. Nothing to fix.
- **`/mcp spotify`** isn't a command in the desktop app. Seeing the `spotify` tools in a new session is the real proof it connected.

**Words you met**
- **MCP (Model Context Protocol):** a standard way for an AI app (the *client*, Claude Code) to use tools provided by a program (the *server*, ours).
- **Tool:** one action the server offers, like `pause`. Its docstring is the description Claude reads.
- **stdio (standard input/output):** the two text channels every program has, the ones behind `input()` and `print()`. Claude Code and our server send messages to each other through them. That's why the server must **never** `print()`: stray text would corrupt the conversation. Logs go to `spotify_mcp.log` instead.
- **Decorator (`@something`):** a function that wraps another function to add behaviour. `@mcp.tool()` means "offer this as a tool", and `@spotify_errors` means "turn errors into friendly replies". They apply from the bottom up.
- **`functools.wraps`:** makes the wrapper keep the original function's name, docstring and parameters, so Claude still sees them.
- **The `register(mcp)` pattern:** each tools file has a `register` function that `server.py` calls with the server. Tools files never import `server.py`, which avoids two files importing each other in a loop.
- **Import:** `import spotify_client` loads another `.py` file so you can use what's inside it. `from tools import playback` loads a file from the `tools` package.
- **Logging:** writing diagnostic messages to a file instead of the screen.
- **Context (Spotify):** a collection Spotify plays through, such as an album, playlist or artist. A *context URI* names one, for example `spotify:album:...`.
- **URI:** Spotify's address for an item, like `spotify:track:2e3Ea0o24lReQFR4FA7yXH`.

---

## Step 4a — The rest of the playback tools

**What was built**
- 9 more tools in `tools/playback.py`: `previous_track`, `set_volume`, `list_devices`, `transfer_playback`, `shuffle`, `repeat`, `seek`, `get_queue`, `add_to_queue`. The server now has 13 tools.
- `format_track` in `spotify_client.py`: one line per track, ending with its URI, so Claude always has the address it needs to act on a track.
- Rate-limit handling in the `spotify_errors` decorator: on a 429, wait and retry once, but only if Spotify asks for 30 seconds or less.

**Key idea**
**Check inputs before calling Spotify.** `set_volume(150)`, `repeat("sometimes")` and `seek(-5)` get a clear answer right away, without a round trip to Spotify and a confusing error back. And because every tool shares one decorator, a single change (the 429 retry) protected all 13 tools at once.

**What went wrong and how it was fixed**
- Nothing broke live. All 9 tools were tested on the laptop, and your volume, shuffle and repeat settings were restored afterwards. You tested moving playback to your phone and back through Claude Code.
- A real 429 can't be produced on demand, so the retry was tested with a fake one in three cases: a short wait (retries and succeeds), a two-hour wait (doesn't wait, explains), and two in a row (gives up after one retry).
- Added a message for phones that refuse remote volume changes (`VOLUME_CONTROL_DISALLOW`). Without it, you'd get the misleading "development mode" message.

**Words you met**
- **Rate limit / HTTP 429:** Spotify limits how many requests an app can make in a short time. Going over gets a 429 reply meaning "slow down". It's like a shop letting only so many people in at once.
- **Header / `Retry-After`:** extra labelled information attached to a reply. `Retry-After: 5` means "try again in 5 seconds".
- **Loop (`for attempt in (1, 2)`):** repeat a block of code. Here it allows at most two tries. `continue` jumps to the next try; `return` leaves the function completely.
- **Input validation:** checking that a value makes sense (0–100 for volume) before using it.
- **`casefold()`:** turns text to a standard lowercase so "My Phone" equals "my phone". It handles more languages than `lower()`.
- **Milliseconds (ms):** thousandths of a second. Spotify measures positions in ms, so `seek` multiplies seconds by 1000.
- **Slicing (`items[:10]`):** takes the first 10 items of a list.
- **`enumerate`:** loops over a list and numbers the items as it goes (1, 2, 3...).

---

## Step 4b — Search and library tools

**What was built**
- `tools/library.py` with 11 tools: `search`, `get_my_playlists`, `get_top_items`, `get_recently_played`, `get_saved_tracks`, `save_current_track`, `remove_saved_track`, `get_artist_tracks`, `get_album_tracks`, `follow_artist`, `get_followed_artists`.
- One new line in `server.py`, `library.register(mcp)`. The server now has 24 tools.

**Key idea**
**Confirm before destroying.** `remove_saved_track` has a `confirm` parameter that starts as `false`. The first call only *describes* what would happen ("This will remove Around the World by Daft Punk..."). The docstring tells Claude to show you that preview and wait for your yes before calling again with `confirm=true`. We tested it: the preview changed nothing, and only the confirmed call removed the song.

Also, adding a whole new file of tools took one line in `server.py`. That's the payoff of the `register(mcp)` layout you chose.

**What went wrong and how it was fixed**
- **Playlist search returned nothing for "lofi study".** Spotify said there were 203 matches, but sent several back as empty slots (`None`), probably playlists hidden from development-mode apps. Asking for 3 got 3 empty slots. Fix: always ask for 10, throw away the empty ones, then keep as many as were asked for.
- **`get_artist_tracks` found only 5 Daft Punk songs.** The strict filter `artist:"Daft Punk"` matched only 5 tracks. Fix: search for the plain name, then keep tracks where one of the artists is a match. That gave 9 of their best-known songs.
- Library-changing tools were tested so nothing changed for good: like a song, preview, confirm the removal, then check Liked Songs were back to how they were. Following was tested on an artist you already follow.

**Words you met**
- **Destructive action:** something that deletes or changes your data and can't be undone easily.
- **Preview / confirm pattern:** describe the change first, act only after an explicit yes.
- **`None`:** Python's "nothing here" value. Spotify's empty slots arrive as `None`, so code must expect and skip them.
- **List comprehension (`[x for x in items if x]`):** a one-line way to build a new list from an old one, here keeping only the non-empty items.
- **Clamping:** forcing a number into a range. `clamp(50, 1, 10)` gives 10.
- **Search filter:** extra syntax in a search, like `artist:"Name"` or `genre:jazz`, that narrows results.
- **Time range:** Spotify's windows for "top" lists. `short_term` is about 4 weeks, `medium_term` about 6 months, `long_term` about a year.
