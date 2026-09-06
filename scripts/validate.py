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

# The six provenance sections (frontmatter-validated, dated artifact types)
# plus the three consumer sections opened by this module (guides, reference,
# runbooks — task-oriented, factual, and operational documentation with their
# own frontmatter models but no decision-ledger semantics). `deep-dives` and
# `evidence` were removed 2026-08-26 (self-hoster's-book scope ruling):
# operational journals never migrate here (durable insight is promoted into
# doctrine/ADR pages instead), and OCC (onex_change_control) is the sole
# evidence authority — this repository cites outcomes, it does not host
# receipts.
ARTIFACT_DIRS = [
    "adrs",
    "architecture",
    "doctrine",
    "pivots",
    "experiments",
    "plans",
    "guides",
    "reference",
    "runbooks",
]
SKIP_FILES = {"_template.md", "README.md"}

# Filename-shape convention. Every section falls into exactly one of three
# shapes (derived from the live tree + docs-taxonomy.md's dated-artifact
# test, not invented independently of it):
#   - "ADR-NNNN-kebab-title.md" / "PIVOT-NNNN-kebab-title.md" — a numbered
#     decision-ledger identifier, never a date, matching the record's own
#     adr_id (or pivot id) already carried in frontmatter.
#   - "YYYY-MM-DD-kebab-title.md" — a point-in-time record, frozen once
#     written; the date is load-bearing identity, not incidental metadata
#     (experiments/, plans/ — see their README.md files: neither is updated
#     after the fact).
#   - "kebab-title.md", no date, no numbered id — a standing reference
#     document that is revised in place (doctrine/, architecture/, guides/,
#     reference/, runbooks/). Its date lives in frontmatter only:
#     generate_indexes.py reads frontmatter exclusively and never parses the
#     filename, so a filename date on a living doc is pure duplication that
#     goes stale the moment the doc is next revised — the defect this rule
#     closes (architecture/ carried 13 dated filenames before this pass).
# README.md / _template.md are exempt (SKIP_FILES, checked by _find_artifact_files
# before this pattern is ever consulted) — fixed conventional names, not
# content-word filenames.
_KEBAB_WORD = r"[a-z0-9]+(?:-[a-z0-9]+)*"
# A living-section name must not itself look date-prefixed — digits are
# otherwise legal kebab characters (e.g. "omnimemory-arch-002-kafka-
# abstraction.md"), so a bare _KEBAB_WORD match alone would silently accept
# "2026-07-21-first-subsystem.md" too. The negative lookahead rejects
# specifically a leading YYYY-MM-DD- run without disallowing digits elsewhere
# in the name.
_LIVING = re.compile(rf"^(?!\d{{4}}-\d{{2}}-\d{{2}}-){_KEBAB_WORD}\.md$")
_NAMING_PATTERNS: dict[str, re.Pattern[str]] = {
    "adrs": re.compile(rf"^ADR-\d{{4}}-{_KEBAB_WORD}\.md$"),
    "pivots": re.compile(rf"^PIVOT-\d{{4}}-{_KEBAB_WORD}\.md$"),
    "experiments": re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}-{_KEBAB_WORD}\.md$"),
    "plans": re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}-{_KEBAB_WORD}\.md$"),
    "doctrine": _LIVING,
    "architecture": _LIVING,
    "guides": _LIVING,
    "reference": _LIVING,
    "runbooks": _LIVING,
}

# Directories holding generated or hand-maintained content that is not an
# artifact (no frontmatter, no cross-reference/broken-link semantics) but is
# still public prose and must be sanitization-scanned and registered.
#
#   - "indexes"  — generated from artifact frontmatter by generate_indexes.py.
#   - "docs"     — repository-support material rather than knowledge-base
#                  artifacts: the brand asset set and its BRAND.md rules
#                  summary. BRAND.md is hand-written public prose, so it is
#                  registered here to be sanitization-scanned; it carries no
#                  frontmatter and is not indexed.
GENERATED_CONTENT_DIRS = ["indexes", "docs"]

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

# Platform/CI configuration: registered as a sanitization-scanned,
# frontmatter-exempt location.
#
# `.github` used to be pruned from the walk below on the stated premise that CI
# configuration "could not carry a leak". A workflow comment naming a private
# repository by slug and describing its contents disproved that premise, and
# the gate reported green over it because nothing scanned the directory. A gate
# scoped to part of the tree reports green over the rest, so the directory is
# scanned rather than assumed harmless. Its files carry no frontmatter and are
# not indexed, exactly like GENERATED_CONTENT_DIRS.
PLATFORM_SANITIZED_DIRS = [".github"]

# File suffixes scanned for sanitization inside PLATFORM_SANITIZED_DIRS.
# Broader than the markdown-only artifact scan: a workflow is a `.yml`, and
# extension-scoped gates are the other half of this failure mode.
PLATFORM_SANITIZED_SUFFIXES = (".md", ".yml", ".yaml")

