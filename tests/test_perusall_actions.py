from perusall import Requirement, read_requirement


class MissingLocator:
    def inner_text(self):
        raise RuntimeError("not found")

    def count(self):
        return 0


class PresentLocator:
    def inner_text(self):
        return "Post at least 3 comments, questions, or responses (1 remaining)."

    def count(self):
        return 1


class FakePage:
    def __init__(self, locator):
        self._locator = locator

    def locator(self, selector):
        return self._locator

    def wait_for_selector(self, selector, timeout=None):
        return object()


def test_reads_requirement_from_progress_block():
    assert read_requirement(FakePage(PresentLocator())) == Requirement(3, 1)


def test_returns_none_when_progress_block_is_absent():
    assert read_requirement(FakePage(MissingLocator())) is None


# --- excerpt -> span lookup (the bug that killed run 2) -----------------------

from perusall import AssignmentNotFound, choose_excerpt, require_rows  # noqa: E402

FIXTURE_SPANS = [
    "201",
    "Let us move away from the cultures created by games and their players, and",
    "back to the substance of the games themselves. This chapter explores the",
    "importance of narrative in video games. Critics, scholars, and parents alike",
    "have found many reasons to dislike and criticize video games.",
]


class SpanList:
    def __init__(self, texts):
        self.texts = texts

    def count(self):
        return len(self.texts)

    def nth(self, i):
        return self

    def inner_text(self):
        return self.texts[self.i] if hasattr(self, "i") else ""

    def __getitem__(self, i):
        class One:
            def __init__(self, text):
                self.text = text

            def inner_text(self):
                return self.text

        return One(self.texts[i])


class SpanPage:
    def __init__(self, texts):
        self.texts = texts

    def evaluate(self, script, args=None):
        return self.texts

    def locator(self, selector):
        page = self

        class Coll:
            def count(self):
                return len(page.texts)

            def nth(self, i):
                class One:
                    def inner_text(self):
                        return page.texts[i]

                return One()

            def inner_text(self):
                return " ".join(page.texts)

        return Coll()


def test_finds_the_first_excerpt_on_the_page():
    from perusall import find_span

    excerpt = choose_excerpt(FIXTURE_SPANS, used=set())
    assert find_span(SpanPage(FIXTURE_SPANS), excerpt) is not None


def test_finds_the_second_excerpt_even_though_it_starts_mid_span():
    from perusall import find_span

    first = choose_excerpt(FIXTURE_SPANS, used=set())
    second = choose_excerpt(FIXTURE_SPANS, used={first})
    assert second is not None
    assert find_span(SpanPage(FIXTURE_SPANS), second) is not None


def test_reports_a_missing_excerpt_as_a_runtime_error():
    import pytest

    from perusall import find_span

    with pytest.raises(RuntimeError):
        find_span(SpanPage(FIXTURE_SPANS), "text that is definitely not on the page")


class EmptyRows:
    def count(self):
        return 0


def test_absent_assignment_raises_a_named_error():
    import pytest

    with pytest.raises(AssignmentNotFound):
        require_rows(EmptyRows())


# --- picking the first assignment that still needs work -----------------------

from perusall import is_actionable, open_first_assignment  # noqa: E402


def test_a_finished_assignment_is_not_actionable():
    assert is_actionable(Requirement(3, 0)) is False


def test_an_unfinished_assignment_is_actionable():
    assert is_actionable(Requirement(3, 2)) is True


def test_a_non_comment_requirement_is_not_actionable():
    assert is_actionable(None) is False


class Row:
    def __init__(self, page, index):
        self.page, self.index = page, index

    def click(self):
        self.page.clicked_rows.append(self.index)
        self.page.current = self.index


class Rows:
    def __init__(self, page, count):
        self.page, self.count_ = page, count

    def count(self):
        return self.count_

    def nth(self, i):
        return Row(self.page, i)

    @property
    def first(self):
        return Row(self.page, 0)


class Toggle:
    def __init__(self):
        self.clicked = 0

    def get_attribute(self, name):
        return "true"

    def click(self):
        self.clicked += 1


class WorkButton:
    def __init__(self, page):
        self.page = page

    def click(self):
        self.page.work_clicked += 1


class SelectionPage:
    """Two rows: the first already has all its comments, the second does not."""

    def __init__(self, requirements):
        self.requirements = requirements
        self.clicked_rows = []
        self.work_clicked = 0
        self.current = 0

    def goto(self, *a, **kw):
        pass

    def get_by_role(self, role, name=None):
        if role == "switch":
            return Toggle()
        return WorkButton(self)

    def locator(self, selector, has_text=None):
        if "role=\"row\"" in selector or "role='row'" in selector:
            return Rows(self, len(self.requirements))
        return self

    def count(self):
        return 1

    def inner_text(self):
        req = self.requirements[self.current]
        if req is None:
            return "Reply to at least 2 classmates."
        return f"Post at least {req.required} comments, questions, or responses ({req.remaining} remaining)."

    def wait_for_selector(self, selector, timeout=None):
        return object()


