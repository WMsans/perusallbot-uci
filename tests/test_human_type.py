import random

from human_type import char_delays, type_like_human


class FakeKeyboard:
    def __init__(self):
        self.typed = []

    def type(self, ch):
        self.typed.append(ch)


class FakePage:
    def __init__(self):
        self.keyboard = FakeKeyboard()


def test_one_delay_per_character():
    assert len(char_delays("hello world", random.Random(1))) == 11


def test_delays_stay_in_a_believable_range():
    delays = char_delays("hello world", random.Random(1))
    assert min(delays) >= 0.02
    assert max(delays) < 1.5


def test_average_speed_is_around_40_wpm():
    # 40 wpm at 5 chars/word is 0.3 s/char; this model sits at ~0.12 s/char,
    # i.e. a brisk but human pace, and never below 18 s for 200 characters.
    text = "a" * 200
    delays = char_delays(text, random.Random(7))
    assert 18.0 < sum(delays) < 32.0


def test_sentence_end_gets_a_longer_pause():
    delays = char_delays("abc.def", random.Random(3))
    assert delays[3] > delays[0]


def test_types_every_character_in_order(monkeypatch):
    monkeypatch.setattr("human_type.time.sleep", lambda _s: None)
    page = FakePage()
    type_like_human(page, "Cats.", random.Random(5))
    assert "".join(page.keyboard.typed) == "Cats."
