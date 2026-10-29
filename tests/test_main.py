import random
from types import SimpleNamespace

import main
from humanizer import HumanizerBlocked
from perusall import Requirement

EXCERPT = "An excerpt long enough to be chosen by the selector, certainly."
POOL = [f"{EXCERPT} {i}" for i in range(5)]


def make_args(**kw):
    defaults = dict(count=None, humanizer="web", model=None, assignment=None)
    return SimpleNamespace(**{**defaults, **kw})


def wire(monkeypatch, remaining_sequence, block_on_post=None):
    """Wire every collaborator. Returns (posted, reloads) records."""
    seq = list(remaining_sequence)
    posted, reloads = [], []

    monkeypatch.setattr(
        main,
        "read_requirement",
        lambda page: Requirement(3, seq.pop(0)) if seq else Requirement(3, 0),
    )
    monkeypatch.setattr(main, "page_spans", lambda page: list(POOL))

    def fake_choose(spans, used, **kw):
        for span in spans:
            if span not in used:
                return span
        return None

    monkeypatch.setattr(main, "choose_excerpt", fake_choose)
    monkeypatch.setattr(main, "doc_title", lambda page: "Chapter 7")
    monkeypatch.setattr(main, "write_insight", lambda e, t, m: "A comment about it.")
    monkeypatch.setattr(main, "humanize", lambda text, page, h, m: text)
    monkeypatch.setattr(main, "reload_reader", lambda page: reloads.append(1))

    def fake_post(page, excerpt, text, rng):
        if block_on_post is not None and len(posted) == block_on_post:
            raise HumanizerBlocked("blocked")
        posted.append(text)

    monkeypatch.setattr(main, "post_comment", fake_post)
    return posted, reloads


def test_stops_when_requirement_is_met(monkeypatch):
    posted, _ = wire(monkeypatch, [3, 2, 1, 0])
    assert main.run(None, None, make_args(), random.Random(1)) == 0
    assert len(posted) == 3


def test_reloads_once_then_stops_when_count_does_not_move(monkeypatch):
    posted, reloads = wire(monkeypatch, [3, 3, 3, 3])
    assert main.run(None, None, make_args(), random.Random(1)) != 0
    assert len(posted) == 1
    assert len(reloads) == 1


def test_aborts_without_posting_when_requirement_is_not_comments(monkeypatch):
    posted, _ = wire(monkeypatch, [])
    monkeypatch.setattr(main, "read_requirement", lambda page: None)
    assert main.run(None, None, make_args(), random.Random(1)) != 0
    assert posted == []


def test_humanizer_block_aborts_after_the_posts_already_made(monkeypatch):
    posted, _ = wire(monkeypatch, [3, 2, 1, 0], block_on_post=1)
    assert main.run(None, None, make_args(), random.Random(1)) != 0
    assert len(posted) == 1


def test_stops_when_excerpts_run_out(monkeypatch):
    posted, _ = wire(monkeypatch, [5, 5, 5, 5])
    monkeypatch.setattr(main, "choose_excerpt", lambda spans, used, **kw: None)
    assert main.run(None, None, make_args(), random.Random(1)) != 0
    assert posted == []
