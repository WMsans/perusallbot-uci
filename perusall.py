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
