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


class TestAdrIdUniqueness:
    """RED-before/GREEN-after for the adr_id collision check.

    ``ADRFrontmatter.adr_id`` is a bare ``str`` — nothing rejects two ADRs
    claiming the same value; each validates individually. These tests prove
    the new ``check_adr_id_uniqueness`` catches that class of defect, and
    that the narrow, exact-path-set exemption for the one already-known,
    owner-sign-off-pending collision does not silently widen to cover any
    other collision (new file, third path, different id).
    """

    def test_two_distinct_adr_ids_pass(self, repo: Path) -> None:
        _write(repo, "adrs/ADR-9001-first.md", ADR_FRONTMATTER)
        second = ADR_FRONTMATTER.replace("ADR-9001", "ADR-9002").replace("Test ADR", "Second Test ADR")
        _write(repo, "adrs/ADR-9002-second.md", second)
        assert validate.check_adr_id_uniqueness(repo) == []

    def test_two_files_sharing_an_adr_id_is_rejected(self, repo: Path) -> None:
        _write(repo, "adrs/ADR-9001-first.md", ADR_FRONTMATTER)
        dup = ADR_FRONTMATTER.replace("Test ADR", "Duplicate Test ADR")
        _write(repo, "adrs/ADR-9001-second.md", dup)
        errors = validate.check_adr_id_uniqueness(repo)
        assert len(errors) == 1
        assert "ADR-9001" in errors[0]
        assert "ADR-9001-first.md" in errors[0]
        assert "ADR-9001-second.md" in errors[0]

    def test_three_files_sharing_an_adr_id_names_all_three(self, repo: Path) -> None:
        _write(repo, "adrs/ADR-9001-a.md", ADR_FRONTMATTER)
        _write(repo, "adrs/ADR-9001-b.md", ADR_FRONTMATTER.replace("Test ADR", "B"))
        _write(repo, "adrs/ADR-9001-c.md", ADR_FRONTMATTER.replace("Test ADR", "C"))
        errors = validate.check_adr_id_uniqueness(repo)
        assert len(errors) == 1
        assert all(name in errors[0] for name in ("ADR-9001-a.md", "ADR-9001-b.md", "ADR-9001-c.md"))

    def test_non_adr_frontmatter_types_are_ignored(self, repo: Path) -> None:
        _write(repo, "guides/test-guide.md", GUIDE_FRONTMATTER)
        assert validate.check_adr_id_uniqueness(repo) == []

    def test_known_collision_exact_path_set_is_exempted(self, repo: Path) -> None:
        a = ADR_FRONTMATTER.replace("ADR-9001", "ADR-KNOWN")
        b = ADR_FRONTMATTER.replace("ADR-9001", "ADR-KNOWN").replace("Test ADR", "B")
        _write(repo, "adrs/known-a.md", a)
        _write(repo, "adrs/known-b.md", b)
        known = {"ADR-KNOWN": frozenset({"adrs/known-a.md", "adrs/known-b.md"})}
        assert validate.check_adr_id_uniqueness(repo, known_collisions=known) == []

    def test_known_collision_exemption_does_not_cover_a_third_file(self, repo: Path) -> None:
        a = ADR_FRONTMATTER.replace("ADR-9001", "ADR-KNOWN")
        b = ADR_FRONTMATTER.replace("ADR-9001", "ADR-KNOWN").replace("Test ADR", "B")
        c = ADR_FRONTMATTER.replace("ADR-9001", "ADR-KNOWN").replace("Test ADR", "C")
        _write(repo, "adrs/known-a.md", a)
        _write(repo, "adrs/known-b.md", b)
        _write(repo, "adrs/known-c.md", c)
        known = {"ADR-KNOWN": frozenset({"adrs/known-a.md", "adrs/known-b.md"})}
        errors = validate.check_adr_id_uniqueness(repo, known_collisions=known)
        assert len(errors) == 1
        assert "known-c.md" in errors[0]

    def test_known_collisions_default_covers_the_live_adr_0010_pair(self) -> None:
        # Proof against real repo content (AC1): the raw, un-exempted
        # detection this check is built on genuinely finds today's live
        # ADR-0010 collision, naming both real paths and the shared id —
        # this is not only provable against synthetic fixtures.
        live_root = Path(__file__).resolve().parent.parent
        by_id = validate._collect_adr_ids(live_root)
        colliding = by_id.get("ADR-0010", [])
        names = {p.name for p in colliding}
        assert names == {
            "ADR-0010-adaptive-recursive-contract-bisection.md",
            "ADR-0010-required-context-parity-ratchet.md",
        }
        # And it is exactly the pair the default allowlist exempts by path —
        # proving the exemption is scoped to precisely this known defect,
        # not a blanket suppression.
        rel = frozenset(str(p.relative_to(live_root)) for p in colliding)
        assert validate._KNOWN_ADR_ID_COLLISIONS["ADR-0010"] == rel


