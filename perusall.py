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
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


def _spaces(text: str) -> str:
    """The PDF's text layer writes spaces as a control char (\x15), which no
    sentence splitter treats as a break."""
    return _CONTROL.sub(" ", text)


def _fit(text: str, max_chars: int) -> str:
    """Trim to the last word boundary that fits."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut


def choose_excerpt(
    spans: list[str],
    used: set[str],
    target: float | None = None,
    min_chars: int = 40,
    max_chars: int = 400,
) -> str | None:
    """Unused run of about two sentences, starting where a line starts.

    A window that begins mid-line can start a few characters before a line
    break, and then none of its opening words is inside any one line -- the
    highlight has nothing to find. Windows stride by two lines so a consumed
    excerpt cannot reappear as a shifted duplicate of itself. `target` says
    where in the reading the comment belongs, so a run of comments spreads
    through the document instead of piling up on page one.
    """
    lines = [" ".join(s.split()) for s in spans if len(s.strip()) >= min_chars]
    windows = []
    for start in range(0, len(lines), 2):
        text = lines[start]
        for line in lines[start + 1 :]:
            if len(_SENTENCE_BREAK.findall(text)) >= 2 or len(text) >= max_chars:
                break
            text = f"{text} {line}"
        candidate = _fit(text, max_chars).strip()
        if len(candidate) >= min_chars:
            windows.append(candidate)
    if not windows:
        return None

    want = 0 if target is None else round(min(max(target, 0.0), 1.0) * (len(windows) - 1))
    for i in sorted(range(len(windows)), key=lambda i: (abs(i - want), i)):
        if windows[i] not in used:
            return windows[i]
    return None


ASSIGNMENTS_URL = "https://app.perusall.com/courses/games-and-society-fall-2026/_/assignments"
ROWS = '[role="row"][data-p-index]'
PAGE = ".page-container"
PAGE_TEXT_SPANS = f"{PAGE} .textLayer span"
EDITOR = "div.ql-editor"
POST_BUTTON = 'button[aria-label="Post comment"]'
PREVIEW_PROGRESS = ".preview-pane .my-progress"

# The reader renders only the pages near the viewport, so the text in the DOM is
# whatever is on screen -- page one until something scrolls. These snippets drive
# the reader's scroller; without them the reading is page one, and a passage from
# later in the document is not even in the DOM to be found.
_FIND_SCROLLER = """
  let scroller = document.scrollingElement;
  for (let el = document.querySelector('.page-container');
       el && el !== document.documentElement; el = el.parentElement) {
    const style = getComputedStyle(el);
    if (el.scrollHeight > el.clientHeight + 100 && /(auto|scroll)/.test(style.overflowY)) {
      scroller = el;
      break;
    }
  }
"""

_SCROLL = """([frac, dy]) => {
""" + _FIND_SCROLLER + """
  const max = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
  const before = scroller.scrollTop;
  scroller.scrollTop = frac === null ? before + dy : frac * max;
  return {max, top: scroller.scrollTop, height: scroller.clientHeight,
          down: scroller.scrollTop > before + 0.5};
}"""

_RENDERED_PAGES = """() => {
""" + _FIND_SCROLLER + """
  return Array.from(document.querySelectorAll('.page-container'), (page) => ({
    top: Math.round((page.getBoundingClientRect().top + scroller.scrollTop) / 50),
    lines: Array.from(page.querySelectorAll('.textLayer span'), (s) => s.innerText),
  }));
}"""

# One round trip for every line: the per-span inner_text() version cost a CDP
# call per span, which made walking the document take minutes.
_SPAN_TEXTS = """() => Array.from(
  document.querySelectorAll('.page-container .textLayer span'), (s) => s.innerText)"""

_MAX_SCROLL_STEPS = 200
_SETTLE_MS = 400

# Put the line in the middle of the viewport instead of wherever a minimal
# scroll leaves it: an edge position can sit under the toolbar, and the drag
# then starts on the wrong element.
_CENTER_SPAN = """(i) => {
  const span = document.querySelectorAll('.page-container .textLayer span')[i];
  if (!span) return null;
  span.scrollIntoView({block: 'center', inline: 'nearest'});
  const b = span.getBoundingClientRect();
  return [b.x, b.y, b.width, b.height];
}"""

# A drag that runs off the bottom of a page leaves Perusall with no single page
# to anchor the annotation to, so no editor opens. Index of the page's last span.
_PAGE_END = """(i) => {
  const spans = Array.from(document.querySelectorAll('.page-container .textLayer span'));
  const page = spans[i] && spans[i].closest('.page-container');
  if (!page) return null;
  const own = Array.from(page.querySelectorAll('.textLayer span'));
  return own.length ? spans.indexOf(own[own.length - 1]) : null;
}"""
_SETTLE_STEPS = 4


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


def scroll_reader(page, fraction: float | None = None, dy: float = 0.0) -> dict:
    """Move the reader's scrollbar: to a fraction of the document, or down by `dy`."""
    return page.evaluate(_SCROLL, [fraction, dy])


