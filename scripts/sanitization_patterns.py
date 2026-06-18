"""Single source of forbidden private-content patterns for the public repo.

This module is intentionally dependency-free (stdlib ``re`` only) so it can be
imported by lightweight tooling — notably the commit-message / PR-text gate in
``check_text_sanitization.py``, which runs under pre-commit's own interpreter
without the project's ``pyyaml`` / ``pydantic`` dependencies.

``validate.py`` re-exports these names, so the artifact-file sanitization guard
and the commit-message / PR-text gate share exactly one list of patterns.
"""

from __future__ import annotations

import re

SANITIZATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"OMN-\d+"), "Internal ticket reference"),
    (re.compile(r"192\.168\.\d+\.\d+"), "Internal IP address"),
    (re.compile(r"\.(200|201)\b"), "Internal host reference"),
    (re.compile(r"github\.com/OmniNode-ai/(?!knowledge-base)"), "Private repo URL"),
    (re.compile(r"infisical|INFISICAL"), "Internal secrets manager reference"),
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "Email address pattern"),
]

_ALLOWLIST_PATTERN = re.compile(r"#\s*sanitization-ok:\s*(.+)")


def scan_text(text: str, *, label: str = "text", honor_allowlist: bool = True) -> list[str]:
    """Scan arbitrary text for private content patterns.

    Shared single source of forbidden-pattern detection. Used both by the
    artifact-file sanitization guard (``validate.py``) and by the
    commit-message / PR-text gate (``check_text_sanitization.py``).

    Returns a list of error strings, one per offending line, prefixed with
    ``label`` and the 1-indexed line number. ``honor_allowlist`` allows a line
    carrying a ``# sanitization-ok:`` marker to suppress its own findings; the
    commit-message / PR-text gate disables it so authors cannot self-exempt
    leaked content.
    """
    errors: list[str] = []
    lines = text.splitlines()

    allowlisted_lines: set[int] = set()
    if honor_allowlist:
        for i, line in enumerate(lines, 1):
            if _ALLOWLIST_PATTERN.search(line):
                allowlisted_lines.add(i)

    for i, line in enumerate(lines, 1):
        if i in allowlisted_lines:
            continue
        for pattern, description in SANITIZATION_PATTERNS:
            if pattern.search(line):
                errors.append(f"{label}:{i}: {description} — matches '{pattern.pattern}'")
                break  # one error per line
    return errors
