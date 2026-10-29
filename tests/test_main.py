import random
from types import SimpleNamespace

import pytest

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
    monkeypatch.setattr(main, "document_spans", lambda page: list(POOL))

    def fake_choose(spans, used, **kw):
        for span in spans:
            if span not in used:
                return span
        return None

    monkeypatch.setattr(main, "choose_excerpt", fake_choose)
    monkeypatch.setattr(main, "doc_title", lambda page: "Chapter 7")
    monkeypatch.setattr(main, "write_insight", lambda e, t, m, **kw: "A comment about it.")
    monkeypatch.setattr(main, "humanize", lambda text, page, h, m: text)
    monkeypatch.setattr(main, "reload_reader", lambda page: reloads.append(1))

    def fake_post(page, excerpt, text, rng, target=None):
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


def test_llm_failure_stops_before_posting(monkeypatch):
    from llm import LlmError

    posted, _ = wire(monkeypatch, [3, 2, 1, 0])
    monkeypatch.setattr(main, "write_insight", lambda e, t, m, **kw: (_ for _ in ()).throw(LlmError("pi died")))
    assert main.run(None, None, make_args(), random.Random(1)) != 0
    assert posted == []


def test_an_unexpected_browser_error_stops_instead_of_raising(monkeypatch):
    posted, _ = wire(monkeypatch, [3, 2, 1, 0])

    def exploding_post(page, excerpt, text, rng, target=None):
        raise RuntimeError("excerpt not found")

    monkeypatch.setattr(main, "post_comment", exploding_post)
    assert main.run(None, None, make_args(), random.Random(1)) != 0


# --- the fzf model picker ----------------------------------------------------

def test_picker_returns_the_fzf_selection(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw.get("input")
        return SimpleNamespace(stdout="opencode/claude-opus-5\n", returncode=0)

    monkeypatch.setattr(main, "list_models", lambda: ["deepseek/deepseek-flash", "opencode/claude-opus-5"])
    monkeypatch.setattr(main.subprocess, "run", fake_run)
    assert main.pick_model() == "opencode/claude-opus-5"
    assert seen["cmd"][0] == "fzf"
    assert "deepseek/deepseek-flash" in seen["input"]


def test_picker_falls_back_to_pi_default_when_dismissed(monkeypatch):
    monkeypatch.setattr(main, "list_models", lambda: ["deepseek/deepseek-flash"])
    monkeypatch.setattr(
        main.subprocess, "run", lambda cmd, **kw: SimpleNamespace(stdout="", returncode=130)
    )
    assert main.pick_model() is None


def test_picker_falls_back_when_fzf_is_missing(monkeypatch):
    def no_fzf(cmd, **kw):
        raise FileNotFoundError("fzf")

    monkeypatch.setattr(main, "list_models", lambda: ["deepseek/deepseek-flash"])
    monkeypatch.setattr(main.subprocess, "run", no_fzf)
    assert main.pick_model() is None


def test_picker_falls_back_when_the_model_list_fails(monkeypatch):
    from llm import LlmError

    def broken():
        raise LlmError("pi --list-models died")

    monkeypatch.setattr(main, "list_models", broken)
    assert main.pick_model() is None


def stop_before_the_browser(monkeypatch, calls):
    def boom(*a, **kw):
        calls.append("browser")
        raise RuntimeError("stop")

    monkeypatch.setattr(main, "sync_playwright", boom)


def test_explicit_model_flag_skips_the_picker(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "pick_model", lambda: calls.append("picker"))
    stop_before_the_browser(monkeypatch, calls)
    monkeypatch.setattr(main.sys, "argv", ["main.py", "--model", "deepseek/deepseek-flash"])
    with pytest.raises(RuntimeError):
        main.main()
    assert calls == ["browser"]


def test_no_model_flag_opens_the_picker(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "pick_model", lambda: calls.append("picker") or "opencode/claude-opus-5")
    stop_before_the_browser(monkeypatch, calls)
    monkeypatch.setattr(main.sys, "argv", ["main.py"])
    with pytest.raises(RuntimeError):
        main.main()
    assert calls == ["picker", "browser"]


# --- even spread through the reading ----------------------------------------

def test_each_comment_targets_its_own_share_of_the_reading(monkeypatch):
    targets = []

    def fake_choose(spans, used, **kw):
        targets.append(kw.get("target"))
        for span in spans:
            if span not in used:
                return span
        return None

    wire(monkeypatch, [3, 2, 1, 0])
    monkeypatch.setattr(main, "choose_excerpt", fake_choose)
    assert main.run(None, None, make_args(), random.Random(1)) == 0
    assert [round(t, 2) for t in targets] == [0.17, 0.5, 0.83]


def test_targets_stay_inside_the_document_when_count_is_capped(monkeypatch):
    targets = []

    def fake_choose(spans, used, **kw):
        targets.append(kw.get("target"))
        for span in spans:
            if span not in used:
                return span
        return None

    wire(monkeypatch, [3, 2, 1, 0])
    monkeypatch.setattr(main, "choose_excerpt", fake_choose)
    main.run(None, None, make_args(count=2), random.Random(1))
    assert [round(t, 2) for t in targets] == [0.25, 0.75]


def test_a_humanizer_that_trims_the_comment_does_not_become_the_comment(monkeypatch):
    long_text = " ".join(["word"] * 120)
    monkeypatch.setattr(main.humanizer, "humanize_with_llm", lambda text, model: "tiny rewrite")
    assert main.humanize(long_text, None, "llm", None) == long_text


def test_a_humanizer_that_keeps_the_length_is_used(monkeypatch):
    long_text = " ".join(["word"] * 120)
    rewrite = " ".join(["rewritten"] * 120)
    monkeypatch.setattr(main.humanizer, "humanize_with_llm", lambda text, model: rewrite)
    assert main.humanize(long_text, None, "llm", None) == rewrite
