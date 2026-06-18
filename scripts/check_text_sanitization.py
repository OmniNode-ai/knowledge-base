"""Forward-blocking sanitization gate for commit messages and PR text.

This public repo's artifact files are already scanned by ``scripts/validate.py``.
Commit messages and pull-request title/body are NOT part of any artifact file,
yet they are equally public once pushed. This gate closes that gap.

It reuses the single source of forbidden patterns — ``SANITIZATION_PATTERNS``
in ``scripts/validate.py`` — via the shared ``scan_text`` helper, so the list of
forbidden patterns is never duplicated.

Modes
-----
``--commit-msg-file PATH``
    Scan a commit-message file (the pre-commit ``commit-msg`` stage passes the
    path to ``.git/COMMIT_EDITMSG``). Comment lines (starting with ``#``) are
    stripped before scanning so the git status template never trips the gate.

``--pr-title TEXT`` / ``--pr-body TEXT``
    Scan a pull-request title and/or body (CI passes
    ``github.event.pull_request.title`` / ``.body``).

``--commit-range RANGE``
    Scan every commit MESSAGE in ``RANGE`` (e.g. ``origin/main..HEAD``). Only
    the PR's own commits are scanned — never the full history of ``main``.

Exit code is non-zero if any forbidden pattern is found; the offending pattern
and its description are printed so the author knows exactly what to remove.
The author allowlist marker (``# sanitization-ok:``) is intentionally NOT
honored here — text gates must not let an author self-exempt leaked content.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Make the sibling sanitization module importable regardless of CWD. We import
# from sanitization_patterns (stdlib-only) rather than validate, so this gate
# runs under pre-commit's interpreter without needing pyyaml / pydantic.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sanitization_patterns import scan_text  # noqa: E402  (path setup must precede import)


def _strip_comment_lines(text: str) -> str:
    """Drop git comment lines (``#`` prefixed) from a commit message."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _commit_messages_in_range(commit_range: str) -> list[tuple[str, str]]:
    """Return [(sha, message), ...] for every commit in ``commit_range``."""
    shas = subprocess.run(
        ["git", "rev-list", commit_range],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    result: list[tuple[str, str]] = []
    for sha in shas:
        message = subprocess.run(
            ["git", "log", "-1", "--format=%B", sha],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        result.append((sha, message))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit-msg-file", metavar="PATH", help="Path to a commit-message file to scan")
    parser.add_argument("--pr-title", metavar="TEXT", help="Pull-request title to scan")
    parser.add_argument("--pr-body", metavar="TEXT", help="Pull-request body to scan")
    parser.add_argument(
        "--commit-range",
        metavar="RANGE",
        help="Scan every commit MESSAGE in RANGE (e.g. origin/main..HEAD)",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []

    if args.commit_msg_file:
        raw = Path(args.commit_msg_file).read_text(encoding="utf-8")
        errors.extend(scan_text(_strip_comment_lines(raw), label="commit message", honor_allowlist=False))

    if args.pr_title:
        errors.extend(scan_text(args.pr_title, label="PR title", honor_allowlist=False))

    if args.pr_body:
        errors.extend(scan_text(args.pr_body, label="PR body", honor_allowlist=False))

    if args.commit_range:
        for sha, message in _commit_messages_in_range(args.commit_range):
            errors.extend(scan_text(message, label=f"commit {sha[:12]}", honor_allowlist=False))

    if errors:
        print("Sanitization gate FAILED — forbidden private content found:", file=sys.stderr)
        for err in errors:
            print(f"  x {err}", file=sys.stderr)
        print(
            "\nThis repo is PUBLIC. Remove internal ticket refs, internal IPs/hosts, "
            "private repo URLs, secrets-manager references, and emails from the text above.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
