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


def test_reads_requirement_from_progress_block():
    assert read_requirement(FakePage(PresentLocator())) == Requirement(3, 1)


def test_returns_none_when_progress_block_is_absent():
    assert read_requirement(FakePage(MissingLocator())) is None
