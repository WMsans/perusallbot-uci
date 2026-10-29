"""Finish a Perusall reading assignment: insight -> humanize -> type it in."""

import argparse
import random
import subprocess
import sys
import time

from patchright.sync_api import sync_playwright

import humanizer
import perusall
from humanizer import HumanizerBlocked
from llm import LlmError, list_models, write_insight
from perusall import (
    AssignmentNotFound,
    choose_excerpt,
    doc_title,
    document_spans,
    open_first_assignment,
    post_comment,
    read_requirement,
    reload_reader,
)

MAX_SECONDS = 20 * 60


def humanize(text: str, page, which: str, model: str | None) -> str:
    if which == "llm":
        out = humanizer.humanize_with_llm(text, model)
    else:
        out = humanizer.humanize_with_web(page, text)
    # Post the original if the rewrite lost a fifth of the words: the comment is
    # meant to be long, and a trimmed rewrite undoes that.
    return out if len(out.split()) >= 0.8 * len(text.split()) else text


def pick_model() -> str | None:
    """fzf over pi's model list. Esc, missing fzf, or an error: pi's default."""
    try:
        models = list_models()
    except LlmError as exc:
        print(f"Could not list models ({exc}); using pi's default.")
        return None
    try:
        proc = subprocess.run(
            ["fzf", "--height=40%", "--reverse", "--prompt=model> "],
            input="\n".join(models) + "\n",
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("fzf is not installed; using pi's default model.")
        return None
    return proc.stdout.strip() or None


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="pi model, e.g. deepseek/deepseek-flash (default: pick with fzf)")
    ap.add_argument("--assignment", help="only pick assignments whose name matches")
    ap.add_argument("--count", type=int, help="post at most this many comments")
    ap.add_argument("--humanizer", choices=sorted(humanizer.HUMANIZERS), default="web")
    return ap.parse_args(argv)


def run(page, hpage, args, rng) -> int:
    requirement = read_requirement(page)
    if requirement is None:
        print("This assignment's requirement is not a comment count. Nothing posted.")
        return 1

    print(f"Assignment wants {requirement.required} comments "
          f"({requirement.remaining} remaining).")

    limit = args.count if args.count is not None else requirement.remaining
    total = max(1, min(limit, requirement.remaining))
    spans = document_spans(page)
    used: set[str] = set()
    posted = 0
    remaining = requirement.remaining
    rounds = 0
    deadline = time.monotonic() + MAX_SECONDS

    while remaining > 0 and posted < limit:
        if rounds > requirement.required:
            print("Gave up: posted more rounds than the assignment asks for.")
            return 1
        if time.monotonic() > deadline:
            print("Gave up: ran past the time limit.")
            return 1
        rounds += 1

        # Each comment takes the middle of its own 1/total share of the reading,
        # so the run spreads over the whole document instead of stacking on page one.
        target = (posted + 0.5) / total
        excerpt = choose_excerpt(spans, used, target=target)
        if excerpt is None:
            print("Gave up: no unused passages left in the reading.")
            return 1

        try:
            reply = write_insight(excerpt, doc_title(page), args.model)
            text = humanize(reply, hpage, args.humanizer, args.model)
            post_comment(page, excerpt, text, rng, target)
        except LlmError as exc:
            print(f"Stopped before posting: {exc}")
            return 1
        except HumanizerBlocked as exc:
            print(f"Stopped after {posted} comment(s): {exc}")
            return 1
        except Exception as exc:  # a browser surprise must still stop cleanly
            print(f"Stopped after {posted} comment(s): {type(exc).__name__}: {exc}")
            return 1

        used.add(excerpt)
        posted += 1
        print(f"Posted {posted}: {text[:70]}...")

        after = read_requirement(page)
        new_remaining = after.remaining if after else remaining
        if new_remaining >= remaining:
            reload_reader(page)
            after = read_requirement(page)
            new_remaining = after.remaining if after else remaining
            if new_remaining >= remaining:
                print(f"Stopped: the count stayed at {remaining} after a reload.")
                return 1
        remaining = new_remaining

    print(f"Done. Posted {posted} comment(s); {remaining} still required.")
    return 0 if remaining == 0 or posted >= limit else 1


def main() -> int:
    args = parse_args(sys.argv[1:])
    if not args.model:
        args.model = pick_model()
    print(f"Comment model: {args.model or 'pi default'}")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=".browser-profile",
            headless=False,
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(perusall.ASSIGNMENTS_URL)
        input("Log in to Perusall in the browser window, then press Enter here: ")

        hpage = ctx.new_page()
        hpage.goto(humanizer.URL)
        page.bring_to_front()

        try:
            open_first_assignment(page, args.assignment)
        except AssignmentNotFound as exc:
            print(f"Nothing to do: {exc}")
            return 1
        return run(page, hpage, args, random.Random())


if __name__ == "__main__":
    sys.exit(main())
