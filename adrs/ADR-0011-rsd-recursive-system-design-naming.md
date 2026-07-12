---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0011: Name the Discipline RSD = Recursive System Design"
adr_id: ADR-0011
topics: [rsd, naming, recursive-system-design, pipeline-fill]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0011: Name the Discipline RSD = Recursive System Design

## Context

The synthesis doc's §5 ("Relation to RSD") ruled: do **not** reuse the "RSD" name for
the new recursive-contract-bisection system, because "RSD" already resolves to a live,
differently-scoped **Risk-Surface-Dependency** ticket-priority scorer (behind
`pipeline_fill`: `score = 0.30·blocking + 0.25·priority + 0.20·staleness +
0.15·repo_readiness + 0.10·size`), plus a one-off 2026-04-02 gloss "Recursive Score
Decomposition" that describes the *same* flat scorer. §5 concluded the new system
should be scoped as new WS-H arms and must not collide with the live scorer's acronym.
The operator then overrode that ruling by fiat within the same session.

## Decision

**RSD now means "Recursive System Design"** — the umbrella discipline for the entire
adaptive-decomposition design (ADR-0010 and its refinements). The acronym is
deliberately reclaimed (its third use in company history). This **operator fiat
OVERRIDES the synthesis doc's §5 do-not-reuse ruling** — an operator decision outranks
a synthesis ruling. Historical docs stay as written. The live Risk-Surface-Dependency
scorer keeps its full name as an internal and continues to run behind `pipeline_fill`;
the two systems compose as adjacent pipeline stages — RSD-the-scorer decides WHAT
enters the factory (intake priority), RSD-the-discipline decides HOW it gets built
(decomposition) — and are never merged into one system under one name.

## Alternatives Considered

1. Keep §5's ruling — do not reuse "RSD"; scope the system as unnamed WS-H arms. Rejected by operator fiat (naming authority is the operator's).
2. Coin an entirely new name to avoid all collision. Not chosen: the operator judged the "recursive" instinct predates the mechanism by 14 months and the name should attach to the mechanism that finally arrived.

## Consequences

"RSD" is now overloaded across two live meanings; every future reference must
disambiguate (Recursive System Design = the discipline; Risk-Surface-Dependency = the
`pipeline_fill` scorer). The naming choice is justified by the operator's claim that
recursion holds on every axis of the discipline (problems decompose; the system
regenerates its own codebase; new FSM control subgraphs enter via gates; distillation
improves its own fission/build models; the dreamer composes new workflows). Risk:
readers conflating the scorer and the discipline — mitigated by always writing the full
name at first use.

## Derived From

`docs/plans/2026-07-06-recursive-contract-bisection-micro-factories.md` §9.A ("Naming
— operator fiat, 2026-07-06"), reconciled against §5 ("Relation to RSD") and the §8
"Reconciliation note" that preserves the scorer's separate identity.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source decision is
an explicit operator fiat recorded in-session, presented as overriding the prior
synthesis ruling.
