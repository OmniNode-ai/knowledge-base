# CLAUDE.md

## Repository: OmniNode-ai/knowledge-base

Canonical home for OmniNode's external documentation, and the public architectural provenance system.

The charter is in [README.md](README.md); the rule deciding where any document belongs is in [docs-taxonomy.md](docs-taxonomy.md); the planned per-repository mapping is in [migration-manifest.yaml](migration-manifest.yaml). Read the taxonomy before adding a document — most "where does this go" questions are already answered there, and the answer is usually "here."

## Commands
- `uv run python scripts/validate.py` — run all eight checks: registered-location fail-closed sweep, frontmatter schema, filename naming convention, ADR `adr_id` uniqueness, `refs:` cross-references, sanitization, index freshness, and broken relative links
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
- Every markdown artifact file in `doctrine/`, `adrs/`, `architecture/`, `pivots/`, `experiments/`, `plans/`, `guides/`, `reference/`, `runbooks/` MUST have valid YAML frontmatter (validator skips `README.md` and `_template.md` for the frontmatter check only — those files are still sanitization-scanned). `deep-dives/` and `evidence/` were removed 2026-08-26 (self-hoster's-book scope ruling) and are no longer recognized sections — see `docs-taxonomy.md`.
- Discovery is recursive: a document nested in a subdirectory of any section is validated, not just top-level files
- No internal ticket references, internal IPs, internal host references, private repo URLs, secrets-manager references, or email addresses (enforced by `sanitization_patterns.py`) — the sanitization guard covers every artifact file (including nested paths and section READMEs), the generated `indexes/`, and repository-root content (`README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `docs-taxonomy.md`, `migration-manifest.yaml`)
- The private-repo-URL rule exempts an **explicit allowlist of exact public repository slugs** (`PUBLIC_REPO_SLUGS` in `scripts/sanitization_patterns.py`), anchored at a slug boundary — a `.git` clone suffix still passes, but a longer sibling name that merely *starts with* a public slug does not inherit the exemption and is blocked as a private repo URL. Making another org repository public means adding its exact slug to that tuple deliberately; `tests/test_sanitization_patterns.py` pins both directions, including the underscore candidate spellings, so a repository rename cannot silently change what this gate exempts.
- Cross-references in `refs:` must point to existing files
- Indexes must match generated output (run generate_indexes.py before committing)
- Every `.md`/`.yaml`/`.yml` file in the repository must live in a recognized location (an `ARTIFACT_DIRS` section, a generated-content dir, or the root-file allowlist in `scripts/validate.py`) or the registered-location check fails closed — a new top-level section or an unexpected root file is a build error, not a silent skip. Adding a genuinely new section means updating `ARTIFACT_DIRS`/`GENERATED_CONTENT_DIRS`/`ROOT_SANITIZED_FILES` deliberately.
- `validate.py` checks ADR `adr_id` uniqueness across `adrs/`. One known collision (`ADR-0010`, two files) is exempted by its exact claiming-path set, pending decision-record-owner sign-off on which file keeps the identifier — see the callout in `adrs/README.md`. Any other collision, or a change to this pair's file set, fails the build.
- Every artifact filename must match its section's naming convention (`validate.py` `_NAMING_PATTERNS`, documented in `CONTRIBUTING.md`): `adrs/ADR-NNNN-kebab-title.md` and `pivots/PIVOT-NNNN-kebab-title.md` carry a numbered decision-ledger id, never a date; `experiments/` and `plans/` carry a `YYYY-MM-DD-kebab-title.md` date prefix (point-in-time, frozen records); `doctrine/`, `architecture/`, `guides/`, `reference/`, and `runbooks/` carry no date in the filename at all (living reference docs revised in place — the date lives in frontmatter only, since `generate_indexes.py` reads frontmatter, never the filename). `README.md`/`_template.md` are exempt.

<!-- verified against scripts/, .pre-commit-config.yaml, and .github/workflows/ci.yml on the 2026-08-19 charter refresh -->
