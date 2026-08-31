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

# The only repositories under the ``OmniNode-ai`` org that are public. A URL
# naming any other slug is a private-repo leak. This is an explicit allowlist,
# not a prefix rule: every entry must be an exact repository name.
#
# The public repository's own name is an open question in the workspace plan
# (Q1) — an underscore spelling is among the candidates. Renaming the repo
# means adding the new slug here DELIBERATELY; ``tests/test_sanitization_patterns.py``
# pins the current verdict for the underscore spellings so a rename cannot
# silently change what this gate exempts.
PUBLIC_REPO_SLUGS: tuple[str, ...] = ("knowledge-base",)

# A GitHub repository name may contain letters, digits, ``.``, ``_`` and ``-``.
# Requiring the character following an exempt slug to be OUTSIDE that set is
# what turns "starts with" into "is exactly", so a private sibling such as
# ``<public-slug>-internal`` can no longer inherit the public exemption.
# ``.git`` may trail the slug so a legitimate clone URL still passes.
_SLUG_BOUNDARY = r"(?:\.git)?(?![A-Za-z0-9._-])"

_PUBLIC_REPO_EXEMPTION = "|".join(re.escape(slug) + _SLUG_BOUNDARY for slug in PUBLIC_REPO_SLUGS)

SANITIZATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"OMN-\d+"), "Internal ticket reference"),
    (re.compile(r"192\.168\.\d+\.\d+"), "Internal IP address"),
    (re.compile(r"\.(200|201)\b"), "Internal host reference"),
    (re.compile(rf"github\.com/OmniNode-ai/(?!{_PUBLIC_REPO_EXEMPTION})"), "Private repo URL"),
    (re.compile(r"infisical", re.IGNORECASE), "Internal secrets manager reference"),
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