def test_skips_assignments_that_already_have_their_comments():
    page = SelectionPage([Requirement(3, 0), Requirement(3, 3)])
    open_first_assignment(page)
    assert page.clicked_rows == [0, 1]
    assert page.work_clicked == 1


def test_starts_at_the_first_incomplete_assignment_without_opening_a_finished_one():
    page = SelectionPage([Requirement(3, 0), Requirement(3, 3), Requirement(3, 1)])
    open_first_assignment(page)
    assert page.work_clicked == 1
    assert page.clicked_rows[-1] == 1


def test_reports_when_every_assignment_is_already_done():
    import pytest

    page = SelectionPage([Requirement(3, 0), Requirement(3, 0)])
    with pytest.raises(AssignmentNotFound):
        open_first_assignment(page)
    assert page.work_clicked == 0


# --- the reader renders lazily, so passages have to be scrolled to ----------
# Regression: every comment landed on page one, because the DOM only ever held
# the pages the reader had rendered and nothing scrolled it.

import pytest  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import perusall  # noqa: E402

PAGE_HEIGHT, VIEWPORT = 1000, 1000


class RenderedSpans:
    def __init__(self, texts):
        self.texts = texts

    def count(self):
        return len(self.texts)

    def nth(self, i):
        texts = self.texts
        return SimpleNamespace(inner_text=lambda: texts[i])


