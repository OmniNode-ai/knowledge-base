#!/usr/bin/env python3
"""Assert the customer guides lead with the shipped client, not hand-written HTTP.

`onex cloud` is the customer delegation path (the 2026-08-29 operator ruling,
made mechanical by omnimarket's `onex.cli` entry point). A customer-facing
guide whose *primary path* walks the reader through assembling the HTTP by
hand is documenting a path we do not want them on: they hand-roll the token
exchange, the poll loop, and the `runner_identity` query parameter whose
omission is a 422.

The rule this enforces, per guarded guide:

  1. the primary-path section MUST mention ``onex cloud``
  2. the primary-path section MUST contain zero ``curl`` invocations

The **primary path** is everything from the top of the file down to the
appendix marker::

    <!-- primary-path-ends -->

Text after that marker is the appendix: the raw-HTTP reference, kept
deliberately for readers building their own client and for the steps that
have no client command. Placing the marker is how a guide declares where its
first-class instructions stop; a guarded guide with no marker is checked in
full, which is the strict reading and the correct default.

Guarded files are listed in ``GUARDED_GUIDES`` — this is an allowlist of the
guides a new customer lands on first, not a whole-tree scan. Widening it is a
decision to hold another guide to the client-first standard.

Exit code is 0 with no violations, 1 otherwise. Runs as both a pre-commit
hook (staged files) and a CI job (full guarded-set scan).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# The guides a new customer reads first. Paths are repo-root-relative POSIX.
GUARDED_GUIDES: tuple[str, ...] = ("guides/connecting-to-the-cloud.md",)

APPENDIX_MARKER = "<!-- primary-path-ends -->"

REQUIRED_TOKEN = "onex cloud"

# `curl` as a command, not as prose ("a curl-based client"). Word-bounded so
# `curl_easy_setopt` or `incurl` never trip it, and so the noun in a sentence
# is only matched when it stands alone -- which is the conservative direction:
# a guide that merely names curl in prose still has to move that prose into
# the appendix or reword it.
CURL_PATTERN = re.compile(r"\bcurl\b")


@dataclass(frozen=True)
class Violation:
    file: str
    line_number: int
    rule: str
    line: str


def split_primary_path(text: str) -> str:
    """Return the primary-path portion of a guide's text.

    Everything before ``APPENDIX_MARKER``. A guide with no marker is entirely
    primary path -- the strict reading, so forgetting the marker fails closed
    rather than exempting the file.
    """
    head, marker, _tail = text.partition(APPENDIX_MARKER)
    return head if marker else text


def check_text(relpath: str, text: str) -> list[Violation]:
    """Apply both rules to one guide's text."""
    violations: list[Violation] = []
    primary = split_primary_path(text)

    for line_number, line in enumerate(primary.splitlines(), start=1):
        if CURL_PATTERN.search(line):
            violations.append(
                Violation(
                    file=relpath,
                    line_number=line_number,
                    rule="curl-in-primary-path",
                    line=line.strip(),
                )
            )

    if REQUIRED_TOKEN not in primary:
        violations.append(
            Violation(
                file=relpath,
                line_number=0,
                rule="missing-onex-cloud",
                line=(
                    f"the primary path never mentions '{REQUIRED_TOKEN}' "
                    "-- the customer client is not the first-class instruction"
                ),
            )
        )

    return violations


def find_violations(root: Path, guarded_guides: tuple[str, ...] = GUARDED_GUIDES) -> list[Violation]:
    """Scan every guarded guide present under ``root``.

    A guarded guide that does not exist is skipped rather than reported: this
    checker is vendored into two repos that guard different files, and a
    missing file is that repo's normal state, not a violation.
    """
    violations: list[Violation] = []
    for relpath in guarded_guides:
        path = root / relpath
        if not path.is_file():
            continue
        violations.extend(check_text(relpath, path.read_text(errors="replace")))
    return violations


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path.cwd()

    if argv:
        # pre-commit mode: check only the passed files that are guarded.
        violations: list[Violation] = []
        for raw in argv:
            path = Path(raw)
            rel = _relative_to_root(path, root)
            if rel not in GUARDED_GUIDES:
                continue
            if not path.is_file():
                continue
            violations.extend(check_text(rel, path.read_text(errors="replace")))
    else:
        # CI mode: scan every guarded guide in the tree.
        violations = find_violations(root, GUARDED_GUIDES)

    if violations:
        print(
            "customer-guide-primary-path: the customer guides must lead with the shipped client:\n",
            file=sys.stderr,
        )
        for v in violations:
            where = f"{v.file}:{v.line_number}" if v.line_number else v.file
            print(f"  {where}: [{v.rule}] {v.line}", file=sys.stderr)
        print(
            f"\nMove hand-written HTTP below the '{APPENDIX_MARKER}' marker and "
            f"make '{REQUIRED_TOKEN}' the first-class instruction.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
