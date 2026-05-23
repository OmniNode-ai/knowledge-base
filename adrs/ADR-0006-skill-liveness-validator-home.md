---
type: adr
status: accepted
date: 2026-04-28
title: "ADR-0006: Skill Liveness Validator Home"
adr_id: ADR-0006
topics: [validators, skills, architecture-layers, pre-commit, ci]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0006: Skill Liveness Validator Home

## Context

Two concurrent plans proposed the skill-backing-node liveness validator in different repository homes. The execution also surfaced a repo-policy constraint: reusable governance and validator logic should not be scattered into workspace-root helpers. Existing validator precedent already places validators in the core layer.

## Decision

The skill-backing-node liveness validator code lives in the **core models layer** (`omnibase_core`).

Invocation surfaces are split by audience:
- The **Claude Code agent plugin** (`omniclaude`) runs it in pre-commit for local author feedback.
- The **market node repository** (`omnimarket`) runs it in CI for shared enforcement.

This ADR applies to the skill-backing-node liveness validator only. It does not make every future validator a core-layer concern by default, but it does align with the current validator-in-core precedent.

## Alternatives Considered

1. **`omnimarket` as code home** — Rejected: too consumer-specific for a validator that scans skill declarations across repository boundaries. The validator logic should not be owned by one of its own enforcement targets.

2. **`omniclaude` as code home** — Rejected: `omniclaude` is a good invocation surface but the wrong ownership layer. Agent plugin code should not own shared architectural validators.

3. **`omnibase_compat` as code home** — Rejected: the compatibility layer should stay focused on DTOs and transitional seams, not become a general validator bucket.

## Consequences

- The competing validator sections in the two older plans are retired and replaced with pointers to this ADR.
- The implementation targets `omnibase_core` for code, not `omnimarket`, `omniclaude`, or `omnibase_compat`.
- `omniclaude` and `omnimarket` remain the enforcement surfaces, not the ownership home.
- Pre-commit (local author feedback) and CI (shared enforcement) form complementary gates — neither alone is sufficient.

## Related Doctrine

- Repo layering rule: `compat → core → spi → infra`. Reusable validators belong in `core` when shared across multiple enforcement surfaces.

## Derived From

Architectural plan overlap review identifying competing validator home proposals in two same-week plans.

## Evidence

Existing validator precedent in `omnibase_core` used as the reference pattern.

## Supersedes

## Superseded By