class LazyReader:
    """A reader like Perusall's: only pages overlapping the viewport exist."""

    def __init__(self, pages):
        self.pages = pages
        self.top = 0

    @property
    def max(self):
        return max(0, len(self.pages) * PAGE_HEIGHT - VIEWPORT)

    def evaluate(self, script, args=None):
        if script is perusall._SPAN_TEXTS:
            return [line for i in self.visible() for line in self.pages[i]]
        frac, dy = args if args else (None, 0.0)
        if script is perusall._SCROLL:
            before = self.top
            self.top = min(
                self.max, max(0, frac * self.max if frac is not None else before + dy)
            )
            return {"max": self.max, "top": self.top, "height": VIEWPORT,
                    "down": self.top > before}
        return [{"top": i * PAGE_HEIGHT // 50, "lines": self.pages[i]} for i in self.visible()]

    def visible(self):
        first = int(self.top) // PAGE_HEIGHT
        last = first + 1
        return [i for i in range(first, last + 1) if i < len(self.pages)]

    def wait_for_timeout(self, ms):
        pass

    def locator(self, selector):
        return RenderedSpans([line for i in self.visible() for line in self.pages[i]])


def _page(i):
    return [f"Page {i} opens with a sentence long enough to be an excerpt."]


READER_PAGES = [_page(i) for i in range(6)]


def test_the_whole_document_is_collected_not_just_the_first_page():
    reader = LazyReader(READER_PAGES)
    assert perusall.document_spans(reader) == [line for lines in READER_PAGES for line in lines]


def test_a_passage_from_a_later_page_is_scrolled_to_and_found():
    reader = LazyReader(READER_PAGES)
    excerpt = READER_PAGES[4][0]
    index = perusall.reveal_excerpt(reader, excerpt, target=0.1)  # asked for near the top
    assert reader.locator(perusall.PAGE_TEXT_SPANS).nth(index).inner_text() == excerpt
    assert reader.top > 0


def test_reveal_excerpt_reports_a_passage_that_is_not_there():
    with pytest.raises(RuntimeError):
        perusall.reveal_excerpt(LazyReader(READER_PAGES), "text that is definitely not there")


# --- the PDF text layer writes spaces as a control character -----------------
# Regression: with \x15 instead of " " the sentence splitter never fired, so
# choose_excerpt saw one enormous sentence and handed back page one every time.


def test_control_char_spaces_are_read_as_spaces():
    reader = LazyReader([["L]Vi\x15K^YZd\x15<VbZh\x15=VkZ"]])
    assert perusall.document_spans(reader) == ["L]Vi K^YZd <VbZh =VkZ"]


def test_finds_an_excerpt_when_the_span_uses_control_char_spaces():
    page = SpanPage(["What\x15Video\x15Games\x15Have\x15to\x15Teach\x15Us"])
    assert perusall.find_span(page, "What Video Games Have to Teach Us") == 0


# --- centring the line: a drag during a scroll picks nothing ------------------

class SettlingReader:
    """Same box twice in a row means the reader has stopped moving."""

    def __init__(self, boxes):
        self.boxes = list(boxes)
        self.waits = 0

    def evaluate(self, script, arg=None):
        return self.boxes.pop(0) if len(self.boxes) > 1 else self.boxes[0]

    def wait_for_timeout(self, ms):
        self.waits += 1


def test_centre_waits_until_the_reader_stops_moving():
    reader = SettlingReader([[0, 9, 1, 1], [0, 5, 1, 1], [0, 4, 1, 1], [0, 4, 1, 1]])
    perusall.center_span(reader, 3)
    assert reader.waits == 3


def test_centre_gives_up_on_a_line_the_reader_lost():
    class Gone:
        def evaluate(self, script, arg=None):
            return None

    with pytest.raises(RuntimeError, match="lost"):
        perusall.center_span(Gone(), 3)


def test_finds_an_excerpt_whose_start_straddles_a_line_break():
    # not needed any more: choose_excerpt never starts mid-line. This guards the
    # short-probe fallback anyway, for a window whose first line is short.
    page = SpanPage([
        "the reading distributed via a com-",
        ". In this game you are Solid Snake and the game tells you so",
    ])
    assert perusall.find_span(page, "In this game you are Solid Snake") == 1


# --- a drag that leaves the page opens no editor --------------------------------
# Regression: the excerpt started on the last lines of a page, so the drag ran
# into the next page and Perusall never opened div.ql-editor.


class TwoPageDrag:
    """Span 0 ends page one; the drag must stop there, not run on to span 3."""

    boxes = {i: {"x": 0.0, "y": i * 10.0, "width": 100.0, "height": 8.0} for i in range(4)}
    texts = ["end of the first page", "excerpt starts here and runs on",
             "onto the next page", "and further still"]

    class Mouse:
        def __init__(self):
            self.moved = []

        def move(self, x, y, steps=None):
            self.moved.append((x, y))

        def down(self):
            pass

        def up(self):
            pass

    def __init__(self):
        self.mouse = self.Mouse()

    def evaluate(self, script, arg=None):
        if script is perusall._SPAN_TEXTS:
            return self.texts
        return 1  # page one's last span

    def locator(self, selector):
        boxes = self.boxes

        class Spans:
            def count(self):
                return len(boxes)

            def nth(self, i):
                class One:
                    def bounding_box(self):
                        return boxes[i]

                return One()

        return Spans()


def test_a_drag_stops_at_the_end_of_the_page(monkeypatch):
    page = TwoPageDrag()
    monkeypatch.setattr(perusall, "reveal_excerpt", lambda *a, **k: 1)
    monkeypatch.setattr(perusall, "center_span", lambda *a, **k: None)
    perusall.highlight(page, "excerpt starts here", __import__("random").Random(3))
    assert page.mouse.moved[-1] == (97.0, 14.0)  # span 1, not span 3


# --- a drag Perusall swallows is retried once, not fatal ----------------------


class EditorPage:
    """wait_for_selector fails `misses` times, then the editor is there."""

    def __init__(self, misses):
        self.misses = misses
        self.typed = ""
        self.posted = 0
        self.keyboard = SimpleNamespace(type=self._type)

    def _type(self, ch):
        self.typed += ch

    def wait_for_selector(self, selector, timeout=None):
        if self.misses:
            self.misses -= 1
            raise TimeoutError("div.ql-editor never appeared")
        return object()

    def locator(self, selector):
        page = self

        class Stub:
            def count(self):
                return 0

            def click(self):
                if selector == perusall.POST_BUTTON:
                    page.posted += 1

        return Stub()


def _stub_highlight(monkeypatch, calls):
    def fake(page, excerpt, rng, target=None):
        calls.append(excerpt)

    monkeypatch.setattr(perusall, "highlight", fake)


def test_a_swallowed_drag_is_retried_once(monkeypatch):
    calls = []
    _stub_highlight(monkeypatch, calls)
    page = EditorPage(misses=1)
    perusall.post_comment(page, "an excerpt", "hi", __import__("random").Random(1))
    assert len(calls) == 2 and page.posted == 1


def test_two_swallowed_drags_still_stop_the_run(monkeypatch):
    calls = []
    _stub_highlight(monkeypatch, calls)
    page = EditorPage(misses=2)
    with pytest.raises(TimeoutError):
        perusall.post_comment(page, "an excerpt", "hi", __import__("random").Random(1))
    assert page.posted == 0