# Directories pruned entirely from the fail-closed repository walk: version
# control internals and local caches, never documentation content or platform
# configuration that could carry a leak.
EXCLUDED_WALK_DIRS = {".git", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache"}


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
        "experiment",
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


class ExperimentFrontmatter(BaseFrontmatter):
    type: Literal["experiment"]
    status: Literal["proposed", "active", "completed"]
    hypothesis: str
    outcome: Literal["confirmed", "refuted", "inconclusive"] | None = None


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
    | Annotated[ExperimentFrontmatter, Tag("experiment")]
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
    for dir_name in PLATFORM_SANITIZED_DIRS:
        platform_dir = root / dir_name
        if platform_dir.is_dir():
            files.extend(
                sorted(
                    p
                    for p in platform_dir.rglob("*")
                    if p.is_file() and p.suffix in PLATFORM_SANITIZED_SUFFIXES
                )
            )
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
    if top in PLATFORM_SANITIZED_DIRS:
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
# Filename naming convention
# ---------------------------------------------------------------------------


def check_naming_convention(root: Path) -> list[str]:
    """Fail on any artifact filename that does not match its section's shape.

    ``_find_artifact_files`` already excludes ``SKIP_FILES`` (README.md,
    _template.md), so those never reach this check. Every other artifact
    file's basename must match the pattern declared in ``_NAMING_PATTERNS``
    for its top-level section — see the shape docstring above
    ``_NAMING_PATTERNS`` for what each of the three shapes is and why each
    section is classed the way it is.
    """
    errors = []
    for md_file in _find_artifact_files(root):
        section = md_file.relative_to(root).parts[0]
        pattern = _NAMING_PATTERNS.get(section)
        if pattern is None:
            continue
        if not pattern.match(md_file.name):
            errors.append(
                f"{md_file}: filename does not match the {section}/ naming convention "
                f"(expected shape: {pattern.pattern!r}) — see CONTRIBUTING.md"
            )
    return errors


# ---------------------------------------------------------------------------
# ADR identifier uniqueness
# ---------------------------------------------------------------------------

# Known adr_id collisions already in the tree, each pending a decision-record
# owner's sign-off on which file keeps the identifier — an ADR's adr_id is a
# published public identifier, and renumbering it unilaterally risks breaking
# inbound refs: entries and external links, so this check flags and indexes
# the defect rather than picking a winner. Keyed by adr_id -> the *exact* set
# of repo-relative paths currently claiming it. An entry is removed the
# moment its collision is resolved; scoping to the exact path set (rather
# than just the id) means an unrelated new file joining the same adr_id, or
# a third path colliding on it, still fails the check below.
_KNOWN_ADR_ID_COLLISIONS: dict[str, frozenset[str]] = {
    "ADR-0010": frozenset(
        {
            "adrs/ADR-0010-adaptive-recursive-contract-bisection.md",
            "adrs/ADR-0010-required-context-parity-ratchet.md",
        }
    ),
}


def _collect_adr_ids(root: Path) -> dict[str, list[Path]]:
    """Group every discovered ADR file by its frontmatter ``adr_id``.

    Pure grouping with no exemption applied — the raw detection
    ``check_adr_id_uniqueness`` builds on, and independently provable
    against real repo content regardless of any known-collision exemption
    layered on top.
    """
    by_id: dict[str, list[Path]] = {}
    for md_file in _find_artifact_files(root):
        text = md_file.read_text(encoding="utf-8")
        fm = _extract_frontmatter(text)
        if not isinstance(fm, dict) or fm.get("type") != "adr":
            continue
        adr_id = fm.get("adr_id")
        if not adr_id:
            continue
        by_id.setdefault(str(adr_id), []).append(md_file)
    return by_id


def check_adr_id_uniqueness(root: Path, *, known_collisions: dict[str, frozenset[str]] | None = None) -> list[str]:
    """Fail on two or more ADRs sharing the same ``adr_id``.

    ``ADRFrontmatter.adr_id`` is a bare ``str`` with no uniqueness
    constraint, so nothing else in this module catches a collision — both
    records validate individually and the generated indexes are keyed off
    frontmatter, so they do not surface it either. A known, already-flagged
    collision pending owner sign-off (``_KNOWN_ADR_ID_COLLISIONS`` by
    default) is exempted by its *exact* claiming path set only; anything
    else — a new file, a third colliding path, a different adr_id — still
    fails, so the next batch add cannot silently reintroduce this defect.
    """
    if known_collisions is None:
        known_collisions = _KNOWN_ADR_ID_COLLISIONS

    errors = []
    for adr_id, paths in sorted(_collect_adr_ids(root).items()):
        if len(paths) <= 1:
            continue
        rel_paths = frozenset(str(p.relative_to(root)) for p in paths)
        if rel_paths == known_collisions.get(adr_id):
            continue
        joined = ", ".join(str(p) for p in sorted(paths))
        errors.append(f"duplicate adr_id '{adr_id}' claimed by {len(paths)} files: {joined}")
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

    print("Checking filename naming convention...")
    all_errors.extend(check_naming_convention(repo_root))

    print("Checking ADR identifier uniqueness...")
    all_errors.extend(check_adr_id_uniqueness(repo_root))

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
