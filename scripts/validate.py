"""Knowledge base validation — frontmatter, cross-references, and sanitization guard."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Annotated, Literal, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Discriminator, Tag, TypeAdapter, ValidationError

# Make the sibling sanitization module importable regardless of CWD / import path.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sanitization_patterns import (  # noqa: E402  (path setup must precede import)
    SANITIZATION_PATTERNS,
    scan_text,
)

# Re-exported so importers of validate continue to find these names.
__all__ = ["SANITIZATION_PATTERNS", "scan_text"]

# The eight provenance sections (frontmatter-validated, dated artifact types)
# plus the three consumer sections opened by this module (guides, reference,
# runbooks — task-oriented, factual, and operational documentation with their
# own frontmatter models but no decision-ledger semantics).
ARTIFACT_DIRS = [
    "adrs",
    "architecture",
    "doctrine",
    "pivots",
    "deep-dives",
    "experiments",
    "evidence",
    "plans",
    "guides",
    "reference",
    "runbooks",
]
SKIP_FILES = {"_template.md", "README.md"}

# Directories holding generated or hand-maintained content that is not an
# artifact (no frontmatter, no cross-reference/broken-link semantics) but is
# still public prose and must be sanitization-scanned and registered.
GENERATED_CONTENT_DIRS = ["indexes"]

# Repository-root files that are content (public prose or checked-in data),
# scanned for sanitization but exempt from frontmatter validation. Charter
# docs plus the migration manifest plus the pre-commit tooling config (the
# only other root-level YAML file that currently exists).
ROOT_SANITIZED_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "docs-taxonomy.md",
    "migration-manifest.yaml",
    ".pre-commit-config.yaml",
}

# Directories pruned entirely from the fail-closed repository walk: version
# control internals and platform/CI configuration, never documentation
# content that could carry a leak.
EXCLUDED_WALK_DIRS = {".git", ".github", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache"}


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class BaseFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "doctrine",
        "adr",
        "architecture",
        "pivot",
        "deep-dive",
        "experiment",
        "evidence",
        "plan",
        "guide",
        "reference",
        "runbook",
    ]
    status: str
    date: str  # YYYY-MM-DD
    title: str
    topics: list[str] = []
    refs: list[str] = []


# ---------------------------------------------------------------------------
# Type-specific models
# ---------------------------------------------------------------------------


class DoctrineFrontmatter(BaseFrontmatter):
    type: Literal["doctrine"]
    status: Literal["draft", "accepted", "deprecated"]


class ADRFrontmatter(BaseFrontmatter):
    type: Literal["adr"]
    status: Literal["proposed", "accepted", "superseded", "deprecated", "rejected"]
    adr_id: str
    supersedes: list[str] = []
    superseded_by: list[str] = []


class PivotFrontmatter(BaseFrontmatter):
    type: Literal["pivot"]
    status: Literal["observed", "emerging", "accepted", "historical", "superseded"]
    observed_date: str
    confidence: Literal["low", "medium", "high"]


class DeepDiveFrontmatter(BaseFrontmatter):
    type: Literal["deep-dive"]
    status: Literal["draft", "public-curated"]
    period: str


class ExperimentFrontmatter(BaseFrontmatter):
    type: Literal["experiment"]
    status: Literal["proposed", "active", "completed"]
    hypothesis: str
    outcome: Literal["confirmed", "refuted", "inconclusive"] | None = None


class EvidenceFrontmatter(BaseFrontmatter):
    type: Literal["evidence"]
    status: Literal["draft", "accepted", "superseded"]


class PlanFrontmatter(BaseFrontmatter):
    type: Literal["plan"]
    status: Literal["draft", "active", "completed", "superseded"]


class ArchitectureFrontmatter(BaseFrontmatter):
    type: Literal["architecture"]
    status: Literal["draft", "accepted", "superseded", "deprecated"]


# Consumer documentation classes (task-oriented, factual, operational). No
# decision-ledger semantics, so they share one lifecycle vocabulary: a
# document is drafted, is current, goes stale, or is deprecated.
_CONSUMER_DOC_STATUS = Literal["draft", "current", "stale", "deprecated"]


class GuideFrontmatter(BaseFrontmatter):
    type: Literal["guide"]
    status: _CONSUMER_DOC_STATUS


class ReferenceFrontmatter(BaseFrontmatter):
    type: Literal["reference"]
    status: _CONSUMER_DOC_STATUS


class RunbookFrontmatter(BaseFrontmatter):
    type: Literal["runbook"]
    status: _CONSUMER_DOC_STATUS


# ---------------------------------------------------------------------------
# Discriminated union
# ---------------------------------------------------------------------------


def _discriminate(v: object) -> str:
    if isinstance(v, dict):
        return str(v.get("type", ""))
    return ""


AnyFrontmatter = (
    Annotated[ADRFrontmatter, Tag("adr")]
    | Annotated[DoctrineFrontmatter, Tag("doctrine")]
    | Annotated[PivotFrontmatter, Tag("pivot")]
    | Annotated[DeepDiveFrontmatter, Tag("deep-dive")]
    | Annotated[ExperimentFrontmatter, Tag("experiment")]
    | Annotated[EvidenceFrontmatter, Tag("evidence")]
    | Annotated[PlanFrontmatter, Tag("plan")]
    | Annotated[ArchitectureFrontmatter, Tag("architecture")]
    | Annotated[GuideFrontmatter, Tag("guide")]
    | Annotated[ReferenceFrontmatter, Tag("reference")]
    | Annotated[RunbookFrontmatter, Tag("runbook")]
)

FrontmatterAdapter: TypeAdapter[AnyFrontmatter] = TypeAdapter(Annotated[AnyFrontmatter, Discriminator(_discriminate)])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_artifact_files(root: Path) -> list[Path]:
    """Return all artifact markdown files, discovered recursively (excluding skipped names).

    Recursive (``rglob``) so a document nested in a subdirectory of any
    section — e.g. ``guides/getting-started/install.md`` — is enumerated
    rather than silently invisible to every check that consumes this list.
    """
    files = []
    for dir_name in ARTIFACT_DIRS:
        artifact_dir = root / dir_name
        if not artifact_dir.is_dir():
            continue
        for md_file in sorted(artifact_dir.rglob("*.md")):
            if md_file.name not in SKIP_FILES:
                files.append(md_file)
    return files


def _find_sanitization_targets(root: Path) -> list[Path]:
    """Return every file the sanitization guard must scan.

    Broader than ``_find_artifact_files``: ``SKIP_FILES`` (README.md,
    _template.md) governs frontmatter/cross-reference/broken-link scope only
    — it must never also exempt content from the sanitization guard, since a
    section README or template is still hand-written public prose. This also
    covers generated content dirs (``indexes/``) and repository-root charter
    documents plus checked-in YAML, closing the two gaps where a leak was
    previously outside the artifact scan entirely.
    """
    files: list[Path] = []
    for dir_name in ARTIFACT_DIRS:
        artifact_dir = root / dir_name
        if artifact_dir.is_dir():
            files.extend(sorted(artifact_dir.rglob("*.md")))
    for dir_name in GENERATED_CONTENT_DIRS:
        gen_dir = root / dir_name
        if gen_dir.is_dir():
            files.extend(sorted(gen_dir.rglob("*.md")))
    for name in sorted(ROOT_SANITIZED_FILES):
        root_file = root / name
        if root_file.is_file():
            files.append(root_file)
    return files


def _is_registered_location(path: Path, root: Path) -> bool:
    """Return whether ``path`` sits inside a location every check knows about.

    A file is registered if it is anywhere under one of ``ARTIFACT_DIRS``
    (any depth — README/template naming is a frontmatter-scope exemption,
    not a location exemption), anywhere under a generated-content dir, or is
    one of the explicitly allowlisted root files.
    """
    rel = path.relative_to(root)
    top = rel.parts[0]
    if top in ARTIFACT_DIRS:
        return True
    if top in GENERATED_CONTENT_DIRS:
        return True
    if len(rel.parts) == 1 and rel.name in ROOT_SANITIZED_FILES:
        return True
    return False


def check_registered_locations(root: Path) -> list[str]:
    """Fail closed on any markdown/YAML file outside a recognized location.

    Walks the entire repository (pruning only version-control and CI/platform
    config directories, never documentation content) and errors on every
    ``*.md``/``*.yaml``/``*.yml`` file that is not inside ``ARTIFACT_DIRS``, a
    generated-content dir, or the root-file allowlist. This is the guard
    against the failure mode this module exists to close: a content file in
    an unregistered location must be an error, never a silent skip.
    """
    errors = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_WALK_DIRS]
        for filename in sorted(filenames):
            if not filename.endswith((".md", ".yaml", ".yml")):
                continue
            path = Path(dirpath) / filename
            if not _is_registered_location(path, root):
                rel = path.relative_to(root)
                errors.append(
                    f"{path}: unregistered location — '{rel}' is not inside a declared "
                    f"ARTIFACT_DIRS section, a generated-content dir, or the root-file "
                    f"allowlist, so no check would otherwise scan it. Register it "
                    f"deliberately (extend ARTIFACT_DIRS / GENERATED_CONTENT_DIRS / "
                    f"ROOT_SANITIZED_FILES in scripts/validate.py) or move it, "
                    f"do not leave it unscanned."
                )
    return errors


def _extract_frontmatter(text: str) -> dict | None:
    """Return parsed YAML frontmatter dict, or None if not present."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    raw = text[3:end].strip()
    return yaml.safe_load(raw)


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------


