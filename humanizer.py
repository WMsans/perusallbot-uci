"""Turn generated text into something that reads as human writing."""

import time

import llm

URL = "https://www.humanizeai.pro/"
INPUT = 'textarea[placeholder="Paste your text here"]'
OUTPUT = "#rich-textarea"

# Any of these in the page title means Cloudflare stopped serving us.
_BLOCK_WORDS = ("attention required", "just a moment", "blocked")

_REWRITE = """Rewrite this so it does not read as machine-written. Keep the
meaning and roughly the length. Reply with the rewritten text only.

{text}"""


class HumanizerBlocked(Exception):
    """The humanizer refused us. The run stops; we never retry."""


def _blocked(page) -> bool:
    title = (page.title() or "").lower()
    return any(word in title for word in _BLOCK_WORDS)


def humanize_with_web(page, text: str, timeout_s: float = 40) -> str:
    page.goto(URL)
    page.locator(INPUT).fill(text)
    page.keyboard.press("Control+Enter")

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _blocked(page):
            raise HumanizerBlocked(f"humanizeai.pro blocked us: {page.title()!r}")
        try:
            out = page.locator(OUTPUT).input_value()
        except Exception:
            out = ""
        if out.strip():
            return out.strip()
        page.wait_for_timeout(500)

    raise HumanizerBlocked("humanizeai.pro returned nothing before the timeout")


def humanize_with_llm(text: str, model: str | None = None) -> str:
    out = llm.ask(_REWRITE.format(text=text), model)
    if not out.strip():
        raise HumanizerBlocked("llm humanizer returned nothing")
    return out.strip()


HUMANIZERS = {"web": humanize_with_web, "llm": humanize_with_llm}
