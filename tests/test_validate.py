"""Tests for scripts/validate.py — fail-closed recursive scanning.

Fixtures build a synthetic repo skeleton under ``tmp_path`` rather than relying
on the live knowledge-base tree, so these tests stay independent of unrelated
content drift in adrs/, deep-dives/, etc.

Several tests here are the RED-before/GREEN-after proof for the coverage gap:
run against the pre-fix ``validate.py``, ``test_nested_leak_is_caught_by_*``
fail because the old code silently skips anything outside the closed 8-entry
``ARTIFACT_DIRS`` top-level glob — including the sanitization guard. They pass
once discovery is recursive, the three consumer classes are registered, and
root/YAML content is in scope.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import get_args

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate  # noqa: E402  (path setup must precede import)

ADR_FRONTMATTER = """---
type: adr
status: proposed
date: "2026-08-19"
title: "Test ADR"
adr_id: ADR-9001
---

Body.
"""

GUIDE_FRONTMATTER = """---
type: guide
status: current
date: "2026-08-19"
title: "Test Guide"
---

Body.
"""

REFERENCE_FRONTMATTER = """---
type: reference
status: current
date: "2026-08-19"
title: "Test Reference"
---

Body.
"""

RUNBOOK_FRONTMATTER = """---
type: runbook
status: current
date: "2026-08-19"
title: "Test Runbook"
---

Body.
"""


def _write(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repo skeleton: root charter docs + empty artifact dirs."""
    _write(tmp_path, "README.md", "# KB\n")
    _write(tmp_path, "CONTRIBUTING.md", "# Contributing\n")
    _write(tmp_path, "CLAUDE.md", "# CLAUDE\n")
    _write(tmp_path, "docs-taxonomy.md", "# Taxonomy\n")
    _write(tmp_path, "migration-manifest.yaml", "schema_version: 1\n")
    for d in validate.ARTIFACT_DIRS:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "indexes").mkdir(exist_ok=True)
    return tmp_path


class TestNewArtifactClasses:
    def test_guide_frontmatter_valid(self, repo: Path) -> None:
        _write(repo, "guides/test-guide.md", GUIDE_FRONTMATTER)
        assert validate.check_all_frontmatter(repo) == []

    def test_reference_frontmatter_valid(self, repo: Path) -> None:
        _write(repo, "reference/test-ref.md", REFERENCE_FRONTMATTER)
        assert validate.check_all_frontmatter(repo) == []

    def test_runbook_frontmatter_valid(self, repo: Path) -> None:
        _write(repo, "runbooks/test-runbook.md", RUNBOOK_FRONTMATTER)
        assert validate.check_all_frontmatter(repo) == []

    def test_guide_rejects_unknown_status(self, repo: Path) -> None:
        bad = GUIDE_FRONTMATTER.replace("status: current", "status: not-a-status")
        _write(repo, "guides/bad-guide.md", bad)
        errors = validate.check_all_frontmatter(repo)
        assert errors, "an invalid status must be rejected, not silently accepted"

    def test_guide_rejects_unknown_type_via_valid_types_gate(self, repo: Path) -> None:
        bad = GUIDE_FRONTMATTER.replace("type: guide", "type: not-a-type")
        _write(repo, "guides/bad-type.md", bad)
        errors = validate.check_all_frontmatter(repo)
        assert errors and "unknown type" in errors[0]

    def test_valid_types_derived_from_single_source(self) -> None:
        # Regression guard against the exact duplication AC1 calls out: the
        # `valid_types` set used by validate_frontmatter must be derived from
        # BaseFrontmatter.type, never a second hand-maintained literal.
        base_types = set(get_args(validate.BaseFrontmatter.model_fields["type"].annotation))
        assert {"guide", "reference", "runbook"} <= base_types
        assert base_types == validate._valid_frontmatter_types()


class TestRecursiveDiscovery:
    def test_nested_adr_is_discovered(self, repo: Path) -> None:
        _write(repo, "adrs/nested/ADR-9001-nested.md", ADR_FRONTMATTER)
        files = validate._find_artifact_files(repo)
        assert any(f.name == "ADR-9001-nested.md" for f in files)

    def test_deeply_nested_file_passes_frontmatter_check(self, repo: Path) -> None:
        deep = ADR_FRONTMATTER.replace("ADR-9001", "ADR-9002")
        _write(repo, "adrs/nested/deep/ADR-9002-deep.md", deep)
        # A valid nested file must produce zero errors, proving it was seen
        # (and validated) at all rather than skipped entirely.
        assert validate.check_all_frontmatter(repo) == []

    def test_nested_readme_and_template_still_excluded_from_frontmatter(self, repo: Path) -> None:
        _write(repo, "adrs/nested/README.md", "# nested section\n")
        _write(repo, "adrs/nested/_template.md", "---\n---\n")
        assert validate.check_all_frontmatter(repo) == []


