"""Scope tests for the sanitization gate's blind spots.

Two coverage gaps, each demonstrated by a live finding at the commit this
change was written against:

* ``.github`` was pruned from the fail-closed walk on the stated premise that
  CI configuration "could not carry a leak". A workflow comment naming a
  private repository by slug and describing its contents disproved it, and the
  gate reported green because nothing scanned the directory.
* the internal-host pattern required a literal dot before the octet, so the
  hyphenated host-alias form passed. A live runbook shipped an internal lab
  SSH alias and an on-host state path on that basis.

Every test named ``previously_unscanned`` or ``previously_passed`` is a
positive control: it fails against the gate as it stood before this change.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate  # noqa: E402
from sanitization_patterns import scan_text  # noqa: E402


# ---------------------------------------------------------------------------
# .github is inside the walk
# ---------------------------------------------------------------------------


def test_github_is_no_longer_pruned_from_the_walk() -> None:
    """Previously unscanned: the directory was in the excluded set."""
    assert ".github" not in validate.EXCLUDED_WALK_DIRS


def test_github_is_a_registered_sanitization_scanned_location() -> None:
    """Unpruning without registering would only convert a silent skip into a
    fail-closed 'unregistered location' error on every workflow file."""
    assert ".github" in validate.PLATFORM_SANITIZED_DIRS
    path = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert validate._is_registered_location(path, _REPO_ROOT)


def test_workflow_files_are_in_the_sanitization_target_set() -> None:
    """A workflow is a `.yml`; a markdown-only target set would still miss it.
    Extension-scoped scanning is the other half of this failure mode."""
    targets = {
        p.relative_to(_REPO_ROOT).as_posix()
        for p in validate._find_sanitization_targets(_REPO_ROOT)
    }
    assert any(t.startswith(".github/workflows/") and t.endswith(".yml") for t in targets)


def test_private_repo_named_without_a_url_is_caught() -> None:
    """The live finding's shape. Previously passed twice over: the directory
    was unscanned, and the private-repo pattern only ever matched a URL."""
    text = "# the same checker is vendored in knowledge-base-internal\n"
    errors = scan_text(text, label="probe")
    assert errors, "a bare private sibling slug must be a finding"
    assert "Private repo name" in errors[0]


def test_public_slug_alone_is_still_exempt() -> None:
    assert scan_text("OmniNode-ai/knowledge-base is public\n", label="probe") == []


# ---------------------------------------------------------------------------
# The hyphenated host-alias form
# ---------------------------------------------------------------------------


def test_hyphenated_host_alias_is_caught() -> None:
    """Previously passed: the pattern required a literal dot."""
    errors = scan_text("ssh omni-201-ts 'cat file'\n", label="probe")
    assert errors, "the hyphenated alias form must be a finding"
    assert "Internal host reference" in errors[0]


def test_dotted_host_form_is_still_caught() -> None:
    errors = scan_text("the box at host.201 is up\n", label="probe")
    assert errors
    assert "Internal host reference" in errors[0]


def test_numeric_argument_is_not_a_host_alias() -> None:
    """`tail -200` occurs in this repo's own prose. A pattern that flags it
    trains contributors to sprinkle allowlist markers, which is how a
    detector becomes decoration."""
    assert scan_text('tail -200 "$LOG"\n', label="probe") == []


def test_numeric_range_is_not_a_host_alias() -> None:
    assert scan_text("Length: 1-200 characters\n", label="probe") == []


# ---------------------------------------------------------------------------
# The live tree
# ---------------------------------------------------------------------------


def test_repository_is_clean_under_the_widened_gate() -> None:
    """Both live findings are fixed rather than allowlisted."""
    errors = validate.check_sanitization(_REPO_ROOT)
    errors += validate.check_registered_locations(_REPO_ROOT)
    assert errors == [], "\n".join(errors)
