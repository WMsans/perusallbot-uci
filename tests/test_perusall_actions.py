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