class TestPreviouslySkippedNestedLeakIsNowCaught:
    """RED-before/GREEN-after: a forbidden pattern in a nested guides/ path."""

    def test_nested_leak_is_caught_by_sanitization(self, repo: Path) -> None:
        leaking = GUIDE_FRONTMATTER + "\nInternal host reachable at 192.168.86.201 for debugging.\n"
        _write(repo, "guides/getting-started/install.md", leaking)
        errors = validate.check_sanitization(repo)
        assert any("install.md" in e for e in errors), (
            "a forbidden IP planted in a nested guides/ path must be caught by "
            "the sanitization guard, not silently skipped"
        )

    def test_nested_file_is_enumerated_as_a_known_location(self, repo: Path) -> None:
        _write(repo, "guides/getting-started/install.md", GUIDE_FRONTMATTER)
        files = validate._find_artifact_files(repo)
        assert any(f.name == "install.md" for f in files)


class TestRootAndYamlSanitization:
    def test_root_markdown_forbidden_pattern_caught(self, repo: Path) -> None:
        _write(repo, "README.md", "# KB\n\nContact us at admin@internal-example.com for access.\n")
        errors = validate.check_sanitization(repo)
        assert any("README.md" in e for e in errors)

    def test_root_yaml_forbidden_pattern_caught(self, repo: Path) -> None:
        _write(
            repo,
            "migration-manifest.yaml",
            "schema_version: 1\nsource_path: /Users/example/internal-repo\nnote: internal ticket OMN-9999\n",
        )
        errors = validate.check_sanitization(repo)
        assert any("migration-manifest.yaml" in e for e in errors)

    def test_charter_files_are_scanned(self, repo: Path) -> None:
        _write(repo, "CLAUDE.md", "# CLAUDE\n\nSee 192.168.86.55 for the dev box.\n")
        errors = validate.check_sanitization(repo)
        assert any("CLAUDE.md" in e for e in errors)

    def test_section_readme_is_scanned_even_though_frontmatter_exempt(self, repo: Path) -> None:
        _write(repo, "adrs/README.md", "# ADRs\n\nInternal ticket OMN-1234 tracked this.\n")
        errors = validate.check_sanitization(repo)
        assert any("adrs/README.md" in e for e in errors)


class TestUnregisteredLocationFailsClosed:
    def test_unknown_top_level_directory_is_an_error(self, repo: Path) -> None:
        _write(repo, "scratch/notes.md", "# notes\n")
        errors = validate.check_registered_locations(repo)
        assert any("scratch" in e for e in errors)

    def test_unknown_root_markdown_file_is_an_error(self, repo: Path) -> None:
        _write(repo, "NOTES.md", "# notes\n")
        errors = validate.check_registered_locations(repo)
        assert any("NOTES.md" in e for e in errors)

    def test_unknown_root_yaml_file_is_an_error(self, repo: Path) -> None:
        _write(repo, "scratch.yaml", "a: 1\n")
        errors = validate.check_registered_locations(repo)
        assert any("scratch.yaml" in e for e in errors)

    def test_known_locations_produce_no_errors(self, repo: Path) -> None:
        _write(repo, "guides/test-guide.md", GUIDE_FRONTMATTER)
        _write(repo, "indexes/chronological.md", "# Chronological\n")
        assert validate.check_registered_locations(repo) == []

    def test_dot_git_and_dot_github_are_pruned_from_the_walk(self, repo: Path) -> None:
        _write(repo, ".git/some-internal-file.md", "internal\n")
        _write(repo, ".github/ISSUE_TEMPLATE/bug.md", "template\n")
        assert validate.check_registered_locations(repo) == []


class TestGenerateIndexesRecursiveAndNewClasses:
    def test_collect_artifacts_recursive(self, repo: Path) -> None:
        import generate_indexes

        nested = ADR_FRONTMATTER.replace("ADR-9001", "ADR-9003")
        _write(repo, "adrs/nested/ADR-9003-nested.md", nested)
        artifacts = generate_indexes.collect_artifacts(repo)
        assert any(a.get("adr_id") == "ADR-9003" for a in artifacts)

    def test_collect_artifacts_includes_new_classes(self, repo: Path) -> None:
        import generate_indexes

        _write(repo, "guides/test-guide.md", GUIDE_FRONTMATTER)
        artifacts = generate_indexes.collect_artifacts(repo)
        assert any(a.get("type") == "guide" for a in artifacts)
