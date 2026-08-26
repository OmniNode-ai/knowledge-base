# Contributing to the OmniNode Knowledge Base

## Overview

This repository is the canonical home for OmniNode's external documentation, and it captures architectural provenance — the reasoning behind decisions, the pivots that changed direction, and the evidence that proves claims. Contributions should meet that standard: specific, evidenced, and honest about uncertainty.

## Does this document belong here?

Read **[docs-taxonomy.md](docs-taxonomy.md)** first. It carries the ordered decision rule that assigns every OmniNode document to exactly one home, and most "where does this go" questions are answered there. The short version: unless a document is a dated point-in-time artifact, is on the closed list of files that must ship beside code, or stays sensitive after scrubbing, it belongs here.

One constraint from the taxonomy binds contributions today:

- **No content has migrated yet.** [`migration-manifest.yaml`](migration-manifest.yaml) holds the planned per-repository mapping; every row is at `not-started`.

The `guides/`, `reference/`, and `runbooks/` sections are now open: the validator recognizes all nine artifact classes and discovers files recursively, so nested paths are validated rather than silently skipped. A file placed anywhere the validator doesn't recognize — a new top-level directory, an unexpected root file — fails the build instead of going unscanned.

## File Naming Convention

Every artifact filename is lowercase kebab-case (`[a-z0-9]+(-[a-z0-9]+)*`), with the prefix determined by what kind of record the section holds. `scripts/validate.py` enforces this (`check_naming_convention`); `README.md` and `_template.md` are exempt everywhere.

| Shape | Sections | Example |
|---|---|---|
| `ID-NNNN-kebab-title.md` | `adrs/` (`ADR-`), `pivots/` (`PIVOT-`) | `adrs/ADR-0038-ci-workflow-modification-risk.md` |
| `YYYY-MM-DD-kebab-title.md` | `experiments/`, `plans/` | `experiments/2026-08-19-cache-warm-latency.md` |
| `kebab-title.md` (no date) | `doctrine/`, `architecture/`, `guides/`, `reference/`, `runbooks/` | `architecture/message-dispatch-engine.md` |

The numbered-id sections are decision-ledger records — the id matches the record's own `adr_id` (or pivot equivalent) in frontmatter and never changes once assigned. The dated sections are point-in-time records: written once, not revised afterward, so the date is load-bearing identity. The undated sections are living reference documents revised in place over a `draft` → `accepted` → `superseded`/`deprecated` lifecycle; every section still carries a required `date:` frontmatter field (it drives `indexes/chronological.md`), it is simply not duplicated into the filename — a filename date on a document that gets revised goes stale the moment the document is next edited, which is exactly what happened to `architecture/` before this convention was enforced.

## Proposing New Artifacts

### Architecture Decision Records (ADRs)

1. Copy [`adrs/_template.md`](adrs/_template.md) to `adrs/ADR-NNNN-short-title.md`
2. Fill in all frontmatter fields — `status` starts as `proposed`
3. Write the Context, Decision, and Alternatives Considered sections before opening a PR
4. Evidence and Consequences sections can be completed after the decision is implemented

### Architecture Technical Designs

1. Copy [`architecture/_template.md`](architecture/_template.md) to `architecture/short-title.md` — **no date in the filename.** A TDD is a living reference document, revised in place over its lifecycle (`draft` → `accepted` → `superseded`/`deprecated`); the authoring date belongs in the `date:` frontmatter field only, the same field `indexes/chronological.md` is generated from. A dated filename on a document that gets revised goes stale the moment it is next edited.
2. Status starts as `draft`; set to `accepted` once the design is ratified
3. Capture Purpose, Scope, Non-Goals, Design Principles, and Acceptance Criteria; distinguish current vs. target state honestly

### Pivots

1. Copy [`pivots/_template.md`](pivots/_template.md) to `pivots/PIVOT-NNNN-short-title.md`
2. Status starts as `emerging` until operational evidence confirms the new model
3. The "Original Assumption" and "Failure Modes Observed" sections are required — these are the most valuable parts

