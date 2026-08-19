"""Generate index files from artifact frontmatter.

Usage:
    uv run python scripts/generate_indexes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ARTIFACT_DIRS = [
    "doctrine",
    "adrs",
    "architecture",
    "pivots",
    "deep-dives",
    "experiments",
    "evidence",
    "plans",
    "guides",
    "reference",
    "runbooks",
]
SKIP_FILES = {"README.md", "_template.md"}


def parse_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file."""
    content = path.read_text()
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        return yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None


def collect_artifacts(root: Path) -> list[dict]:
    """Collect all artifacts with their frontmatter and paths.

    Discovery is recursive (``rglob``) so a document nested in a
    subdirectory of any section is indexed rather than silently omitted.
    """
    artifacts = []
    for dir_name in ARTIFACT_DIRS:
        dir_path = root / dir_name
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            if md_file.name in SKIP_FILES:
                continue
            fm = parse_frontmatter(md_file)
            if fm:
                fm["_path"] = str(md_file.relative_to(root))
                fm["_dir"] = dir_name
                artifacts.append(fm)
    return artifacts


def generate_chronological(artifacts: list[dict]) -> str:
    """Generate chronological index sorted by date."""
    lines = [
        "# Chronological Index",
        "",
        "Generated — do not edit manually. Run `uv run python scripts/generate_indexes.py` to regenerate.",
        "",
        "All knowledge base artifacts sorted by date.",
        "",
    ]

    dated = [(a.get("date", ""), a) for a in artifacts if a.get("date")]
    dated.sort(key=lambda x: str(x[0]), reverse=True)

    current_month = ""
    for date_str, artifact in dated:
        date_str = str(date_str)
        month = date_str[:7] if len(date_str) >= 7 else date_str[:4]
        if month != current_month:
            current_month = month
            lines.append(f"## {current_month}")
            lines.append("")

        artifact_type = artifact.get("type", "unknown")
        title = artifact.get("title", "Untitled")
        path = artifact.get("_path", "")
        lines.append(f"- **[{title}]({path})** ({artifact_type}) — {date_str}")

    if not dated:
        lines.append("No dated artifacts found.")

    lines.append("")
    return "\n".join(lines)


def generate_by_topic(artifacts: list[dict]) -> str:
    """Generate topic index grouped by topic tag."""
    lines = [
        "# Topic Index",
        "",
        "Generated — do not edit manually. Run `uv run python scripts/generate_indexes.py` to regenerate.",
        "",
        "Knowledge base artifacts grouped by topic.",
        "",
    ]

    topic_map: dict[str, list[dict]] = {}
    for artifact in artifacts:
        for topic in artifact.get("topics", []):
            topic_map.setdefault(topic, []).append(artifact)

    for topic in sorted(topic_map):
        lines.append(f"## {topic}")
        lines.append("")
        for artifact in topic_map[topic]:
            title = artifact.get("title", "Untitled")
            path = artifact.get("_path", "")
            artifact_type = artifact.get("type", "unknown")
            lines.append(f"- **[{title}]({path})** ({artifact_type})")
        lines.append("")

    if not topic_map:
        lines.append("No topics found.")
        lines.append("")

    return "\n".join(lines)


def generate_by_type(artifacts: list[dict]) -> str:
    """Generate type index grouped by artifact type."""
    lines = [
        "# Type Index",
        "",
        "Generated — do not edit manually. Run `uv run python scripts/generate_indexes.py` to regenerate.",
        "",
        "Knowledge base artifacts grouped by type.",
        "",
    ]

    type_map: dict[str, list[dict]] = {}
    for artifact in artifacts:
        artifact_type = artifact.get("type", "unknown")
        type_map.setdefault(artifact_type, []).append(artifact)

    type_order = [
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
    for artifact_type in type_order:
        if artifact_type not in type_map:
            continue
        display_name = artifact_type.replace("-", " ").title()
        lines.append(f"## {display_name}")
        lines.append("")
        for artifact in sorted(type_map[artifact_type], key=lambda a: str(a.get("date", ""))):
            title = artifact.get("title", "Untitled")
            path = artifact.get("_path", "")
            status = artifact.get("status", "")
            lines.append(f"- **[{title}]({path})** — {status}")
        lines.append("")

    for artifact_type in sorted(type_map):
        if artifact_type in type_order:
            continue
        lines.append(f"## {artifact_type.title()}")
        lines.append("")
        for artifact in type_map[artifact_type]:
            title = artifact.get("title", "Untitled")
            path = artifact.get("_path", "")
            lines.append(f"- **[{title}]({path})**")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).parent.parent
    artifacts = collect_artifacts(root)

    print(f"Found {len(artifacts)} artifacts across {len(ARTIFACT_DIRS)} directories")

    indexes_dir = root / "indexes"
    indexes_dir.mkdir(exist_ok=True)

    chronological = generate_chronological(artifacts)
    (indexes_dir / "chronological.md").write_text(chronological)
    print("  Generated indexes/chronological.md")

    by_topic = generate_by_topic(artifacts)
    (indexes_dir / "by-topic.md").write_text(by_topic)
    print("  Generated indexes/by-topic.md")

    by_type = generate_by_type(artifacts)
    (indexes_dir / "by-type.md").write_text(by_type)
    print("  Generated indexes/by-type.md")

    print("Index generation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
