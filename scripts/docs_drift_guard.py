"""Docs migration drift guard.

Enforces the two rules the migration plan depends on: a product repository
must not re-grow a document that migrated to the knowledge base (bucket A),
and a thinned bucket-B document must not drop its verbatim pointer line or
exceed the line budget the manifest declares for it.

The guard reads `migration-manifest.yaml` from `knowledge-base@main` by
default (never a PR branch — see docs-taxonomy.md and the manifest's own
header comment) so a product-repo PR cannot weaken its own guard by editing
the manifest in the same change. `--manifest-path` overrides this with a
local file and exists only for the knowledge-base repo's own CI self-check
and for tests; a product repo's real invocation (see
`.github/workflows/docs-drift-guard-reusable.yml`) must always use the
default URL fetch.

Fails closed: any manifest fetch/parse failure is a guard FAILURE (nonzero
exit), never treated as "zero violations". An unreadable manifest is an
UNKNOWN, and UNKNOWN is a failure, not a pass.

Row nesting is a build-time decision, not yet fixed by the taxonomy: the
landed manifest is still `STATE: skeleton` with per-repository entries only
(no per-document rows exist yet — see migration-manifest.yaml's own header).
This guard reads per-document rows from an optional `rows:` list nested
under each `repos[]` entry, one dict per row matching `row_schema`. Until
Wave 2 writes real rows, every repo's row list is empty and the guard is
correctly a no-op — see tests/test_docs_drift_guard.py for the fixture proof
this file cannot give on its own with today's manifest content.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/OmniNode-ai/knowledge-base/main/migration-manifest.yaml"

# Matched verbatim — see docs-taxonomy.md, "Bucket B" section, which states
# this exact string and warns that a reworded variant reads as a missing
# pointer by design. Duplicated here as the enforced literal rather than
# parsed out of the doc at runtime; test_pointer_string_matches_docs_taxonomy
# pins the two together so they cannot silently diverge.
POINTER_STRING = "Full documentation → https://github.com/OmniNode-ai/knowledge-base"

NOT_STARTED = "not-started"

# Sockets fail slowly, not silently: bound how long a hung raw.githubusercontent.com
# fetch can block a CI job before the guard's own fail-closed handling kicks in.
FETCH_TIMEOUT_SECONDS = 15


class ManifestError(RuntimeError):
    """The manifest could not be fetched or parsed. Always fail-closed."""


@dataclass(frozen=True)
class Violation:
    rule: str
    source_path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"[{self.rule}] {self.source_path}: {self.message}"


def load_manifest(*, manifest_path: str | None, manifest_url: str) -> dict[str, Any]:
    """Read and parse the manifest. Raises ManifestError on any failure.

    This is the single fail-closed boundary: every caller of this function
    must treat a raised ManifestError as a guard FAILURE, not as "no rows to
    check".
    """
    try:
        if manifest_path is not None:
            text = Path(manifest_path).read_text(encoding="utf-8")
        else:
            with urllib.request.urlopen(manifest_url, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
                text = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as exc:
        raise ManifestError(f"could not read manifest ({manifest_path or manifest_url}): {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"manifest is not valid YAML: {exc}") from exc

    if not isinstance(data, dict) or "repos" not in data or not isinstance(data["repos"], list):
        raise ManifestError(
            "manifest has no top-level 'repos' list after parsing — fetched the wrong content, "
            "or the manifest's shape changed underneath this guard"
        )
    return data


def find_repo_rows(manifest: dict[str, Any], repo_name: str) -> list[dict[str, Any]]:
    """Per-document rows declared for one repo. Empty is a valid, non-error state.

    A repo absent from the manifest, or present with no `rows:` list, has
    nothing to check yet — this is the correct state for every repo today
    (manifest STATE: skeleton, no per-document rows exist). It is distinct
    from ManifestError: "nothing declared" is not "could not read the
    declaration".
    """
    for repo in manifest.get("repos", []):
        if isinstance(repo, dict) and repo.get("repo") == repo_name:
            rows = repo.get("rows") or []
            return [row for row in rows if isinstance(row, dict)]
    return []


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def check_bucket_a_regrowth(rows: list[dict[str, Any]], repo_root: Path) -> list[Violation]:
    """Rule 1: a moved bucket-A document must not exist anywhere in this repo.

    A bucket-A row's `destination` is a knowledge-base path, i.e. a
    different repository — so once cutover_state has left not-started, the
    only valid location for the source document is *not in this repo at
    all*. Presence of the file at its original source_path, regardless of
    content, is re-growth.
    """
    violations = []
    for row in rows:
        if row.get("bucket") != "A":
            continue
        cutover_state = row.get("cutover_state", NOT_STARTED)
        if cutover_state == NOT_STARTED:
            continue
        source_path = row.get("source_path")
        if not source_path:
            continue
        if (repo_root / source_path).exists():
            violations.append(
                Violation(
                    rule="bucket-a-regrowth",
                    source_path=source_path,
                    message=(
                        f"bucket A, cutover_state={cutover_state!r} — this document migrated to "
                        f"{row.get('destination')!r} in knowledge-base and must not exist in this "
                        "repository any more"
                    ),
                )
            )
    return violations


def check_bucket_b_pointer(rows: list[dict[str, Any]], repo_root: Path) -> list[Violation]:
    """Rule 2: a moved bucket-B document must keep its verbatim pointer and size budget."""
    violations = []
    for row in rows:
        if row.get("bucket") != "B":
            continue
        cutover_state = row.get("cutover_state", NOT_STARTED)
        if cutover_state == NOT_STARTED:
            continue
        source_path = row.get("source_path")
        if not source_path:
            continue
        file_path = repo_root / source_path
        if not file_path.exists():
            violations.append(
                Violation(
                    rule="bucket-b-pointer",
                    source_path=source_path,
                    message=f"bucket B, cutover_state={cutover_state!r} but the file does not exist in this repo",
                )
            )
            continue

        text = file_path.read_text(encoding="utf-8")
        if POINTER_STRING not in text:
            violations.append(
                Violation(
                    rule="bucket-b-pointer",
                    source_path=source_path,
                    message=f"missing the verbatim pointer line {POINTER_STRING!r}",
                )
            )

        max_lines = row.get("max_lines")
        if max_lines is not None:
            line_count = _line_count(text)
            if line_count > max_lines:
                violations.append(
                    Violation(
                        rule="bucket-b-size-budget",
                        source_path=source_path,
                        message=f"{line_count} lines exceeds the manifest's max_lines budget of {max_lines}",
                    )
                )
    return violations


def run_guard(rows: list[dict[str, Any]], repo_root: Path) -> list[Violation]:
    return check_bucket_a_regrowth(rows, repo_root) + check_bucket_b_pointer(rows, repo_root)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--repo-name", required=True, help="Repo key as it appears in migration-manifest.yaml repos[].repo"
    )
    parser.add_argument("--repo-root", default=".", help="Checked-out root of the repo being guarded")
    parser.add_argument("--manifest-url", default=DEFAULT_MANIFEST_URL)
    parser.add_argument(
        "--manifest-path",
        default=None,
        help=(
            "Local manifest file, overrides --manifest-url. For the knowledge-base repo's own CI "
            "self-check and for tests only — a product repo's real guard invocation must fetch "
            "from knowledge-base@main, never read a local copy of the manifest."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        manifest = load_manifest(manifest_path=args.manifest_path, manifest_url=args.manifest_url)
    except ManifestError as exc:
        print(f"FAIL-CLOSED: {exc}", file=sys.stderr)
        return 1

    rows = find_repo_rows(manifest, args.repo_name)
    violations = run_guard(rows, Path(args.repo_root))

    if violations:
        print(f"docs drift guard: {len(violations)} violation(s) for repo {args.repo_name!r}:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1

    print(f"docs drift guard: 0 violations for repo {args.repo_name!r} ({len(rows)} row(s) checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
