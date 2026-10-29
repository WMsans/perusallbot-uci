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
