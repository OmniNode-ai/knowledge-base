"""Knowledge base validation — frontmatter, cross-references, and sanitization guard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Discriminator, Tag, TypeAdapter, ValidationError

ARTIFACT_DIRS = ["adrs", "doctrine", "pivots", "deep-dives", "experiments", "evidence", "plans"]
SKIP_FILES = {"_template.md", "README.md"}


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class BaseFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["doctrine", "adr", "pivot", "deep-dive", "experiment", "evidence", "plan"]
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
)

FrontmatterAdapter: TypeAdapter[AnyFrontmatter] = TypeAdapter(Annotated[AnyFrontmatter, Discriminator(_discriminate)])


# ---------------------------------------------------------------------------
# File-level validation
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> dict | None:
    """Return parsed YAML frontmatter dict, or None if not present."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    raw = text[3:end].strip()
    return yaml.safe_load(raw)


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

    valid_types = {"doctrine", "adr", "pivot", "deep-dive", "experiment", "evidence", "plan"}
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
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent

    if args.export_schema:
        export_schema(repo_root / args.export_schema)
        return 0

    all_errors: list[str] = []
    checked = 0

    for dir_name in ARTIFACT_DIRS:
        artifact_dir = repo_root / dir_name
        if not artifact_dir.is_dir():
            continue
        for md_file in sorted(artifact_dir.glob("*.md")):
            if md_file.name in SKIP_FILES:
                continue
            errors = validate_frontmatter(md_file)
            all_errors.extend(errors)
            checked += 1

    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print(f"\n{len(all_errors)} error(s) in {checked} file(s)", file=sys.stderr)
        return 1

    print(f"OK: {checked} artifact file(s) validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
