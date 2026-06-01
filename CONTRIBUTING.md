# Contributing to the OmniNode Knowledge Base

## Overview

This repository captures architectural provenance — the reasoning behind decisions, the pivots that changed direction, and the evidence that proves claims. Contributions should meet that standard: specific, evidenced, and honest about uncertainty.

## Proposing New Artifacts

### Architecture Decision Records (ADRs)

1. Copy [`adrs/_template.md`](adrs/_template.md) to `adrs/ADR-NNNN-short-title.md`
2. Fill in all frontmatter fields — `status` starts as `proposed`
3. Write the Context, Decision, and Alternatives Considered sections before opening a PR
4. Evidence and Consequences sections can be completed after the decision is implemented

### Architecture Technical Designs

1. Copy [`architecture/_template.md`](architecture/_template.md) to `architecture/YYYY-MM-DD-short-title.md`
2. Status starts as `draft`; set to `accepted` once the design is ratified
3. Capture Purpose, Scope, Non-Goals, Design Principles, and Acceptance Criteria; distinguish current vs. target state honestly

### Pivots

1. Copy [`pivots/_template.md`](pivots/_template.md) to `pivots/PIVOT-NNNN-short-title.md`
2. Status starts as `emerging` until operational evidence confirms the new model
3. The "Original Assumption" and "Failure Modes Observed" sections are required — these are the most valuable parts

### Deep Dives

1. Copy [`deep-dives/_template.md`](deep-dives/_template.md) to `deep-dives/YYYY-MM-DD-short-title.md`
2. Deep dives are narrative records — they do not need to be exhaustive, but they should identify candidate ADRs and pivots that emerged

### Experiments

1. Copy [`experiments/_template.md`](experiments/_template.md) to `experiments/YYYY-MM-DD-short-title.md`
2. State the hypothesis clearly before running the experiment
3. Record the actual result honestly — "refuted" is a valid and valuable outcome

## Frontmatter Requirements

Every artifact file must begin with valid YAML frontmatter:

```yaml
---
type: adr | architecture | pivot | deep-dive | experiment | doctrine | evidence | plan
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
2. Run `uv run ruff check scripts/ && uv run ruff format scripts/` if you modified Python files
3. Open a PR with a description that explains what decision, pivot, or finding the artifact captures
4. At least one review approval is required before merge

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

# Lint and format Python scripts
uv run ruff check scripts/
uv run ruff format scripts/
```
