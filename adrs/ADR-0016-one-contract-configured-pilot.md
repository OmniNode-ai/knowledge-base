---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy"
adr_id: ADR-0016
topics: [steel-onslaught, pilot, contracts, archetypes, rule-7a]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy

## Context

Steel Onslaught must support two first-class modes: `LLM vs LLM` (spectate) and
`Human vs LLM` (play). Human-vs-LLM is not greenfield — `HumanPilot`/`BrowserHumanPilot`
classes and the SO-0012 / JON-19 live browser lane already exist. The natural but wrong
instinct is to model each seat type as its own subclass (`HumanPilot`,
`BrowserHumanPilot`, `LLMPilot`). CLAUDE.md rule 7a (the canonical architecture is exactly
three primitives — CONTRACT, NODE, HANDLER — with no bespoke per-variant classes) and the
naming conventions (`Model`-prefix, frozen Pydantic, `StrEnum` for finite sets) forbid a
per-variant class hierarchy.

## Decision

There is a **single pilot model**, not a class hierarchy. A pilot is **`ModelPilot`
(a pilot contract)** whose behavior is **configuration**: `kind: EnumPilotKind`
(`llm | human`), `model_ref` (which local model pilots this seat), `persona_ref`, and
`input_source` (for `human`: browser/WS seat). The runtime resolves a decision from that
config — a live local-LLM inference call for `kind=llm`, or await-external-input for
`kind=human` — behind ONE `ProtocolMessageHandler`/pilot surface. It is contract-backed
like everything else (contract YAML declares the pilot config; no free-form Python
config). This collapses the human/LLM seat distinction into data, so `Human vs LLM` mode
is simply a match contract with one `kind=human` seat and one `kind=llm` seat.

**Honest nuance:** the *config model* is one, but the decision-resolution still branches
on `kind` inside the handler (sync LLM call vs await human input) — that branch lives in
the handler/runtime, NOT in subclassed models.

## Alternatives Considered

1. `HumanPilot` / `BrowserHumanPilot` / `LLMPilot` class hierarchy. Rejected: violates rule 7a (no bespoke per-variant classes) and the naming conventions; multiplies bespoke lifecycles instead of collapsing to data.
2. Free-form Python config for pilot behavior. Rejected: everything is contract-backed; the pilot config is declared in contract YAML.
3. Leave Human-vs-LLM as a buried `?`-flag path. Rejected: the redesign must make it a selectable mode in the control surface (paired with the mode-toggle UI), not a hidden flag.

## Consequences

Positive: one pilot surface, behavior selected by data; adding a mode is a contract
change, not a new class; consistent with the three-primitive architecture. Negative /
sequencing: collapsing the existing `HumanPilot`/`BrowserHumanPilot` hierarchy into
`ModelPilot` + `EnumPilotKind` + contract is its own typed refactor that touches the same
pilot seat as the B0 move-verb work (SO-LOCAL-35) — read `src/steel_onslaught/llm/pilot.py`
and the HumanPilot/BrowserHumanPilot code first and sequence the two changes so they do not
collide. The `kind`-branch in the handler is an accepted, explicitly-documented seam (not a
model subclass).

## Derived From

`docs/plans/2026-07-06-steel-onslaught-redesign-plan.md` §0 ("ARCHITECTURE INVARIANT —
ONE `Pilot`, contract-configured (operator, 2026-07-06)"), cross-referenced to CLAUDE.md
rule 7a (three primitives, no `Plugin*`/bespoke base classes) and the naming conventions.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is an explicit
operator architecture invariant recorded in-session; the existing hierarchy
(`HumanPilot`/`BrowserHumanPilot`) and the collision with B0's `pilot.py` work are
file-grounded in §0/§1.

## Related Doctrine

- CLAUDE.md rule 7a — CONTRACT/NODE/HANDLER only; no bespoke per-variant classes.
