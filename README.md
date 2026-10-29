# perusallbot-uci

Finishes a Perusall reading assignment on its own. You log in; the bot finds the
assignment, writes a comment about a real passage, runs it through
[humanizeai.pro](https://www.humanizeai.pro/), then types it into Perusall one
character at a time and posts it. It repeats until the assignment's required
comment count is met.

## Prerequisites

- `uv` and a Linux/WSL environment with a display (`DISPLAY` set; WSLg is fine)
- `pi` on `PATH` (`/usr/bin/pi`) with a provider already authenticated
- `fzf` on `PATH` for the model picker (without it, `pi`'s default model is used)
- A Perusall account, and Duo to get into it

## Setup

```bash
uv sync
uv run patchright install chromium
```

(`patchright install chrome` wants sudo and fails in WSL. Please use `chromium`.)

## Run

```bash
uv run main.py
```

First an `fzf` list of every model `pi` can run appears — pick the one that
writes the comments (Esc uses `pi`'s default). Then a Chrome window opens on
your course's assignments list. **Log in there yourself** (UCI SSO + Duo), then
press Enter in the terminal. The bot takes over from there: it walks the list,
skips anything already finished or already satisfied, and opens the first
assignment that still needs comments.

| Flag | Meaning |
| --- | --- |
| `--model <pattern>` | Skip the picker and use this model, e.g. `deepseek/deepseek-flash`, `openrouter/...`. |
| `--assignment <text>` | Only pick an assignment whose name contains this text. |
| `--count <n>` | Post at most `n` comments this run. |
| `--humanizer web\|llm` | `web` (default) uses humanizeai.pro. `llm` skips it and rewrites with `pi` instead. |

Exit code `0` means the requirement was met (or your `--count` cap was reached).

## When it stops

- **Requirement met** — done.
- **Every assignment in the list is already done** — it says so and exits
  without opening anything; finished assignments are checked and skipped.
- **The requirement isn't a comment count** (reply to classmates, checkpoints,
  read every page) — it aborts before posting anything.
- **The humanizer blocks us** — the run stops immediately. Nothing is retried and
  nothing falls back on its own; already-posted comments stay posted. Wait out
  the block, or rerun with `--humanizer llm`.
- **The posted count doesn't move** — it reloads the reader once, rechecks, and
  gives up if the count still hasn't changed.
- **No unused passages left**, or more than 20 minutes elapsed — it gives up.

## Layout

| File | Responsibility |
| --- | --- |
| `main.py` | CLI, fzf model picker, the posting loop, stop rules |
| `perusall.py` | assignments list, reader, composer (all selectors live here) |
| `humanizer.py` | humanizeai.pro client, block detection, `llm` mode |
| `llm.py` | comment generation through `pi -p`, model list for the picker |
| `human_type.py` | per-character keystroke timing |
| `tests/` | unit tests; no browser needed |
