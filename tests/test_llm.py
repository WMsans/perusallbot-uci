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


def test_write_insight_passes_excerpt_into_the_prompt(monkeypatch):
    seen = {}

    def fake_ask(prompt, model):
        seen["prompt"] = prompt
        return "I keep coming back to how the chapter treats narrative."

    monkeypatch.setattr(llm, "ask", fake_ask)
    out = llm.write_insight("excerpt about stories", "Chapter 7", None)
    assert "excerpt about stories" in seen["prompt"]
    assert "Chapter 7" in seen["prompt"]
    assert out.startswith("I keep coming back")
