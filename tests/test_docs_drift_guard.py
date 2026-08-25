"""Fixture tests for scripts/docs_drift_guard.py.

These tests build synthetic manifests with synthetic rows under ``tmp_path``,
and prove both directions for both rules: a violation is caught, and the
same fixture at its declared post-move state is clean. This is the AC3 proof
and does not depend on the real manifest's content.

test_real_manifest_is_inert_except_where_wave_2_has_landed_rows (near the
bottom) is a supplementary sanity check that pins today's live manifest
content — which repos have real rows and what those rows look like — so a
future edit that silently empties or corrupts a repo's `rows:` list is
caught here. It is not a substitute for the fixtures above it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import docs_drift_guard as guard  # noqa: E402  (path setup must precede import)

REPO_NAME = "sample-repo"


def _write_manifest(tmp_path: Path, rows: list[dict], *, repo_name: str = REPO_NAME) -> Path:
    manifest = {
        "schema_version": 1,
        "status": "skeleton",
        "repos": [
            {
                "repo": repo_name,
                "rows": rows,
            }
        ],
    }
    manifest_path = tmp_path / "migration-manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest_path


def _repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# load_manifest — fail-closed on an unreadable/unfetchable manifest
# ---------------------------------------------------------------------------


def test_fail_closed_on_missing_manifest_file(tmp_path: Path) -> None:
    with pytest.raises(guard.ManifestError):
        guard.load_manifest(
            manifest_path=str(tmp_path / "does-not-exist.yaml"), manifest_url=guard.DEFAULT_MANIFEST_URL
        )


def test_fail_closed_on_invalid_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("repos: [this is: not: valid: yaml", encoding="utf-8")
    with pytest.raises(guard.ManifestError):
        guard.load_manifest(manifest_path=str(bad), manifest_url=guard.DEFAULT_MANIFEST_URL)


def test_fail_closed_on_missing_repos_key(tmp_path: Path) -> None:
    wrong_shape = tmp_path / "wrong-shape.yaml"
    wrong_shape.write_text("schema_version: 1\nstatus: skeleton\n", encoding="utf-8")
    with pytest.raises(guard.ManifestError):
        guard.load_manifest(manifest_path=str(wrong_shape), manifest_url=guard.DEFAULT_MANIFEST_URL)


def test_unknown_repo_yields_zero_rows_not_a_manifest_error(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, rows=[])
    manifest = guard.load_manifest(manifest_path=str(manifest_path), manifest_url=guard.DEFAULT_MANIFEST_URL)
    assert guard.find_repo_rows(manifest, "some-other-repo") == []


# ---------------------------------------------------------------------------
# Rule 1 — bucket-A re-growth (both directions)
# ---------------------------------------------------------------------------


def test_bucket_a_regrown_doc_fails(tmp_path: Path) -> None:
    rows = [
        {
            "source_path": "docs/architecture/old-design.md",
            "bucket": "A",
            "destination": "architecture/old-design.md",
            "owner": "someone",
            "sensitivity": "public",
            "correctness_status": "current",
            "verification_evidence": "unverified — fixture",
            "cutover_state": "moved",
        }
    ]
    repo_root = _repo_root(tmp_path)
    doc = repo_root / "docs" / "architecture" / "old-design.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Old design\n\nThis should have moved out of the repo.\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert len(violations) == 1
    assert violations[0].rule == "bucket-a-regrowth"
    assert violations[0].source_path == "docs/architecture/old-design.md"


def test_bucket_a_doc_absent_after_move_passes(tmp_path: Path) -> None:
    rows = [
        {
            "source_path": "docs/architecture/old-design.md",
            "bucket": "A",
            "destination": "architecture/old-design.md",
            "owner": "someone",
            "sensitivity": "public",
            "correctness_status": "current",
            "verification_evidence": "unverified — fixture",
            "cutover_state": "moved",
        }
    ]
    repo_root = _repo_root(tmp_path)
    # Document only exists at its knowledge-base destination, which by
    # construction is not inside this repo's tree at all.

    violations = guard.run_guard(rows, repo_root)

    assert violations == []


def test_bucket_a_row_still_not_started_is_ignored_even_if_file_exists(tmp_path: Path) -> None:
    """Matches the real manifest's current state: every row is not-started, so
    the guard must be a no-op even though every document still physically
    exists in its origin repo."""
    rows = [
        {
            "source_path": "docs/architecture/old-design.md",
            "bucket": "A",
            "destination": "architecture/old-design.md",
            "owner": "someone",
            "sensitivity": "public",
            "correctness_status": "current",
            "verification_evidence": "unverified — fixture",
            "cutover_state": "not-started",
        }
    ]
    repo_root = _repo_root(tmp_path)
    doc = repo_root / "docs" / "architecture" / "old-design.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Old design\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert violations == []


# ---------------------------------------------------------------------------
# Rule 2 — bucket-B pointer + size budget (both directions)
# ---------------------------------------------------------------------------


def _bucket_b_row(**overrides: object) -> dict:
    row = {
        "source_path": "README.md",
        "bucket": "B",
        "destination": "stays-in-repo",
        "owner": "someone",
        "sensitivity": "public",
        "correctness_status": "current",
        "verification_evidence": "unverified — fixture",
        "cutover_state": "pointer-live",
    }
    row.update(overrides)
    return row


def test_bucket_b_missing_pointer_fails(tmp_path: Path) -> None:
    rows = [_bucket_b_row()]
    repo_root = _repo_root(tmp_path)
    (repo_root / "README.md").write_text("# Sample repo\n\nNo pointer here.\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert len(violations) == 1
    assert violations[0].rule == "bucket-b-pointer"
    assert violations[0].source_path == "README.md"


def test_bucket_b_with_verbatim_pointer_passes(tmp_path: Path) -> None:
    rows = [_bucket_b_row()]
    repo_root = _repo_root(tmp_path)
    (repo_root / "README.md").write_text(f"# Sample repo\n\n{guard.POINTER_STRING}\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert violations == []


def test_bucket_b_reworded_pointer_still_fails(tmp_path: Path) -> None:
    """docs-taxonomy.md states a reworded variant reads as a missing pointer
    by design, not by accident — pin that behavior directly."""
    rows = [_bucket_b_row()]
    repo_root = _repo_root(tmp_path)
    reworded = guard.POINTER_STRING.replace("Full documentation", "See full docs")
    (repo_root / "README.md").write_text(f"# Sample repo\n\n{reworded}\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert len(violations) == 1
    assert violations[0].rule == "bucket-b-pointer"


def test_bucket_b_missing_file_fails(tmp_path: Path) -> None:
    rows = [_bucket_b_row()]
    repo_root = _repo_root(tmp_path)
    # File does not exist at all.

    violations = guard.run_guard(rows, repo_root)

    assert len(violations) == 1
    assert violations[0].rule == "bucket-b-pointer"
    assert "does not exist" in violations[0].message


def test_bucket_b_not_started_is_ignored(tmp_path: Path) -> None:
    rows = [_bucket_b_row(cutover_state="not-started")]
    repo_root = _repo_root(tmp_path)
    # No file at all, and no pointer — would fail rule 2 if this row were live.

    violations = guard.run_guard(rows, repo_root)

    assert violations == []


def test_bucket_b_within_max_lines_passes(tmp_path: Path) -> None:
    rows = [_bucket_b_row(max_lines=5)]
    repo_root = _repo_root(tmp_path)
    body = "\n".join(["# Sample repo", "", "One line of real content.", "", guard.POINTER_STRING])
    (repo_root / "README.md").write_text(body + "\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert violations == []


def test_bucket_b_exceeds_max_lines_fails(tmp_path: Path) -> None:
    rows = [_bucket_b_row(max_lines=3)]
    repo_root = _repo_root(tmp_path)
    body = "\n".join(["# Sample repo", "", "Line 3", "Line 4", "Line 5", guard.POINTER_STRING])
    (repo_root / "README.md").write_text(body + "\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    size_violations = [v for v in violations if v.rule == "bucket-b-size-budget"]
    assert len(size_violations) == 1
    assert "exceeds" in size_violations[0].message


def test_bucket_b_no_max_lines_declared_skips_size_check(tmp_path: Path) -> None:
    """max_lines is optional per row_schema — its absence must not fail a row,
    only its presence-and-exceeded should."""
    rows = [_bucket_b_row()]  # no max_lines key at all
    repo_root = _repo_root(tmp_path)
    body = "\n".join([f"Line {i}" for i in range(500)] + [guard.POINTER_STRING])
    (repo_root / "README.md").write_text(body + "\n", encoding="utf-8")

    violations = guard.run_guard(rows, repo_root)

    assert violations == []


# ---------------------------------------------------------------------------
# CLI entry point — end to end against a fixture manifest
# ---------------------------------------------------------------------------


def test_main_exits_nonzero_on_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rows = [
        {
            "source_path": "docs/old.md",
            "bucket": "A",
            "destination": "architecture/old.md",
            "owner": "someone",
            "sensitivity": "public",
            "correctness_status": "current",
            "verification_evidence": "unverified — fixture",
            "cutover_state": "moved",
        }
    ]
    manifest_path = _write_manifest(tmp_path, rows)
    repo_root = _repo_root(tmp_path)
    doc = repo_root / "docs" / "old.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("still here\n", encoding="utf-8")

    exit_code = guard.main(
        [
            "--repo-name",
            REPO_NAME,
            "--repo-root",
            str(repo_root),
            "--manifest-path",
            str(manifest_path),
        ]
    )

    assert exit_code == 1
    assert "bucket-a-regrowth" in capsys.readouterr().err


def test_main_exits_zero_when_clean(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, rows=[])
    repo_root = _repo_root(tmp_path)

    exit_code = guard.main(
        [
            "--repo-name",
            REPO_NAME,
            "--repo-root",
            str(repo_root),
            "--manifest-path",
            str(manifest_path),
        ]
    )

    assert exit_code == 0


def test_main_fails_closed_on_missing_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = _repo_root(tmp_path)

    exit_code = guard.main(
        [
            "--repo-name",
            REPO_NAME,
            "--repo-root",
            str(repo_root),
            "--manifest-path",
            str(tmp_path / "does-not-exist.yaml"),
        ]
    )

    assert exit_code == 1
    assert "FAIL-CLOSED" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# The pointer literal must not silently drift from docs-taxonomy.md
# ---------------------------------------------------------------------------


def test_pointer_string_matches_docs_taxonomy() -> None:
    taxonomy_path = Path(__file__).resolve().parent.parent / "docs-taxonomy.md"
    text = taxonomy_path.read_text(encoding="utf-8")
    assert guard.POINTER_STRING in text, (
        "docs_drift_guard.POINTER_STRING no longer matches the verbatim pointer line in "
        "docs-taxonomy.md — update the constant (and re-check every repo's thinned "
        "bucket-B documents) rather than the doc, unless the doc change is deliberate."
    )


# ---------------------------------------------------------------------------
# Supplementary sanity check against the real, live manifest — NOT the AC3 proof.
# ---------------------------------------------------------------------------


def test_real_manifest_is_inert_except_where_wave_2_has_landed_rows() -> None:
    """Wave 2 migration PRs write real per-document rows as they land; the
    guard must stay a true no-op for every repo that has none yet, and must
    see exactly the rows a landed migration declared for the repos that do.
    This is a regression guard on today's real content, supplementary to the
    fixture tests above — it does not exercise either rule's violation path
    on synthetic data (see the fixtures above for that); it pins what the
    real manifest currently contains so a future edit that silently empties
    or corrupts a repo's `rows:` list is caught here.

    omnibase_core was the first repo with landed rows (first Wave 2 migration
    PR) and, as of a second omnibase_core migration pass (2026-08-25), is
    fully migrated: every docs/decisions/**, docs/standards/**, and
    docs/troubleshooting/** candidate has a row (23 total — 4 from the first
    pass plus 19 from the second). omniclaude, omnimemory, and
    omnibase_infra are the second, third, and fourth repos with landed rows
    (their own Wave 2 migration PRs). omnimarket is the fifth: its two
    declared bucket_a_candidates globs (docs/architecture/delegation-*,
    docs/reference/node-catalog.md) resolve to 3 files, all landed
    2026-08-25. omniintelligence is the sixth: its two declared
    bucket_a_candidates globs (docs/reference/**, docs/architecture/**)
    resolve to 6 files; 5 landed 2026-08-25 (2 corrected before publication)
    and 1 (DASH_INTEGRATION_TRUTH_BOUNDARY.md) is quarantined in-repo
    (cutover_state: not-started) pending a cross-repo omnidash-side pass, so
    it still contributes a row. onex_change_control is the seventh, fully
    migrated in its own single pass (2026-08-25): every docs/standards/**,
    docs/policy/**, and docs/governance/** candidate has a row except
    docs/standards/doctrine_clauses.yaml and docs/standards/doctrine_coverage.md,
    both reclassified bucket A -> B and retained in-repo unthinned as a
    generator/generated-output pair (see the repo's manifest notes).
    omnibase_infra and omniintelligence each carry one further row beyond
    their own bucket_a_candidates batch: docs/standards/STANDARD_DOC_LAYOUT.md,
    landed separately under Wave 2 item C7 (shared_layout_template), which
    reconciles that document's independently-diverged copies across
    omniclaude, omnibase_core, omnibase_infra, and omniintelligence into one
    canonical reference/standard-doc-layout.md — hence infra_prefixes
    includes docs/standards/ and the infra row count is 51, not 50. Every
    other repo must still be empty until its own migration PR lands — do
    not add rows for a repo here without a matching migration."""
    manifest_path = Path(__file__).resolve().parent.parent / "migration-manifest.yaml"
    manifest = guard.load_manifest(manifest_path=str(manifest_path), manifest_url=guard.DEFAULT_MANIFEST_URL)

    repos_with_rows = {
        repo["repo"]: guard.find_repo_rows(manifest, repo["repo"])
        for repo in manifest["repos"]
        if guard.find_repo_rows(manifest, repo["repo"])
    }

    expected_repos = {
        "omnibase_core",
        "omniclaude",
        "omnimemory",
        "omnibase_infra",
        "omnimarket",
        "omniintelligence",
        "onex_change_control",
    }
    assert set(repos_with_rows) == expected_repos, (
        f"expected only {sorted(expected_repos)} to have landed rows today, found rows for: {sorted(repos_with_rows)}"
    )
    assert len(repos_with_rows["omnibase_core"]) == 23
    core_prefixes = ("docs/decisions/", "docs/standards/", "docs/troubleshooting/")
    for row in repos_with_rows["omnibase_core"]:
        assert row["bucket"] == "A"
        assert row["cutover_state"] == "moved"
        assert row["source_path"].startswith(core_prefixes)

    assert len(repos_with_rows["omniclaude"]) == 21
    for row in repos_with_rows["omniclaude"]:
        assert row["bucket"] == "A"
        assert row["cutover_state"] == "moved"
        assert row["source_path"].startswith(("docs/architecture/", "docs/guides/", "docs/standards/"))

    assert len(repos_with_rows["omnimemory"]) == 5
    for row in repos_with_rows["omnimemory"]:
        assert row["bucket"] == "A"
        assert row["cutover_state"] == "pointer-live"
        assert row["correctness_status"] == "broken"
        assert row["source_path"].startswith("docs/architecture/") or row["source_path"].startswith(
            ("docs/runtime/", "docs/migrations/")
        )

    infra_rows = repos_with_rows["omnibase_infra"]
    assert len(infra_rows) == 51
    infra_prefixes = ("docs/architecture/", "docs/guides/", "docs/runbooks/", "docs/standards/")
    for row in infra_rows:
        assert row["bucket"] in {"A", "B"}
        assert row["cutover_state"] in {"moved", "not-started", "pointer-live"}
        assert row["source_path"].startswith(infra_prefixes)
    pointer_live = [r for r in infra_rows if r["cutover_state"] == "pointer-live"]
    not_started = [r for r in infra_rows if r["cutover_state"] == "not-started"]
    # 38 migrated-content rows plus the 2 directory-nav README.md rewrites,
    # both already pointer-live from the start.
    assert len(pointer_live) == 40
    assert len(not_started) == 10
    # Every not-started row is quarantined for a documented reason, never silently dropped.
    for row in not_started:
        assert row["sensitivity"] in {"needs-review", "public"}
        assert row["verification_evidence"]
    # The bucket-B seam manifest is the one not-started row that is public (it
    # stays in the repo because it's executable tooling, not because it's
    # under sensitivity review).
    hygiene_risk_not_started = [r for r in not_started if r["bucket"] == "A"]
    assert len(hygiene_risk_not_started) == 9
    for row in hygiene_risk_not_started:
        assert row["sensitivity"] == "needs-review"
        assert row["correctness_status"] == "hygiene-risk"

    market_rows = repos_with_rows["omnimarket"]
    assert len(market_rows) == 3
    for row in market_rows:
        assert row["bucket"] == "A"
        assert row["cutover_state"] == "moved"
        assert row["correctness_status"] == "broken"
        assert row["source_path"].startswith(("docs/architecture/delegation-", "docs/reference/node-catalog.md"))

    occ_rows = repos_with_rows["onex_change_control"]
    assert len(occ_rows) == 5
    occ_prefixes = ("docs/standards/", "docs/policy/", "docs/governance/")
    for row in occ_rows:
        assert row["bucket"] == "A"
        assert row["cutover_state"] == "moved"
        assert row["source_path"].startswith(occ_prefixes)
    # doctrine_clauses.yaml + doctrine_coverage.md are deliberately absent —
    # reclassified bucket B, stay in-repo as the generator/generated-output
    # pair (the repo's own CI dry-run-validates the registry on every PR).
    occ_source_paths = {r["source_path"] for r in occ_rows}
    assert "docs/standards/doctrine_clauses.yaml" not in occ_source_paths
    assert "docs/standards/doctrine_coverage.md" not in occ_source_paths
