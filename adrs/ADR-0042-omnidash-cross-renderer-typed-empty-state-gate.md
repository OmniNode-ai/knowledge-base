---
type: adr
status: accepted
date: "2026-06-18"
title: "ADR-0042: Cross-Renderer Typed Empty-State Gate"
adr_id: ADR-0042
topics: [omnidash, contract-driven-ui, empty-state, eslint, renderers]
refs: [architecture/omnidash-composable-frame.md, reference/omnidash-component-manifest.md]
supersedes: []
superseded_by: []
---

# ADR-0042: Cross-Renderer Typed Empty-State Gate

**Status**: Accepted
**Date**: 2026-06-18
**Source**: omnidash `docs/adr/004-cross-renderer-empty-state-gate.md` (filed in-repo as "ADR 004"; renumbered on migration into the platform-wide decision ledger)

---

## Context

Phase 1 of the contract-driven UI platform makes "no blind/blank render" a mechanical invariant. When the renderer-capability projection is stale, absent, or unsatisfiable, the dispatch surface must render a **typed** `EnumEmptyStateReason` — specifically `UPSTREAM_BLOCKED` — never a blank element and never a crash. The enforcement backing this was previously `local/no-projection-fallback`, which keys on React's `useProjectionQuery` hook and so was effectively React/chart-only.

## Decision

1. **Typed empty state.** The `CapabilityDispatcher` miss path is wired to a renderer-agnostic `TypedEmptyState`. `resolveCapabilityEmptyState` classifies a degraded (`is_degraded`), absent (no rows), or unsatisfiable capability read as `upstream-blocked`. `VizRenderer` renders the typed empty state on a dispatcher miss. The typed reason VALUE is exposed on `data-empty-state-reason` so the state is machine-verifiable.

2. **Cross-renderer gate.** A new ESLint rule `local/no-untyped-empty-state` generalizes the no-projection enforcement beyond React/charts. It applies to the whole cross-renderer file set (`src/**/*.{ts,tsx}`, `shared/**/*.ts`, `server/**/*.ts`) and flags any empty-state-reason literal that is not one of the four canonical values.

3. **Key on VALUES, not the symbol name.** The hand-authored chart type is `EmptyStateReason`; the generated mirror is `EnumEmptyStateReason`. Both carry the same four values. The rule keys on the VALUES (`no-data` | `missing-field` | `upstream-blocked` | `schema-invalid`) so it is agnostic to which symbol — or no symbol — a given renderer imports.

## Cross-Renderer Scope

The gate is **not** chart-only and **not** React-only:

- Rule scope spans plain `.ts` modules and `server/**` (Node, non-React) in addition to React `.tsx`.
- `src/no-untyped-empty-state.test.ts` exercises the rule against a **plain, non-React, non-chart `.ts` surface** (`src/__lint_fixture_empty_state.ts`), proving it fires and stays silent independent of React/JSX/chart context.

The canonical reason vocabulary lives once in `shared/types/empty-state-reason.ts` (`EMPTY_STATE_REASONS`, `EmptyStateReasonValue`), re-exporting the generated mirror's `EnumEmptyStateReason` type so every renderer and the gate share one value set.

## Consequences

- Adding a new empty-state reason requires editing the canonical Python enum, regenerating the TypeScript mirror, and updating `EMPTY_STATE_REASONS` + `CANONICAL_REASON_VALUES` in the rule in lockstep. There is intentionally no inline-disable escape hatch — a new reason is a platform-vocabulary change.
- A renderer that invents a reason synonym (`'error'`, `'not-found'`, `'blank'`) fails lint regardless of platform.

## Evidence

Verified against the live omnidash tree at migration time: `local/no-untyped-empty-state` is registered at `'error'` severity in `eslint.config.js`, and `shared/types/empty-state-reason.ts` exists.
