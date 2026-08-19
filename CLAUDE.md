# CLAUDE.md

## Repository: OmniNode-ai/knowledge-base

Canonical home for OmniNode's external documentation, and the public architectural provenance system.

The charter is in [README.md](README.md); the rule deciding where any document belongs is in [docs-taxonomy.md](docs-taxonomy.md); the planned per-repository mapping is in [migration-manifest.yaml](migration-manifest.yaml). Read the taxonomy before adding a document — most "where does this go" questions are already answered there, and the answer is usually "here."

## Commands
- `uv run python scripts/validate.py` — run all five checks: frontmatter schema, `refs:` cross-references, sanitization, index freshness, and broken relative links
- `uv run python scripts/validate.py --export-schema [PATH]` — write the frontmatter JSON schema (default `schemas/frontmatter.schema.json`); CI fails if `schemas/frontmatter.schema.json` is out of date
- `uv run python scripts/validate.py --fix-indexes` — regenerate indexes (delegates to `generate_indexes.py`)
- `uv run python scripts/generate_indexes.py` — regenerate `indexes/{chronological,by-topic,by-type}.md` from frontmatter
- `uv run ruff check scripts/` — lint Python scripts
- `uv run ruff format scripts/` — format Python scripts

## Gates
- `scripts/check_text_sanitization.py` — separate gate scanning commit messages (`--commit-msg-file`), PR title/body (`--pr-title`/`--pr-body`), and a commit range (`--commit-range`). Wired as a `commit-msg` pre-commit hook (`.pre-commit-config.yaml`) and the `sanitize-text` CI job (`.github/workflows/ci.yml`). It shares `scripts/sanitization_patterns.py` with `validate.py` and does NOT honor the `# sanitization-ok:` author allowlist.
- **Consequence for pull requests: a PR title, body, or commit message that names an internal ticket identifier fails CI.** This repository is public and deliberately carries no ticket references. Ticket-to-PR linkage is recorded in the internal tracker, not here. This is the gate working, not a gate to route around.

## Rules
- Every markdown artifact file in `doctrine/`, `adrs/`, `architecture/`, `pivots/`, `deep-dives/`, `experiments/`, `evidence/`, `plans/` MUST have valid YAML frontmatter (validator skips `README.md` and `_template.md`)
- No internal ticket references, internal IPs, internal host references, private repo URLs, secrets-manager references, or email addresses (enforced by `sanitization_patterns.py`)
- Cross-references in `refs:` must point to existing files
- Indexes must match generated output (run generate_indexes.py before committing)
- Do NOT add content to `guides/`, `reference/`, or `runbooks/` yet, and do not nest artifacts in subdirectories of the existing sections. The validator recognizes a closed set of eight artifact types and discovers files with a top-level glob, so files in those locations are silently skipped by every check rather than rejected. Extending the tooling is a prerequisite tracked ahead of the first migration.

## Validation coverage limits (know these before trusting a green run)
- The artifact scan covers the eight provenance sections at their top level only — nested paths and the three declared consumer sections are invisible to it.
- Repository-root documents (`README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `docs-taxonomy.md`, `migration-manifest.yaml`) are outside the artifact scan entirely and are not sanitization-checked by `validate.py`. The commit-message gate still covers what you write about them; the file contents themselves are on the author.
- `validate.py` does not check decision-record identifier uniqueness, and there is currently a duplicate identifier in `adrs/`.

<!-- verified against scripts/, .pre-commit-config.yaml, and .github/workflows/ci.yml on the 2026-08-19 charter refresh -->
