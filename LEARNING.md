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
