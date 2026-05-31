"""Knowledge base validation — frontmatter, cross-references, and sanitization guard."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Discriminator, Tag, TypeAdapter, ValidationError

ARTIFACT_DIRS = ["adrs", "architecture", "doctrine", "pivots", "deep-dives", "experiments", "evidence", "plans"]
SKIP_FILES = {"_template.md", "README.md"}


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class BaseFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["doctrine", "adr", "architecture", "pivot", "deep-dive", "experiment", "evidence", "plan"]
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
)

FrontmatterAdapter: TypeAdapter[AnyFrontmatter] = TypeAdapter(Annotated[AnyFrontmatter, Discriminator(_discriminate)])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_artifact_files(root: Path) -> list[Path]:
    """Return all artifact markdown files (excluding skipped names)."""
    files = []
    for dir_name in ARTIFACT_DIRS:
        artifact_dir = root / dir_name
        if not artifact_dir.is_dir():
            continue
        for md_file in sorted(artifact_dir.glob("*.md")):
            if md_file.name not in SKIP_FILES:
                files.append(md_file)
    return files


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

    valid_types = {"doctrine", "adr", "architecture", "pivot", "deep-dive", "experiment", "evidence", "plan"}
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

SANITIZATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"OMN-\d+"), "Internal ticket reference"),
    (re.compile(r"192\.168\.\d+\.\d+"), "Internal IP address"),
    (re.compile(r"\.(200|201)\b"), "Internal host reference"),
    (re.compile(r"github\.com/OmniNode-ai/(?!knowledge-base)"), "Private repo URL"),
    (re.compile(r"infisical|INFISICAL"), "Internal secrets manager reference"),
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "Email address pattern"),
]

_ALLOWLIST_PATTERN = re.compile(r"#\s*sanitization-ok:\s*(.+)")


def check_sanitization(root: Path) -> list[str]:
    """Scan all artifact files for private content patterns."""
    errors = []
    for md_file in _find_artifact_files(root):
        content = md_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Collect allowlisted line numbers (1-indexed)
        allowlisted_lines: set[int] = set()
        for i, line in enumerate(lines, 1):
            if _ALLOWLIST_PATTERN.search(line):
                allowlisted_lines.add(i)

        for i, line in enumerate(lines, 1):
            if i in allowlisted_lines:
                continue
            for pattern, description in SANITIZATION_PATTERNS:
                if pattern.search(line):
                    errors.append(f"{md_file}:{i}: {description} — matches '{pattern.pattern}'")
                    break  # one error per line
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
