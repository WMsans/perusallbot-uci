import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    required: int
    remaining: int


_REQUIREMENT = re.compile(
    r"Post at least (\d+) comments?, questions?, or responses?\s*\((\d+) remaining\)",
    re.IGNORECASE,
)


def parse_requirement(progress_text: str) -> Requirement | None:
    m = _REQUIREMENT.search(progress_text)
    if not m:
        return None
    return Requirement(int(m.group(1)), int(m.group(2)))


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def _fit(text: str, max_chars: int) -> str:
    """Trim to the last word boundary that fits."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut


def choose_excerpt(
    spans: list[str],
    used: set[str],
    min_chars: int = 40,
    max_chars: int = 400,
) -> str | None:
    """First unused run of 1-2 sentences from the page text.

    Windows stride by two sentences so a consumed excerpt cannot reappear as a
    shifted duplicate of itself.
    """
    body = " ".join(s.strip() for s in spans if len(s.strip()) >= min_chars)
    sentences = [s for s in _SENTENCE_BREAK.split(body) if s.strip()]
    for start in range(0, len(sentences), 2):
        candidate = _fit(" ".join(sentences[start : start + 2]), max_chars).strip()
        if len(candidate) < min_chars or candidate in used:
            continue
        return candidate
    return None
