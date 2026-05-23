---
type: adr
status: accepted
date: 2026-04-23
title: "ADR-0002: Data Verification Node Invocation Policy"
adr_id: ADR-0002
topics: [data-verification, dod, kafka, receipts, evidence-gates]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0002: Data Verification Node Invocation Policy

## Context

The `node_data_verification` node has a working runtime adapter — the node runs end-to-end against a real database, the six deterministic checks (`NO_GARBAGE_UUIDS`, `NO_NULL_REQUIRED_FIELDS`, `NO_DUPLICATES`, `ROW_COUNT_NONZERO`, `SCHEMA_MATCH`, `EVENT_LANDED`) pass golden-chain tests, and real-database execution was proven through integration verification. What did not exist was a deterministic contract describing how DoD gates call the node. Four questions were open:

1. How does `dod_verify` invoke `node_data_verification` — skill wrapper, Kafka event, or both?
2. How are target tables selected per ticket — explicit list, PR-diff inference, or contract-declared?
3. How is `rendered_output` evidence represented — what is the receipt format?
4. What does a verification failure block — Done status, PR merge, or both?

Without single canonical answers, `dod_verify` cannot call `node_data_verification` consistently, and receipts written by different callers cannot be compared. This ADR locks the answers against the node's contract definition.

## Decision

### 1. Invocation Mode — Kafka command topic is canonical; local CLI is the fallback

`dod_verify` invokes `node_data_verification` by publishing a `ModelDataVerificationStartCommand` envelope onto the command topic declared in the node contract. The completion topic carries the terminal event.

The Kafka path is canonical because:
- It is the only path available when `dod_verify` runs inside the runtime container (no filesystem access to local CLI tools, no authority to shell out).
- It is the only path that produces a verifiable event trail that the runtime sweep can audit.

Local CLI invocation (`uv run onex run node_data_verification -- --table-name ... --correlation-id ...`) remains supported as a debugging and CI fallback for environments without Kafka reachability. Local invocation **must** emit an equivalent `ModelDataVerificationCompletedEvent` through an in-memory event bus and **must not** be used to satisfy a DoD receipt for a real ticket — receipts are only valid when sourced from the Kafka terminal event.

**Rejected:** a dedicated HTTP endpoint on the runtime. Rejected because it would duplicate the command-topic surface and would not be auditable via the existing event log.

### 2. Table Selection — Contract-declared with explicit override

Per-ticket table selection reads from the ticket's `dod_evidence` list, specifically `rendered_output` evidence items whose verification method is `data_verification`. Each such item declares the target table and verification parameters.

`dod_verify` reads the evidence list, filters to `data_verification` items, and publishes one command per item. No PR-diff inference. No wildcard expansion. If a ticket's tables are not listed in `dod_evidence`, `dod_verify` does not guess — the ticket either does not require data verification, or it is misconfigured and must be fixed at the contract level.

**Rejected:** PR-diff inference. The mapping from diff to affected tables is ambiguous and the inference step would itself need verification. Contract declaration is explicit, auditable, and diffable.

**Rejected:** per-repo allowlist file. The source of truth would drift away from the ticket that describes the work.

### 3. Receipt Format — Structured JSON serialization of the terminal event

The `rendered_output` evidence receipt is a structured JSON document written by `dod_verify` after it consumes the terminal event:

```json
{
  "evidence_type": "rendered_output",
  "verification_method": "data_verification",
  "ticket_id": "<ticket identifier>",
  "correlation_id": "<uuid from start command>",
  "table_name": "<fully-qualified table name from contract inputs>",
  "verification_status": "pass | fail | partial | timeout",
  "total_rows": "<int>",
  "issues": ["<issue strings from verification result>"],
  "event_landed": "<bool>",
  "started_at": "<ISO-8601>",
  "completed_at": "<ISO-8601>",
  "source_event_topic": "<completion topic from contract>",
  "source_event_offset": "<int>"
}
```

Fields map directly to the `ModelDataVerificationCompletedEvent` model. Status vocabulary is fixed by the `EnumVerificationStatus` enum.

Receipts are stored under the existing receipts surface used for other `rendered_output` types. `dod_verify` does not invent a new storage mechanism.

**Rejected:** free-form markdown summary. Receipts must be machine-readable to be gated on.

### 4. Blocking Semantics — Failures block Done; PR merge is not gated

A failed `node_data_verification` run blocks **Done** on the Linear ticket via the DoD completion guard. It does **not** block PR merge.

Rationale:
- Verification runs against real database state. Many verification targets only exist **after** the PR merges and the runtime redeploys (projection tables populate from live events). Gating merge on a table that does not exist yet would deadlock the release.
- Merge-time gating is already covered by CI (unit tests, golden-chain tests, contract sweep). Data verification is the post-deploy confirmation that the merged change produced correct rows.
- Done gate enforcement already exists as a hard-mode check in the change control layer. Adding data verification as an evidence type fits that surface without new plumbing.

A `fail` terminal status writes a failing receipt; the Done guard reads receipt status and refuses to mark the ticket Done. A `partial` or `timeout` status is treated as `fail` for gating purposes and produces an explicit `retry_required` flag on the receipt.

**Rejected:** block PR merge on verification failure. Rejected for the deadlock reason above and because pre-merge verification against post-merge schema is logically impossible.

**Rejected:** block neither (advisory only). Advisory checks do not get adopted. Detection without enforcement is the status quo this work was filed to replace.

## Alternatives Considered

See the individual rejected paths documented under each decision point above.

## Consequences

**Immediate:**
- `dod_verify` can begin publishing start commands as soon as the runtime wiring lands. No further policy work required.
- Tickets whose Done gates need data verification must add `rendered_output` evidence items with `verification_method: data_verification` and the required input fields. Missing evidence means no verification fires — which is correct, because the ticket author is the only party who knows which tables matter.
- Tickets that merge without declaring verification evidence cannot retroactively have verification enforced.

**Deferred to follow-on work:**
- A pipeline-touching PR classifier that fires verification when the ticket contract did not declare it and the diff touches pipeline code paths.
- Runtime wiring for the Kafka publisher path in `dod_verify`.
- Additive field on the DoD evidence model for `verification_method` vocabulary.

## Related Doctrine

- Deterministic truth doctrine: truth is proven through event logs, materialized projections, and deterministic replay — not advisory sweeps.

## Derived From

Post-pipeline data validation gate design, as part of the runtime activation and infrastructure observability effort.

## Evidence

End-to-end node execution verified against a real database with all six deterministic checks passing.

## Supersedes

## Superseded By
