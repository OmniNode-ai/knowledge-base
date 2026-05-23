# CLAUDE.md

## Repository: OmniNode-ai/knowledge-base

Public architectural provenance system for OmniNode.

## Commands
- `uv run python scripts/validate.py` — validate all frontmatter, cross-references, and sanitization
- `uv run python scripts/generate_indexes.py` — regenerate index files from frontmatter
- `uv run ruff check scripts/` — lint Python scripts
- `uv run ruff format scripts/` — format Python scripts

## Rules
- Every markdown artifact file in `doctrine/`, `adrs/`, `pivots/`, `deep-dives/`, `experiments/`, `evidence/`, `plans/` MUST have valid YAML frontmatter
- No internal ticket references (OMN-XXXX), internal IPs, private repo URLs, or personal information
- Cross-references in `refs:` must point to existing files
- Indexes must match generated output (run generate_indexes.py before committing)
