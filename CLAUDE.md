# CLAUDE.md

## Repository: OmniNode-ai/knowledge-base

Public architectural provenance system for OmniNode.

## Commands
- `uv run python scripts/validate.py` — run all five checks: frontmatter schema, `refs:` cross-references, sanitization, index freshness, and broken relative links
- `uv run python scripts/validate.py --export-schema [PATH]` — write the frontmatter JSON schema (default `schemas/frontmatter.schema.json`); CI fails if `schemas/frontmatter.schema.json` is out of date
- `uv run python scripts/validate.py --fix-indexes` — regenerate indexes (delegates to `generate_indexes.py`)
- `uv run python scripts/generate_indexes.py` — regenerate `indexes/{chronological,by-topic,by-type}.md` from frontmatter
- `uv run ruff check scripts/` — lint Python scripts
- `uv run ruff format scripts/` — format Python scripts

## Gates
- `scripts/check_text_sanitization.py` — separate gate scanning commit messages (`--commit-msg-file`), PR title/body (`--pr-title`/`--pr-body`), and a commit range (`--commit-range`). Wired as a `commit-msg` pre-commit hook (`.pre-commit-config.yaml`) and the `sanitize-text` CI job (`.github/workflows/ci.yml`). It shares `scripts/sanitization_patterns.py` with `validate.py` and does NOT honor the `# sanitization-ok:` author allowlist.

## Rules
- Every markdown artifact file in `doctrine/`, `adrs/`, `architecture/`, `pivots/`, `deep-dives/`, `experiments/`, `evidence/`, `plans/` MUST have valid YAML frontmatter (validator skips `README.md` and `_template.md`)
- No internal ticket references, internal IPs, internal host references, private repo URLs, secrets-manager references, or email addresses (enforced by `sanitization_patterns.py`)
- Cross-references in `refs:` must point to existing files
- Indexes must match generated output (run generate_indexes.py before committing)

<!-- verified against scripts/, .pre-commit-config.yaml, and .github/workflows/ci.yml on the 2026-06-21 refresh -->
