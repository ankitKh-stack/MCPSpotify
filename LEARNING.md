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
