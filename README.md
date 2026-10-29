# perusallbot-uci

Finishes a Perusall reading assignment on its own. You log in; the bot finds the
assignment, writes a comment about a real passage, runs it through
[humanizeai.pro](https://www.humanizeai.pro/), then types it into Perusall one
character at a time and posts it. It repeats until the assignment's required
comment count is met.

Sibling of [pollevbot-uci](https://github.com/?/pollevbot-uci): same idea (you
do the Duo login, the bot does the rest), plus the typing feel of `fake_typer`
done through the browser instead of OS keystrokes.

## Why Patchright, not Selenium

humanizeai.pro sits behind Cloudflare Turnstile, and Turnstile's own docs say
automation suites are detected as bots. A plain Selenium/CDP browser gets the
humanize call rejected with `403` and then the whole site blocked. Patchright is
a Playwright drop-in that patches the CDP tells Turnstile looks for, so the same
workflow passes. Perusall needs none of this; it is just along for the ride in
the same browser.

## Prerequisites

- `uv` and a Linux/WSL environment with a display (`DISPLAY` set; WSLg is fine)
- `pi` on `PATH` (`/usr/bin/pi`) with a provider already authenticated
- A Perusall account, and Duo to get into it

## Setup

```bash
uv sync
uv run patchright install chromium
```

(`patchright install chrome` wants sudo and fails in WSL — use `chromium`.)

## Run

```bash
uv run main.py --model deepseek/deepseek-flash
```

A Chrome window opens on your course's assignments list. **Log in there
yourself** (UCI SSO + Duo), then press Enter in the terminal. The bot takes over
from there: it opens the first assignment in the list and starts posting.

| Flag | Meaning |
| --- | --- |
| `--model <pattern>` | `pi` model used to write comments, e.g. `deepseek/deepseek-flash`, `openrouter/...`. Default: whatever `pi` uses. |
| `--assignment <text>` | Only pick an assignment whose name contains this text. |
| `--count <n>` | Post at most `n` comments this run. |
| `--humanizer web\|llm` | `web` (default) uses humanizeai.pro. `llm` skips it and rewrites with `pi` instead. |

Exit code `0` means the requirement was met (or your `--count` cap was reached).

## When it stops

- **Requirement met** — done.
- **The requirement isn't a comment count** (reply to classmates, checkpoints,
  read every page) — it aborts before posting anything.
- **The humanizer blocks us** — the run stops immediately. Nothing is retried and
  nothing falls back on its own; already-posted comments stay posted. Wait out
  the block, or rerun with `--humanizer llm`.
- **The posted count doesn't move** — it reloads the reader once, rechecks, and
  gives up if the count still hasn't changed.
- **No unused passages left**, or more than 20 minutes elapsed — it gives up.

## Known gaps

- **Comments already on the page are not detected.** The bot only avoids
  passages it used earlier in the *same* run. Pointing it at an assignment you
  (or a previous run) already commented on can highlight the same passage twice.
- It posts top-level comments only. It does not reply to classmates or answer
  checkpoints.
- One course, one assignment per run: the assignments list URL is hard-coded in
  `perusall.py` (`ASSIGNMENTS_URL`).
- Typing speed is a single constant (`human_type.BASE_DELAY`, ~0.12 s per key). Raise it
  if the typing looks mechanical.

## Layout

| File | Responsibility |
| --- | --- |
| `main.py` | CLI, the posting loop, stop rules |
| `perusall.py` | assignments list, reader, composer (all selectors live here) |
| `humanizer.py` | humanizeai.pro client, block detection, `llm` mode |
| `llm.py` | comment generation through `pi -p` |
| `human_type.py` | per-character keystroke timing |
| `tests/` | unit tests; no browser needed |

Design and plan: `docs/superpowers/specs/`, `docs/superpowers/plans/`.