def rendered_pages(page) -> list[tuple[int, list[str]]]:
    """Each rendered page's position and lines, so pages can be ordered and merged."""
    return [(p["top"], p["lines"]) for p in page.evaluate(_RENDERED_PAGES)]


def document_spans(page) -> list[str]:
    """Every line of the reading, in page order.

    Pages are keyed by their position in the document, so a page that renders
    twice is not duplicated and a page that unmounts is not lost.
    """
    state = scroll_reader(page, 0.0)
    step = max(200, round(state["height"] * 0.8))
    page.wait_for_timeout(_SETTLE_MS)
    pages: dict[int, list[str]] = {}
    for _ in range(_MAX_SCROLL_STEPS):
        pages.update({top: lines for top, lines in rendered_pages(page) if lines})
        if not scroll_reader(page, dy=step)["down"]:
            break
        page.wait_for_timeout(_SETTLE_MS)
    pages.update({top: lines for top, lines in rendered_pages(page) if lines})
    return [_spaces(line) for top in sorted(pages) for line in pages[top]]


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

    A span can hold more than one line, and a short first line may not hold the
    whole opening probe, so the probe is matched *inside* a span and falls back
    to shorter probes.
    """
    needle = " ".join(_spaces(excerpt).split())
    texts = page.evaluate(_SPAN_TEXTS)
    for length in (30, 24, 18, 12):
        probe = needle[:length]
        if not probe:
            continue
        for i, text in enumerate(texts):
            text = " ".join(_spaces(text).split())
            if len(text) >= 10 and probe in text:
                return i
    raise RuntimeError(f"could not find the excerpt on the page: {excerpt[:40]!r}")


def reveal_excerpt(page, excerpt: str, target: float | None = None) -> int:
    """Scroll to the excerpt and return its span index.

    Starts at the position the excerpt was chosen for and walks the document one
    viewport at a time, so every page renders and gets one chance to match.
    """
    state = scroll_reader(page, 0.0)
    steps = max(1, round(state["max"] / max(200, round(state["height"] * 0.8))))
    start = round((target or 0.0) * steps)
    failure = None
    for i in list(range(start, steps + 1)) + list(range(0, start)):
        scroll_reader(page, i / steps)
        page.wait_for_timeout(_SETTLE_MS)
        try:
            return find_span(page, excerpt)
        except RuntimeError as exc:
            failure = exc
    raise failure


def center_span(page, index: int) -> None:
    """Centre the line and wait until the reader stops moving under it.

    A drag that starts while a scroll is still settling selects nothing, and
    Perusall then never opens its comment editor.
    """
    box = page.evaluate(_CENTER_SPAN, index)
    if box is None:
        raise RuntimeError("the reader lost the excerpt's line")
    for _ in range(_SETTLE_STEPS):
        page.wait_for_timeout(_SETTLE_MS)
        again = page.evaluate(_CENTER_SPAN, index)
        if again == box:
            return
        box = again


def highlight(page, excerpt: str, rng, target: float | None = None) -> None:
    """Scroll to the excerpt and drag-select its first lines."""
    spans = page.locator(PAGE_TEXT_SPANS)
    start = reveal_excerpt(page, excerpt, target)

    center_span(page, start)
    start = find_span(page, excerpt)  # indices shift when a page renders

    end = min(start + 2, spans.count() - 1)
    page_end = page.evaluate(_PAGE_END, start)
    if page_end is not None:
        end = min(end, page_end)

    top = spans.nth(start).bounding_box()
    below = spans.nth(end).bounding_box()
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


def post_comment(page, excerpt: str, text: str, rng, target: float | None = None) -> None:
    """Highlight the excerpt's first line, then type the comment into it."""
    import human_type

    # Perusall swallows the odd drag without opening the editor; a second drag on
    # the same passage is harmless, so the run does not die on that one miss.
    for attempt in (1, 2):
        highlight(page, excerpt, rng, target)
        try:
            page.wait_for_selector(EDITOR, timeout=10_000)
            break
        except Exception:
            if attempt == 2 or page.locator(EDITOR).count():
                raise

    page.locator(EDITOR).click()
    human_type.type_like_human(page, text, rng)
    page.locator(POST_BUTTON).click()
