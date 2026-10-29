from perusall import choose_excerpt

SPANS = [
    "201",
    "Let us move away from the cultures created by games and their players, and",
    "back to the substance of the games themselves. This chapter explores the",
    "importance of narrative in video games. Critics, scholars, and parents alike",
    "have found many reasons to dislike and criticize video games.",
]


def test_skips_page_number_and_returns_sentences():
    excerpt = choose_excerpt(SPANS, used=set())
    assert excerpt is not None
    assert not excerpt.startswith("201")
    assert "importance of narrative" in excerpt


def test_respects_min_chars():
    assert choose_excerpt(["201", "short line"], used=set()) is None


def test_skips_already_used_excerpt():
    first = choose_excerpt(SPANS, used=set())
    second = choose_excerpt(SPANS, used={first})
    assert first is not None and second is not None
    assert second != first


def test_returns_none_when_everything_is_used():
    first = choose_excerpt(SPANS, used=set())
    assert choose_excerpt(SPANS, used={first}) is not None
    used = {first, choose_excerpt(SPANS, used={first})}
    assert choose_excerpt(SPANS, used=used) is None


def test_caps_length():
    long = ["word " * 300]
    excerpt = choose_excerpt(long, used=set(), max_chars=400)
    assert excerpt is not None and len(excerpt) <= 400