### Experiments

1. Copy [`experiments/_template.md`](experiments/_template.md) to `experiments/YYYY-MM-DD-short-title.md`
2. State the hypothesis clearly before running the experiment
3. Record the actual result honestly — "refuted" is a valid and valuable outcome

### Plans

1. Add `plans/YYYY-MM-DD-short-title.md` — a plan is a point-in-time record of an intended implementation path, not updated after the work is done (see [`plans/README.md`](plans/README.md)), so it carries the same date-prefixed shape as an experiment
2. Only plans that capture architectural intent worth preserving belong here — one that shaped how the system was built, was significantly revised, or contains reasoning about alternatives
3. Once the work is done, capture what actually happened in an ADR or pivot instead of updating the plan

### Guides, Reference, and Runbooks

1. Check [docs-taxonomy.md](docs-taxonomy.md) — the distinguishing test between the three sections is whether the reader is trying to *do* something (`guides/`), *look something up* (`reference/`), or *operate or recover* something (`runbooks/`)
2. Frontmatter `status` for these three types is `draft | current | stale | deprecated` — there is no decision-ledger lifecycle to track
3. Runbooks must be parameterized: use the placeholder tokens in [docs-taxonomy.md](docs-taxonomy.md) (`<onex-host>`, `<kafka-bootstrap-servers>`, `<runner-home>`, `<repo-root>`, `<cluster-ip>`) rather than a real address, hostname, or path

## Frontmatter Requirements

Every artifact file must begin with valid YAML frontmatter:

```yaml
---
type: adr | architecture | pivot | experiment | doctrine | plan | guide | reference | runbook
status: <lifecycle status for the type>
date: YYYY-MM-DD
title: "Descriptive title"
topics: [list, of, topics]
refs: [list/of/relative/file/paths.md]
---
```

Cross-references in `refs:` must point to files that exist in this repository. The validator will fail on broken references.

## PR Review Process

1. Run `uv run python scripts/validate.py` locally — it must exit 0 before opening a PR
2. Run `uv run pytest tests/ -v` and `uv run ruff check scripts/ tests/ && uv run ruff format scripts/ tests/` if you modified Python files
3. Open a PR with a description that explains what decision, pivot, or finding the artifact captures
4. CI must be green: the `validate` job runs the checks above (registered-location sweep, frontmatter, cross-references, sanitization, index freshness, broken links) plus the test suite, and the `sanitize-text` job scans the PR title, the PR body, and the PR's own commit messages
5. Review is expected before merge but is not currently enforced by branch protection — treat it as a norm, not a mechanism

### Your PR text is scanned, not just your files

The `sanitize-text` job applies the same forbidden-pattern list to the PR title, the PR body, and every commit message in the PR. It does **not** honor the `# sanitization-ok:` marker, so a leak in PR text cannot be self-exempted.

The practical consequence: **do not put an internal ticket identifier in a PR title, body, or commit message here.** This is a public repository and it deliberately carries no ticket references; linkage belongs in the internal tracker. A PR that names a ticket fails CI, and the fix is to remove the reference, never to work around the gate.

## Sanitization Rules

This is a **public repository**. Before submitting any artifact:

- No internal IP addresses or hostnames
- No internal ticket or issue identifiers
- No URLs pointing to private repositories
- No personal information (email addresses, usernames, credentials)
- No implementation-specific configuration values (passwords, tokens, connection strings)

The validator checks for common patterns. When in doubt, abstract the detail to the principle it represents.

## Running Validation Locally

```bash
# Install dependencies
uv sync

# Validate frontmatter, cross-references, and sanitization
uv run python scripts/validate.py

# Regenerate index files (run before committing if you added new artifacts)
uv run python scripts/generate_indexes.py

# Run the validator's own test suite
uv run pytest tests/ -v

# Lint and format Python scripts
uv run ruff check scripts/ tests/
uv run ruff format scripts/ tests/
```