def _valid_frontmatter_types() -> set[str]:
    """Single source for the recognized ``type`` values.

    Derived from ``BaseFrontmatter.type``'s ``Literal`` rather than a second
    hand-maintained set, so the two can never drift apart.
    """
    return set(get_args(BaseFrontmatter.model_fields["type"].annotation))


def validate_frontmatter(file_path: Path) -> list[str]:
    """Return list of error strings for the given markdown file (empty = valid)."""
    text = file_path.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    if fm is None:
        return [f"{file_path}: missing frontmatter block"]
    if not isinstance(fm, dict):
        return [f"{file_path}: frontmatter is not a YAML mapping"]

    artifact_type = fm.get("type")
    if not artifact_type:
        return [f"{file_path}: frontmatter missing 'type' field"]

    valid_types = _valid_frontmatter_types()
    if artifact_type not in valid_types:
        return [f"{file_path}: unknown type '{artifact_type}' — must be one of {sorted(valid_types)}"]

    try:
        FrontmatterAdapter.validate_python(fm)
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err["loc"]) if err["loc"] else "(root)"
            errors.append(f"{file_path}: [{loc}] {err['msg']}")
        return errors

    return []


def check_all_frontmatter(root: Path) -> list[str]:
    errors = []
    for md_file in _find_artifact_files(root):
        errors.extend(validate_frontmatter(md_file))
    return errors


