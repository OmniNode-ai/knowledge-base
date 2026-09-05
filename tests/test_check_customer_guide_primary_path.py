"""Fixture tests for scripts/check_customer_guide_primary_path.py.

The checker asserts that each guarded customer guide's PRIMARY PATH -- the
text above the ``<!-- primary-path-ends -->`` appendix marker -- mentions
``onex cloud`` and contains no ``curl`` invocation. The raw-HTTP reference is
allowed, and expected, below the marker.

Both directions are proven on synthetic fixtures under ``tmp_path``: a guide
that leads with the client is clean, and the same guide with a curl above the
marker is caught. A checker that returned no violations unconditionally would
fail the second, so the clean run against this repo's real guide (the last
test) is evidence rather than silence.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_customer_guide_primary_path as checker  # noqa: E402  (path setup must precede import)

GUIDE = "guides/connecting-to-the-cloud.md"
MARKER = checker.APPENDIX_MARKER

CLIENT_FIRST_PRIMARY = f"""# Connecting to the Cloud

```bash
uv tool install --python 3.12 --upgrade --with omnimarket omnibase-core
onex cloud login --base-url https://api.omninode.ai --api-key-stdin
onex cloud delegate "summarize this" --task-type summarization
```

{MARKER}

## Appendix -- the raw HTTP

```bash
curl -sS "https://api.omninode.ai/v1/whoami" -H "x-api-key: $ONEX_API_KEY"
```
"""

CURL_FIRST_PRIMARY = """# Connecting to the Cloud

```bash
curl -sS -X POST "https://api.omninode.ai/v1/workflows" -H "x-api-key: $ONEX_API_KEY"
```
"""


def test_client_first_guide_passes() -> None:
    """Positive control, pass direction."""
    assert checker.check_text(GUIDE, CLIENT_FIRST_PRIMARY) == []


def test_curl_in_primary_path_is_flagged() -> None:
    """Positive control, fail direction: an always-empty checker fails here."""
    violations = checker.check_text(GUIDE, CURL_FIRST_PRIMARY)
    assert {v.rule for v in violations} >= {"curl-in-primary-path"}


def test_guide_without_onex_cloud_is_flagged() -> None:
    violations = checker.check_text(GUIDE, "# Connecting\n\nSign in and copy your key.\n")
    assert [v.rule for v in violations] == ["missing-onex-cloud"]
    assert violations[0].line_number == 0


def test_curl_below_the_marker_is_allowed() -> None:
    text = f"Run `onex cloud delegate`.\n\n{MARKER}\n\ncurl -sS https://example.invalid\n"
    assert checker.check_text(GUIDE, text) == []


def test_missing_marker_checks_the_whole_file() -> None:
    """Forgetting the marker fails closed rather than exempting the file."""
    text = "Run `onex cloud delegate`.\n\ncurl -sS https://example.invalid\n"
    assert [v.rule for v in checker.check_text(GUIDE, text)] == ["curl-in-primary-path"]


def test_curl_violation_reports_its_line_number() -> None:
    text = f"line one\nRun `onex cloud`.\ncurl -sS https://example.invalid\n{MARKER}\n"
    violations = checker.check_text(GUIDE, text)
    assert len(violations) == 1
    assert violations[0].line_number == 3


def test_curl_substring_in_an_identifier_is_not_a_violation() -> None:
    text = f"Run `onex cloud delegate`.\nThe binding is curl_easy_setopt.\n{MARKER}\n"
    assert checker.check_text(GUIDE, text) == []


def test_scans_the_guarded_guide(tmp_path: Path) -> None:
    guide = tmp_path / GUIDE
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_text(CURL_FIRST_PRIMARY)
    violations = checker.find_violations(tmp_path, (GUIDE,))
    assert any(v.rule == "curl-in-primary-path" for v in violations)


def test_absent_guarded_guide_is_skipped_not_flagged(tmp_path: Path) -> None:
    """The checker is vendored into two repos guarding different files."""
    assert checker.find_violations(tmp_path, (GUIDE,)) == []


def test_unguarded_guide_is_not_scanned(tmp_path: Path) -> None:
    other = tmp_path / "guides/getting-started-local.md"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(CURL_FIRST_PRIMARY)
    assert checker.find_violations(tmp_path, (GUIDE,)) == []


def test_guarded_set_is_not_empty() -> None:
    """A checker guarding nothing passes vacuously."""
    assert checker.GUARDED_GUIDES


def test_repo_guide_leads_with_the_client() -> None:
    """The gate, applied to this repo's own checked-in guide."""
    root = Path(__file__).resolve().parent.parent
    violations = checker.find_violations(root, checker.GUARDED_GUIDES)
    assert violations == [], "\n".join(f"{v.file}:{v.line_number} [{v.rule}] {v.line}" for v in violations)
