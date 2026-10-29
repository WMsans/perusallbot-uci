"""Comment generation through the local `pi` CLI."""

import subprocess

PI = "pi"
PI_TIMEOUT_S = 120
MIN_WORDS = 100
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
unstated. First person, plain prose, at least {min_words} words — take the space
to develop the thought properly, since a longer, more substantive comment is
better than a short one. Do not open with "This chapter" or "The author". Reply
with the comment only."""


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
    prompt = _PROMPT.format(title=doc_title, excerpt=excerpt, min_words=MIN_WORDS)
    out = ask(prompt, model)
    words = len(out.split())
    if words < MIN_WORDS:
        raise LlmError(f"pi returned {words} words, under the {MIN_WORDS} the comment needs: {out!r}")
    return out


def list_models() -> list[str]:
    """Every model pi can run, as `provider/model`, for the picker."""
    try:
        proc = subprocess.run(
            [PI, "--list-models"], capture_output=True, text=True, timeout=PI_TIMEOUT_S
        )
    except subprocess.TimeoutExpired as exc:
        raise LlmError(f"pi --list-models did not answer within {PI_TIMEOUT_S}s") from exc
    if proc.returncode != 0:
        raise LlmError(f"pi --list-models exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return parse_models(proc.stdout)


def parse_models(table: str) -> list[str]:
    """Pull `provider/model` out of the columns pi prints."""
    models = []
    for line in table.splitlines():
        cells = line.split()
        if len(cells) >= 2 and cells[0] != "provider":
            models.append(f"{cells[0]}/{cells[1]}")
    return models
