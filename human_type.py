"""Per-character typing with human-ish timing, driven through the browser."""

import random
import time

# ~0.12 s/char: a brisk but human pace, and never instant-looking.
BASE_DELAY = 0.12
JITTER = 0.6


def char_delays(text: str, rng: random.Random) -> list[float]:
    delays = []
    for ch in text:
        delay = BASE_DELAY * rng.uniform(1 - JITTER, 1 + JITTER)
        if ch in ".?!":
            delay += rng.uniform(0.25, 0.7)
        elif ch == ",":
            delay += rng.uniform(0.12, 0.35)
        delays.append(delay)
    return delays


def type_like_human(page, text: str, rng: random.Random) -> None:
    for ch, delay in zip(text, char_delays(text, rng)):
        page.keyboard.type(ch)
        time.sleep(delay)
