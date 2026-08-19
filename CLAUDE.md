# CLAUDE.md

## Repository: OmniNode-ai/knowledge-base

Canonical home for OmniNode's external documentation, and the public architectural provenance system.

The charter is in [README.md](README.md); the rule deciding where any document belongs is in [docs-taxonomy.md](docs-taxonomy.md); the planned per-repository mapping is in [migration-manifest.yaml](migration-manifest.yaml). Read the taxonomy before adding a document — most "where does this go" questions are already answered there, and the answer is usually "here."

## Commands
- `uv run python scripts/validate.py` — run all six checks: registered-location fail-closed sweep, frontmatter schema, `refs:` cross-references, sanitization, index freshness, and broken relative links
- `uv run python scripts/validate.py --export-schema [PATH]` — write the frontmatter JSON schema (default `schemas/frontmatter.schema.json`); CI fails if `schemas/frontmatter.schema.json` is out of date
- `uv run python scripts/validate.py --fix-indexes` — regenerate indexes (delegates to `generate_indexes.py`)
- `uv run python scripts/generate_indexes.py` — regenerate `indexes/{chronological,by-topic,by-type}.md` from frontmatter
- `uv run pytest tests/ -v` — run the validator's own test suite (required CI step)
- `uv run ruff check scripts/ tests/` — lint Python scripts
- `uv run ruff format scripts/ tests/` — format Python scripts

## Gates
- `scripts/check_text_sanitization.py` — separate gate scanning commit messages (`--commit-msg-file`), PR title/body (`--pr-title`/`--pr-body`), and a commit range (`--commit-range`). Wired as a `commit-msg` pre-commit hook (`.pre-commit-config.yaml`) and the `sanitize-text` CI job (`.github/workflows/ci.yml`). It shares `scripts/sanitization_patterns.py` with `validate.py` and does NOT honor the `# sanitization-ok:` author allowlist.
- **Consequence for pull requests: a PR title, body, or commit message that names an internal ticket identifier fails CI.** This repository is public and deliberately carries no ticket references. Ticket-to-PR linkage is recorded in the internal tracker, not here. This is the gate working, not a gate to route around.

## Rules
- Every markdown artifact file in `doctrine/`, `adrs/`, `architecture/`, `pivots/`, `deep-dives/`, `experiments/`, `evidence/`, `plans/`, `guides/`, `reference/`, `runbooks/` MUST have valid YAML frontmatter (validator skips `README.md` and `_template.md` for the frontmatter check only — those files are still sanitization-scanned)
- Discovery is recursive: a document nested in a subdirectory of any section is validated, not just top-level files
- No internal ticket references, internal IPs, internal host references, private repo URLs, secrets-manager references, or email addresses (enforced by `sanitization_patterns.py`) — the sanitization guard covers every artifact file (including nested paths and section READMEs), the generated `indexes/`, and repository-root content (`README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `docs-taxonomy.md`, `migration-manifest.yaml`)
- Cross-references in `refs:` must point to existing files
- Indexes must match generated output (run generate_indexes.py before committing)
- Every `.md`/`.yaml`/`.yml` file in the repository must live in a recognized location (an `ARTIFACT_DIRS` section, a generated-content dir, or the root-file allowlist in `scripts/validate.py`) or the registered-location check fails closed — a new top-level section or an unexpected root file is a build error, not a silent skip. Adding a genuinely new section means updating `ARTIFACT_DIRS`/`GENERATED_CONTENT_DIRS`/`ROOT_SANITIZED_FILES` deliberately.
- `validate.py` does not check decision-record identifier uniqueness, and there is currently a duplicate identifier in `adrs/` (tracked separately, ahead of this file).

<!-- verified against scripts/, .pre-commit-config.yaml, and .github/workflows/ci.yml on the 2026-08-19 charter refresh -->
