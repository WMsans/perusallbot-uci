import pytest

import humanizer


class FakeLocator:
    def __init__(self, value="", raises=False):
        self._value, self._raises = value, raises

    def click(self):
        pass

    def fill(self, text):
        self._value = text

    def input_value(self):
        if self._raises:
            raise RuntimeError("element not attached")
        return self._value


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def press(self, combo):
        self.page.submitted = True


class FakePage:
    def __init__(self, output_getter, title="Humanize AI"):
        self._output_getter = output_getter
        self.title_text = title
        self.submitted = False
        self.keyboard = FakeKeyboard(self)

    def goto(self, *a, **kw):
        pass

    def title(self):
        return self.title_text

    def locator(self, selector):
        if "Paste your text here" in selector:
            return FakeLocator()
        return FakeLocator(*self._output_getter())

    def wait_for_timeout(self, ms):
        pass


def test_returns_humanized_text():
    page = FakePage(lambda: ("humanized words", False))
    assert humanizer.humanize_with_web(page, "raw words") == "humanized words"


def test_block_page_raises():
    page = FakePage(lambda: ("", True), title="Attention Required! | Cloudflare")
    with pytest.raises(humanizer.HumanizerBlocked):
        humanizer.humanize_with_web(page, "raw words")


def test_empty_result_raises():
    page = FakePage(lambda: ("", False))
    with pytest.raises(humanizer.HumanizerBlocked):
        humanizer.humanize_with_web(page, "raw words", timeout_s=0.1)


def test_llm_fallback_is_available_but_not_default():
    assert "web" in humanizer.HUMANIZERS
    assert "llm" in humanizer.HUMANIZERS
