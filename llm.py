"""Comment generation through the local `pi` CLI."""

import subprocess

PI = "pi"
PI_TIMEOUT_S = 120
_BASE_ARGS = [
    "-p",
    "--no-tools",
    "--no-extensions",
    "--no-skills",
    "--no-prompt-templates",
    "--no-context-files",
    "--no-session",
]

_PROMPT = """You are a student in a Games & Society seminar, adding one marginal
comment to a reading called "{title}".

The passage you highlighted:
---
{excerpt}
---

Write one comment on that passage with real insight: notice something specific
about what the author claims, or connect it to an implication they leave
unstated. Two to four sentences, first person, under 60 words, plain prose. Do
not open with "This chapter" or "The author". Reply with the comment only."""


class LlmError(Exception):
    pass


def ask(prompt: str, model: str | None) -> str:
    cmd = [PI, *_BASE_ARGS]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PI_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise LlmError(f"pi did not answer within {PI_TIMEOUT_S}s") from exc
    if proc.returncode != 0:
        raise LlmError(f"pi exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def write_insight(excerpt: str, doc_title: str, model: str | None) -> str:
    out = ask(_PROMPT.format(title=doc_title, excerpt=excerpt), model)
    if len(out) < 20:
        raise LlmError(f"pi returned no usable comment: {out!r}")
    return out