# ---------------------------------------------------------------------------
# Cross-reference integrity
# ---------------------------------------------------------------------------


def check_cross_references(root: Path) -> list[str]:
    """For every refs: entry in frontmatter, verify the target file exists."""
    errors = []
    for md_file in _find_artifact_files(root):
        text = md_file.read_text(encoding="utf-8")
        fm = _extract_frontmatter(text)
        if not isinstance(fm, dict):
            continue
        for ref in fm.get("refs", []):
            target = root / ref
            if not target.exists():
                errors.append(f"{md_file}: broken ref '{ref}' — file does not exist")
    return errors


# ---------------------------------------------------------------------------
# Sanitization guard
# ---------------------------------------------------------------------------
#
# The forbidden-pattern list and the text scanner live in the dependency-free
# ``sanitization_patterns`` module so the commit-message / PR-text gate can
# reuse the exact same patterns without pulling in pyyaml/pydantic. Re-exported
# here for backward compatibility with anything importing from validate.


def check_sanitization(root: Path) -> list[str]:
    """Scan every registered content file for private content patterns.

    Covers artifact files (including README/_template files SKIP_FILES
    exempts from frontmatter checking — sanitization is a separate concern),
    generated indexes, and repository-root charter docs plus checked-in YAML.
    """
    errors = []
    for md_file in _find_sanitization_targets(root):
        content = md_file.read_text(encoding="utf-8")
        errors.extend(scan_text(content, label=str(md_file)))
    return errors


