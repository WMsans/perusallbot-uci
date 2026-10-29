from perusall import Requirement, parse_requirement

LIVE = """Your assignment requires you to:

Post at least 3 comments, questions, or responses (0 remaining).

No suggestions for you right now."""


def test_parses_the_live_block():
    assert parse_requirement(LIVE) == Requirement(required=3, remaining=0)


def test_parses_partial_progress():
    text = "Post at least 3 comments, questions, or responses (2 remaining)."
    assert parse_requirement(text) == Requirement(required=3, remaining=2)


def test_returns_none_for_a_different_requirement():
    text = "Your assignment requires you to: Reply to at least 2 classmates."
    assert parse_requirement(text) is None


def test_returns_none_for_empty_text():
    assert parse_requirement("") is None
