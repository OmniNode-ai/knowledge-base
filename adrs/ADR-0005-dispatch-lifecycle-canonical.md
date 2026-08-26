---
type: adr
status: accepted
date: "2026-04-28"
title: "ADR-0005: Dispatch Lifecycle Canonical Source"
adr_id: ADR-0005
topics: [dispatch, lifecycle, fsm, event-bus, canonical-model]
refs:
  - doctrine/truth-must-be-proven.md
  - doctrine/canonical-reducers-win.md
  - doctrine/deterministic-under-replay.md
  - doctrine/evidence-is-first-class-output.md
supersedes: []
superseded_by: []
---

# ADR-0005: Dispatch Lifecycle Canonical Source

## Context

Two concurrent plans introduced overlapping abstractions for the same dispatch lifecycle:

**Typed FSM events** (`ModelDispatchLifecycleEvent`) — a typed finite state machine with states `accepted / started / heartbeat / terminal_success / terminal_failure / timeout / cancelled / dlq`. Already implemented in the core models layer.

**Filesystem YAML records** (`ModelDispatchRecord`) — YAML written to a local state directory at dispatch time by a dispatch record writer handler.

Without a canonical owner, both abstractions could independently drift. Different work streams could claim lifecycle correctness against different surfaces, making it impossible to verify lifecycle guarantees across the system. This ADR closes that ambiguity.

## Decision

**Typed FSM events are canonical.**

`ModelDispatchLifecycleEvent` in the core models layer is the authoritative representation of dispatch lifecycle state and transition semantics. This ADR ratifies the existing model home rather than proposing a relocation.

Filesystem YAML records (`ModelDispatchRecord`) are compatibility projections — derived views written from terminal FSM events, not the authoritative source.

### Emitter responsibility table

| State | Emitter | Required fields |
|---|---|---|
| `accepted` | DISPATCHER | `dispatched_at`, `command_topic`, `target_node_id` |
| `started` | CONSUMER | `started_at`, `consumer_group`, `consumer_host` |
| `heartbeat` | CONSUMER | `heartbeat_at`, `consumer_host` |
| `terminal_success` | CONSUMER | `terminated_at`, `terminal_event_topic`, `result_payload_hash` |
| `terminal_failure` | CONSUMER | `terminated_at`, `terminal_event_topic`, `failure_reason` |
| `timeout` | ORCHESTRATOR | `timed_out_at`, `budget_seconds`, `last_observed_state` |
| `cancelled` | ORCHESTRATOR | `cancelled_at`, `cancel_reason`, `cancelled_by` |
| `dlq` | DLQ_WRITER | `dlq_at`, `dlq_topic`, `retry_attempts_used`, `final_failure_reason` |

Emitter ownership and required fields are enforced by validators at construction time, preventing dispatchers from self-reporting terminal success.

## Alternatives Considered

1. **YAML as canonical** — Rejected: local file records are too easy to self-attest and cannot carry the typed emitter-ownership constraints that prevent dispatchers from self-reporting terminal success. No verifiable event trail.

2. **Second canonical home outside the core models layer** — Rejected: adds indirection without solving ownership. The typed FSM model already exists in the correct layer; ratifying the existing location is the zero-cost path.

3. **Co-equal YAML and typed events** — Rejected: leaves the same lifecycle open to inconsistent claims across work streams and repositories — the failure mode this ADR exists to prevent.

## Consequences

1. **Skills-to-market work** must treat `ModelDispatchRecord` as a projection of `terminal_success` / `terminal_failure` FSM events, not as a standalone source of truth.

2. **Runtime lifecycle work** must add a task requiring that skill workers emit `ModelDispatchLifecycleEvent` events on the canonical event bus.

3. **Name collision** — a separate model named `ModelDispatchRecord` exists in the build-loop history handler with a different schema (build-loop history, not per-dispatch snapshot). It should be renamed to `ModelBuildDispatchRecord` in a separate follow-up. Do not bundle into this ADR.

4. **The compatibility layer** may hold compatibility projection record types and projection writer surfaces only; it must not redefine lifecycle state semantics.

5. **Proof-of-lifecycle claims** in PR bodies, receipts, and DoD evidence must cite a `ModelDispatchLifecycleEvent` chain observable on the bus, not a local YAML file.

## Related Doctrine

- Deterministic truth doctrine: truth is proven through event logs and deterministic replay — not local file writes that can be self-attested.

## Derived From

Architectural seam review (SEAM-9) surfacing ambiguity between two concurrent plans covering the same dispatch lifecycle surface.

## Evidence

Typed FSM model with emitter-ownership validators already implemented and passing; filesystem YAML path confirmed as lacking equivalent ownership guarantees.

## Supersedes

## Superseded By
