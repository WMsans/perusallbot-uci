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


# --- spreading comments through the document, not the first page ------------

DOCO = [f"Sentence {i} here and it is long enough to be an excerpt." for i in range(20)]


def sentence_number(excerpt):
    return int(excerpt.split()[1])


def test_targets_spread_the_comments_across_the_reading():
    numbers = [
        sentence_number(choose_excerpt(DOCO, set(), target=t)) for t in (1 / 6, 0.5, 5 / 6)
    ]
    assert numbers == sorted(numbers)
    assert numbers[0] >= 4  # not back on page one
    assert numbers[-1] >= 14  # out near the end
    assert numbers[1] - numbers[0] >= 2 and numbers[-1] - numbers[1] >= 2


def test_the_whole_document_is_in_play():
    assert sentence_number(choose_excerpt(DOCO, set(), target=1.0)) == 18
    assert sentence_number(choose_excerpt(DOCO, set(), target=0.0)) == 0


def test_a_taken_window_falls_back_to_its_closest_neighbour():
    mid = choose_excerpt(DOCO, set(), target=0.5)
    again = choose_excerpt(DOCO, {mid}, target=0.5)
    assert again is not None and again != mid


def test_the_title_line_is_never_annotated():
    for target in (0.0, 0.5, 1.0):
        excerpt = choose_excerpt(SPANS, used=set(), target=target)
        assert excerpt is not None and "Narrative in Video Games" not in excerpt


# --- windows start at a line start so the highlight can find them ------------

THREE_LINES = [
    "Line one is long enough to be kept as a line of text here.",
    "Line two ends a sentence. Line three begins here and is long enough.",
    "Line four continues that sentence and ends it right here. Done.",
]


def test_a_window_starts_where_a_line_starts():
    # The old sentence windows could open a few characters before a line break,
    # where no single line holds the opening words and the highlight gave up.
    for target in (0.0, 0.5, 1.0):
        excerpt = choose_excerpt(THREE_LINES, set(), target=target)
        assert excerpt is not None
        assert any(excerpt.startswith(line) for line in THREE_LINES)


def test_windows_are_about_two_sentences_long():
    excerpt = choose_excerpt(THREE_LINES, set(), target=0.0)
    assert excerpt is not None and excerpt.count(".") >= 2
