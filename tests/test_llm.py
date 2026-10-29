import subprocess

import pytest

import llm


def test_ask_invokes_pi_print_mode(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["input"] = kw.get("input")
        return subprocess.CompletedProcess(cmd, 0, stdout="  a comment  \n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert llm.ask("PROMPT", "deepseek/deepseek-flash") == "a comment"
    assert seen["cmd"][:2] == ["pi", "-p"]
    assert "--model" in seen["cmd"] and "deepseek/deepseek-flash" in seen["cmd"]
    assert "--no-tools" in seen["cmd"]


def test_ask_without_model_omits_the_flag(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert llm.ask("PROMPT", None) == "ok"
    assert "--model" not in seen["cmd"]


def test_ask_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, stdout="", stderr="boom"),
    )
    with pytest.raises(llm.LlmError):
        llm.ask("PROMPT", None)


def test_write_insight_rejects_empty_output(monkeypatch):
    monkeypatch.setattr(llm, "ask", lambda prompt, model: "   ")
    with pytest.raises(llm.LlmError):
        llm.write_insight("an excerpt", "Chapter 7", None)


LONG = " ".join(["I keep coming back to how the chapter frames narrative"] * 12)


def test_write_insight_passes_excerpt_into_the_prompt(monkeypatch):
    seen = {}

    def fake_ask(prompt, model):
        seen["prompt"] = prompt
        return LONG

    monkeypatch.setattr(llm, "ask", fake_ask)
    out = llm.write_insight("excerpt about stories", "Chapter 7", None)
    assert "excerpt about stories" in seen["prompt"]
    assert "Chapter 7" in seen["prompt"]
    assert out.startswith("I keep coming back")
    assert str(llm.MIN_WORDS) in seen["prompt"]


def test_ask_gives_up_when_pi_hangs(monkeypatch):
    def hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(subprocess, "run", hang)
    with pytest.raises(llm.LlmError):
        llm.ask("PROMPT", None)


def test_parse_models_reads_provider_and_id_columns():
    table = (
        "provider   model             context  max-out\n"
        "deepseek   deepseek-flash    1M       384K\n"
        "opencode   claude-opus-5     1M       128K\n"
    )
    assert llm.parse_models(table) == [
        "deepseek/deepseek-flash",
        "opencode/claude-opus-5",
    ]


def test_list_models_surfaces_a_pi_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="nope"),
    )
    with pytest.raises(llm.LlmError):
        llm.list_models()


def test_write_insight_rejects_a_comment_worth_of_words_short(monkeypatch):
    short = " ".join(["A sentence that is too short to count"] * 5)
    monkeypatch.setattr(llm, "ask", lambda prompt, model: short)
    with pytest.raises(llm.LlmError, match="words"):
        llm.write_insight("an excerpt", "Chapter 7", None)


def test_write_insight_accepts_a_hundred_words(monkeypatch):
    hundred = " ".join(["word"] * 100)
    monkeypatch.setattr(llm, "ask", lambda prompt, model: hundred)
    assert llm.write_insight("an excerpt", "Chapter 7", None) == hundred
