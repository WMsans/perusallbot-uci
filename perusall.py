import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    required: int
    remaining: int


_REQUIREMENT = re.compile(
    r"Post at least (\d+) comments?, questions?, or responses?\s*\((\d+) remaining\)",
    re.IGNORECASE,
)


def parse_requirement(progress_text: str) -> Requirement | None:
    m = _REQUIREMENT.search(progress_text)
    if not m:
        return None
    return Requirement(int(m.group(1)), int(m.group(2)))


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def _fit(text: str, max_chars: int) -> str:
    """Trim to the last word boundary that fits."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut


def choose_excerpt(
    spans: list[str],
    used: set[str],
    min_chars: int = 40,
    max_chars: int = 400,
) -> str | None:
    """First unused run of 1-2 sentences from the page text.

    Windows stride by two sentences so a consumed excerpt cannot reappear as a
    shifted duplicate of itself.
    """
    body = " ".join(s.strip() for s in spans if len(s.strip()) >= min_chars)
    sentences = [s for s in _SENTENCE_BREAK.split(body) if s.strip()]
    for start in range(0, len(sentences), 2):
        candidate = _fit(" ".join(sentences[start : start + 2]), max_chars).strip()
        if len(candidate) < min_chars or candidate in used:
            continue
        return candidate
    return None


ASSIGNMENTS_URL = "https://app.perusall.com/courses/games-and-society-fall-2026/_/assignments"
ROWS = '[role="row"][data-p-index]'
PAGE_TEXT_SPANS = ".page-container .textLayer span"
EDITOR = "div.ql-editor"
POST_BUTTON = 'button[aria-label="Post comment"]'
PREVIEW_PROGRESS = ".preview-pane .my-progress"


class AssignmentNotFound(Exception):
    """No assignment row matched."""


def read_requirement(page, selector: str = ".my-progress") -> Requirement | None:
    """Read the progress bubble, giving the panel a moment to render."""
    try:
        page.wait_for_selector(selector, timeout=10_000)
    except Exception:
        return None
    loc = page.locator(selector)
    try:
        if loc.count() == 0:
            return None
        return parse_requirement(loc.inner_text())
    except Exception:
        return None


def page_spans(page) -> list[str]:
    return page.locator(PAGE_TEXT_SPANS).all_inner_texts()


def doc_title(page) -> str:
    return (page.title() or "").split("|")[0].strip()


def reload_reader(page) -> None:
    page.reload()
    page.wait_for_selector(".page-container", timeout=60_000)


def require_rows(rows):
    """Fail loudly when nothing matched, instead of a click timeout."""
    if rows.count() == 0:
        raise AssignmentNotFound("no assignment in the list matched")
    return rows


def is_actionable(requirement: Requirement | None) -> bool:
    """An assignment worth starting: a comment quota that is not yet met."""
    return requirement is not None and requirement.remaining > 0


def open_first_assignment(page, name: str | None = None) -> None:
    """Open the first assignment that still needs comments.

    Finished assignments are skipped, not opened and abandoned: entering one
    just replays "you already have 3 comments".
    """
    page.goto(ASSIGNMENTS_URL)
    for label in ("Hide past due", "Preview"):
        toggle = page.get_by_role("switch", name=label)
        if toggle.get_attribute("aria-checked") == "false":
            toggle.click()

    rows = require_rows(page.locator(ROWS, has_text=name) if name else page.locator(ROWS))
    for i in range(rows.count()):
        rows.nth(i).click()
        requirement = read_requirement(page, PREVIEW_PROGRESS)
        if not is_actionable(requirement):
            continue
        page.get_by_role("button", name="Work on assignment").click()
        page.wait_for_selector(".page-container", timeout=60_000)
        return
    raise AssignmentNotFound("every assignment in the list is already done")


def find_span(page, excerpt: str) -> int:
    """Index of the span where the excerpt starts.

    An excerpt can begin mid-line (sentence windows do not respect line
    breaks), so the probe is matched *inside* a span, not only at its start.
    Fall back to shorter probes when the opening words straddle two spans.
    """
    needle = " ".join(excerpt.split())
    spans = page.locator(PAGE_TEXT_SPANS)
    count = spans.count()
    for length in (30, 24, 18, 12):
        probe = needle[:length]
        if not probe:
            continue
        for i in range(count):
            text = " ".join(spans.nth(i).inner_text().split())
            if len(text) >= 10 and probe in text:
                return i
    raise RuntimeError(f"could not find the excerpt on the page: {excerpt[:40]!r}")


def post_comment(page, excerpt: str, text: str, rng) -> None:
    """Highlight the excerpt's first line, then type the comment into it."""
    import human_type

    spans = page.locator(PAGE_TEXT_SPANS)
    start = find_span(page, excerpt)

    top = spans.nth(start).bounding_box()
    below = spans.nth(min(start + 2, spans.count() - 1)).bounding_box()
    if not top or not below:
        raise RuntimeError("excerpt is not on screen; scroll it into view first")

    # Precursor cross-references pointer activity against keystrokes, so the
    # selection is made with a curved drag rather than an instant jump.
    start_x, start_y = top["x"] + 3, top["y"] + top["height"] / 2
    end_x, end_y = below["x"] + below["width"] - 3, below["y"] + below["height"] / 2
    page.mouse.move(start_x - 80, start_y - 40, steps=rng.randint(6, 14))
    page.mouse.move(start_x, start_y, steps=rng.randint(5, 12))
    page.mouse.down()
    page.mouse.move(end_x, end_y, steps=rng.randint(14, 30))
    page.mouse.up()

    page.wait_for_selector(EDITOR, timeout=30_000)
    page.locator(EDITOR).click()
    human_type.type_like_human(page, text, rng)
    page.locator(POST_BUTTON).click()