class TestNamingConvention:
    """Coverage for ``check_naming_convention`` — the three filename shapes.

    ``check_naming_convention`` only looks at the path (via
    ``_find_artifact_files``), never frontmatter, so these fixtures use
    minimal placeholder bodies rather than full valid frontmatter.
    """

    _BODY = "placeholder body\n"

    def test_id_shaped_sections_accept_the_numbered_prefix(self, repo: Path) -> None:
        _write(repo, "adrs/ADR-9001-first-decision.md", self._BODY)
        _write(repo, "pivots/PIVOT-9001-first-pivot.md", self._BODY)
        assert validate.check_naming_convention(repo) == []

    def test_id_shaped_sections_reject_a_date_prefix(self, repo: Path) -> None:
        _write(repo, "adrs/2026-08-19-first-decision.md", self._BODY)
        errors = validate.check_naming_convention(repo)
        assert len(errors) == 1
        assert "adrs/2026-08-19-first-decision.md" in errors[0]

    def test_id_shaped_sections_reject_a_bare_kebab_name(self, repo: Path) -> None:
        _write(repo, "pivots/first-pivot.md", self._BODY)
        errors = validate.check_naming_convention(repo)
        assert len(errors) == 1
        assert "pivots/first-pivot.md" in errors[0]

    def test_dated_sections_accept_the_date_prefix(self, repo: Path) -> None:
        _write(repo, "experiments/2026-08-19-first-experiment.md", self._BODY)
        _write(repo, "plans/2026-08-19-first-plan.md", self._BODY)
        assert validate.check_naming_convention(repo) == []

    def test_dated_sections_reject_an_undated_kebab_name(self, repo: Path) -> None:
        _write(repo, "plans/first-plan.md", self._BODY)
        errors = validate.check_naming_convention(repo)
        assert len(errors) == 1
        assert "plans/first-plan.md" in errors[0]

    def test_dated_sections_reject_a_numbered_id_prefix(self, repo: Path) -> None:
        _write(repo, "experiments/ADR-9001-first-experiment.md", self._BODY)
        errors = validate.check_naming_convention(repo)
        assert len(errors) == 1
        assert "experiments/ADR-9001-first-experiment.md" in errors[0]

    def test_living_sections_accept_a_bare_kebab_name(self, repo: Path) -> None:
        _write(repo, "doctrine/first-principle.md", self._BODY)
        _write(repo, "architecture/first-subsystem.md", self._BODY)
        _write(repo, "guides/first-guide.md", self._BODY)
        _write(repo, "reference/first-reference.md", self._BODY)
        _write(repo, "runbooks/first-runbook.md", self._BODY)
        assert validate.check_naming_convention(repo) == []

    def test_living_sections_reject_a_date_prefix(self, repo: Path) -> None:
        # The exact defect this rule closes: architecture/ carried 13
        # dated filenames before this pass even though it is a living,
        # revised-in-place section.
        _write(repo, "architecture/2026-07-21-first-subsystem.md", self._BODY)
        errors = validate.check_naming_convention(repo)
        assert len(errors) == 1
        assert "architecture/2026-07-21-first-subsystem.md" in errors[0]

    def test_living_sections_reject_an_uppercase_or_underscored_name(self, repo: Path) -> None:
        _write(repo, "doctrine/First_Principle.md", self._BODY)
        errors = validate.check_naming_convention(repo)
        assert len(errors) == 1
        assert "doctrine/First_Principle.md" in errors[0]

    def test_readme_and_template_are_exempt_in_every_section(self, repo: Path) -> None:
        for section in validate.ARTIFACT_DIRS:
            _write(repo, f"{section}/README.md", self._BODY)
            _write(repo, f"{section}/_template.md", self._BODY)
        assert validate.check_naming_convention(repo) == []

    def test_live_repo_tree_is_fully_conforming(self) -> None:
        # Proof against real repo content, not only synthetic fixtures —
        # the rename sweep that shipped alongside this rule brought every
        # existing file into conformance rather than grandfathering it.
        live_root = Path(__file__).resolve().parent.parent
        assert validate.check_naming_convention(live_root) == []


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
