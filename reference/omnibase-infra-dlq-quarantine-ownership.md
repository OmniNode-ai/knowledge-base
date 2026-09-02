---
type: reference
status: current
date: "2026-09-02"
title: "DLQ Quarantine Ownership Semantics"
topics: [omnibase-infra, dlq, quarantine, ownership]
refs: []
---

<!-- Migrated from omnibase_infra:docs/operations/DLQ_QUARANTINE_OWNERSHIP.md on 2026-09-02. -->

# DLQ Quarantine Ownership Semantics

> Authoritative companion to the `quarantine:` block in
> `src/omnibase_infra/nodes/node_dlq_replay_effect/contract.yaml`.
> These semantics are **net-new** — no prior pattern existed.

## Why quarantine exists

The legacy manual replay CLI (`scripts/dlq_replay.py`) handled non-replayable
DLQ messages with a **skip-and-drop** path in its replay command flow. In the default
configuration (`--enable-tracking` off) those messages were not even recorded —
they were logged and lost. That is **silent message loss**.

`NodeDlqReplayEffect` replaces skip-and-drop with **quarantine**: every
non-replayable message is published durably to
`onex.dlq.omnibase-infra.quarantine.v1` and a terminal `QUARANTINED` row is
written to `dlq_replay_history`. A message is never dropped.

A message is non-replayable when `should_replay()` returns `False`:

- `retry_count >= max_replay_count` (exhausted retries), or
- `error_type` is in `EnumNonRetryableErrorCategory` (e.g. `ValidationError`,
  `ProtocolConfigurationError`), or
- it falls outside the active replay filter (topic / error-type / correlation /
  time-range).

## Quarantine topic

| Field | Value |
|-------|-------|
| Topic | `onex.dlq.omnibase-infra.quarantine.v1` (`TOPIC_DLQ_QUARANTINE`) |
| Producer | `NodeDlqReplayEffect` (`DLQQuarantineProducer`) |
| Key | original message `correlation_id` |
| Retention | long retention, MUST exceed replay-topic retention (default 90d) |

The quarantine payload carries the original payload plus the quarantine
decision: `quarantine_correlation_id`, `quarantined_at`, `reason`,
`original_topic`, `original_correlation_id`, `error_type`, `retry_count`, and the
`source_dlq_topic` / `source_dlq_offset` / `source_dlq_partition` coordinates
needed for re-entry.

## Ownership

| Owner | Role | Responsibility |
|-------|------|----------------|
| **Retention owner** | Platform infrastructure team | Owns the `onex.dlq.omnibase-infra.quarantine.v1` topic retention. Retention must exceed the replay topics so a message is never aged out before reclassification. |
| **Reclassification owner** | Team that owns the `original_topic` | Decides whether a quarantined message is genuinely terminal (discard after audit) or was misclassified (transient error mis-tagged non-retryable). Keyed by `original_correlation_id`. |
| **Replay-eligibility-change owner** | Original-topic team, with platform review | Owns changes to what counts as replay-eligible — edits to `EnumNonRetryableErrorCategory` or `max_replay_count`. These affect every DLQ consumer and require platform review. |

## Re-entry / replay path

A quarantined message re-enters replay **explicitly and owner-driven**. The node
never auto-promotes quarantined messages back into replay.

1. Audit the quarantine record (keyed by `original_correlation_id`).
2. Reclassify: confirm the message should be replayable now.
3. Republish `original_payload` to `source_dlq_topic` with `retry_count` reset
   below `max_replay_count` (and/or after the offending `error_type` is removed
   from `EnumNonRetryableErrorCategory`).
4. The persistent `onex-dlq-replay` consumer group picks it up; `should_replay()`
   decides afresh.

## Consumer group

The node consumes from the **persistent** consumer group `onex-dlq-replay`
(`DLQ_REPLAY_CONSUMER_GROUP`), set via `ONEX_GROUP_ID` on the
`dlq-replay-consumer` service. This replaces the legacy ephemeral
`dlq-replay-{pid}` group, which left no durable read position across runs.

## Evidence guarantees

- A replay publish failure is recorded as `FAILED` (never a false `COMPLETED`).
- A quarantine publish failure is recorded as `FAILED` (still durable — not a
  silent drop).
- Every terminal outcome (`COMPLETED`, `QUARANTINED`, `FAILED`) writes a row to
  `dlq_replay_history`.