# ---------------------------------------------------------------------------
# Index freshness
# ---------------------------------------------------------------------------


def check_index_freshness(root: Path) -> list[str]:
    """Verify committed indexes match what generate_indexes.py would produce."""
    import sys

    scripts_dir = root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from generate_indexes import collect_artifacts, generate_by_topic, generate_by_type, generate_chronological

    artifacts = collect_artifacts(root)
    expected = {
        "chronological.md": generate_chronological(artifacts),
        "by-topic.md": generate_by_topic(artifacts),
        "by-type.md": generate_by_type(artifacts),
    }

    errors = []
    for index_file, expected_content in expected.items():
        path = root / "indexes" / index_file
        if not path.exists():
            errors.append(f"Missing index file: indexes/{index_file} — run: uv run python scripts/generate_indexes.py")
            continue
        actual = path.read_text()
        if actual != expected_content:
            errors.append(f"Stale index: indexes/{index_file} — run: uv run python scripts/generate_indexes.py")
    return errors


# ---------------------------------------------------------------------------
# Broken link detection
# ---------------------------------------------------------------------------

_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def check_broken_links(root: Path) -> list[str]:
    """Check for broken relative markdown links within artifact files."""
    errors = []
    for md_file in _find_artifact_files(root):
        content = md_file.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            for _text, href in _LINK_PATTERN.findall(line):
                # Skip absolute URLs and anchors
                if href.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path_part = href.split("#")[0]
                if not path_part:
                    continue
                target = (md_file.parent / path_part).resolve()
                if not target.exists():
                    errors.append(f"{md_file}:{i}: broken link '{href}' — file does not exist")
    return errors


# ---------------------------------------------------------------------------
# Schema export
# ---------------------------------------------------------------------------


def export_schema(output_path: Path) -> None:
    schema = FrontmatterAdapter.json_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Schema written to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate knowledge-base frontmatter")
    parser.add_argument(
        "--export-schema",
        metavar="PATH",
        nargs="?",
        const="schemas/frontmatter.schema.json",
        help="Write JSON schema to PATH (default: schemas/frontmatter.schema.json) and exit",
    )
    parser.add_argument(
        "--fix-indexes",
        action="store_true",
        help="Regenerate index files from artifact frontmatter",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent

    if args.export_schema:
        export_schema(repo_root / args.export_schema)
        return 0

    if args.fix_indexes:
        import sys

        scripts_dir = repo_root / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import generate_indexes

        return generate_indexes.main()

    all_errors: list[str] = []

    print("Checking for unregistered content locations...")
    all_errors.extend(check_registered_locations(repo_root))

    print("Validating frontmatter...")
    all_errors.extend(check_all_frontmatter(repo_root))

    print("Checking cross-references...")
    all_errors.extend(check_cross_references(repo_root))

    print("Running sanitization guard...")
    all_errors.extend(check_sanitization(repo_root))

    print("Checking index freshness...")
    all_errors.extend(check_index_freshness(repo_root))

    print("Checking for broken links...")
    all_errors.extend(check_broken_links(repo_root))

    if all_errors:
        print(f"\n{len(all_errors)} validation error(s):")
        for err in all_errors:
            print(f"  x {err}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
