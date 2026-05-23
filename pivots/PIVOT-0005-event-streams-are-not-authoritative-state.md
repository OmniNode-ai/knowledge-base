---
type: pivot
status: accepted
date: "2026-05-23"
title: "Event Streams Are Not Authoritative State"
observed_date: "2026-01-10"
confidence: high
topics: [event-streaming, projections, authority, truth, materialization, raw-events]
refs:
  - doctrine/authoritative-projections-own-truth.md
  - doctrine/state-is-materialized-projection.md
  - doctrine/cursors-represent-projection-progress.md
  - doctrine/truth-must-be-proven.md
  - doctrine/ordering-must-be-explicit.md
---

# PIVOT-0005: Event Streams Are Not Authoritative State

## Original Assumption

The event stream is the system state. In an event-sourced system, the log of all events is the complete record of everything that happened, and the current state of any entity can be derived by reading the events in that entity's history. Under this assumption, reading "the latest events" for a given entity or topic is equivalent to reading the current state of that entity.

This assumption made the event stream feel like a natural API: want to know how many nodes are registered? Subscribe to the registration topic and count. Want to know the current status of a workflow? Read the last event on that workflow's partition. The stream was treated as a queryable store where the answer to any state question was the result of processing some subset of events.

The model was reinforced by the simplicity of early implementations. For bounded event sequences — a single workflow, a single entity with a known history — reading the stream and deriving state produced correct results. The assumption that this approach scaled to production traffic, multi-partition consumers, and concurrent updates went unexamined.

## Pressure Encountered

At low volume, reading the event stream to derive state appeared to work. At production volume, the approach accumulated failure modes faster than individual issues could be diagnosed.

The first pressure: duplicates in the stream. Event streams at production scale contain duplicates — events published more than once due to producer retries, at-least-once delivery semantics, and network conditions. A consumer that counted events to derive state would overcount. A consumer that took the "latest" event would encounter duplicate events with the same sequence position and have no way to determine which was the canonical copy.

The second pressure: out-of-order arrivals. Events did not arrive at consumers in the order they were produced. Consumer restarts, partition rebalancing, and Kafka's per-partition ordering guarantee (not cross-partition) meant that a consumer reading from multiple partitions would encounter events in a different order than the order in which they were produced.

The third pressure: malformed events from superseded versions. As schema versions evolved, old events in the log — or events produced by services that had not yet been updated — did not conform to current schemas. A consumer that read the stream to derive state had to decide how to handle events from older versions: skip them (potentially missing valid state updates), accept them (potentially applying semantically incorrect values), or fail (blocking progress on the entire stream).

The fourth pressure: partition-dependent views. Two services reading the same topic from different partition offsets derived different state. There was no single "current state" — there was only "the state as seen from this offset and these partitions." The view was a function of where in the stream each reader happened to be, not a function of the actual system state.

## Failure Modes Observed

**Inconsistent views across consumers.** Services that derived state by reading the same event stream showed different values depending on which partitions they had consumed, which offsets they had reached, and whether they had seen the duplicate events. The same topic subscription produced different answers to the same state question for different subscribers.

**Overcounting from duplicates.** Aggregate values computed by counting or summing events were inflated by producer retries and at-least-once delivery duplicates. The error was not visible unless the consumer had access to both the aggregate and the original event sequence, and had a way to identify which events were canonical.

**State derived from superseded events.** Old events in the log that were produced by earlier code versions sometimes contained values that were semantically incorrect under current semantics. A consumer that processed these events to derive current state would produce incorrect state, with no indication that the source events were stale.

**Race conditions in state derivation.** When two concurrent events modified the same entity and a consumer was deriving state by reading both, the outcome depended on which event the consumer happened to process last. Different consumers would process the same pair of events in different orders and derive different final states.

**Cursor as offset, not progress.** When consumers used Kafka offsets as their state-of-progress indicator, a restart from an old offset would re-derive all state from that point forward. This was not replay — it was re-derivation — and the result was state that mixed events from the historical re-derivation window with events from the live stream, with no boundary marker.

## Pivot

Event streams are input, not truth. Authoritative state exists only in materialized projections that have sequenced, reduced, and aggregated events through contracted logic.

**The raw event stream is not queryable for current state.** Reading the most recent events on a topic does not tell you the current state. It tells you the recent activity. Current state is what a projection service reports after processing the full event history through its defined reducer.

**Duplicates, out-of-order arrivals, and malformed events are not edge cases.** They are expected properties of production event streams. A system that assumes a clean, ordered, deduplicated stream will produce incorrect state under production conditions. The projection service is responsible for handling all three.

**Projections are the state API.** When any component needs to know the current state of any entity, it queries a projection. It does not read the event stream. It does not ask a consumer what events it has seen. It reads the value that the projection service has materialized from the full event history.

**The cursor represents projection progress, not stream position.** A projection's cursor is the maximum known truth boundary for that projection. It is not a Kafka offset. It is a monotonic value in the projection's own coordinate system, derived from the ingest-assigned sequence numbers that the projection has successfully processed and reduced. Advancing the cursor means the projection has incorporated all events up to that point and its materialized state reflects them.

## New Model

The event architecture has three distinct layers with different roles:

**Layer 1 — The event log:**
The append-only log of all events. Source of record. Not queryable for current state. May contain duplicates, out-of-order events, and events from superseded schema versions. Immutable.

**Layer 2 — Projection services:**
The services that consume the event log and materialize authoritative state. Each projection service:
- Subscribes to one or more topics
- Deduplicates events by message identity where the contract defines it
- Rejects or quarantines malformed events and events from incompatible versions
- Applies a declared ordering contract to sequence events
- Applies a declared reducer to determine valid state transitions
- Materializes the result into a queryable store
- Advances its cursor as events are successfully processed

The projection service transforms raw event stream input into authoritative state. It owns the deduplication, sequencing, and reduction. It exposes materialized state, not raw events.

**Layer 3 — Consumers:**
All other components that need state information — dashboards, APIs, downstream projections, other services — read from Layer 2 (projections). They never read from Layer 1 directly to derive current state.

The event log plus contracted inputs plus projections own truth. The raw stream does not.

## Preserved Invariants

- The event log remains immutable and append-only. No event is ever deleted or modified. The pivot is about who interprets the log, not about the log's contents.
- Replay is still possible. Rebuilding a projection by replaying the event log through the projection's reducer is a valid operation. This is how projections are bootstrapped and how they are verified. The pivot is about runtime state queries, not about replay semantics.
- Projection correctness is auditable. Because projections expose their cursor, the materialized state can be compared to the event log at any cursor position. This auditability is a property of the explicit projection model.

## Doctrine Impact

This pivot is foundational to the `authoritative-projections-own-truth` doctrine, which specifies that truth is owned by the event log, contracted inputs, and materialized projections — not by raw event streams. The doctrine prohibits clients from merging event streams into truth, inferring authoritative system state, or fabricating consistency.

The `state-is-materialized-projection` doctrine captures the construction principle: state must be explicitly constructed from source events through a projection that owns sequencing, reduction, aggregation, shape, and cursor semantics. There is no hidden authoritative state.

The `cursors-represent-projection-progress` doctrine addresses the cursor model: a cursor is not a stream offset. It is the maximum known truth boundary for the projection, monotonic within its scope, and derived from the projection's own progress through contracted sequencing — not from Kafka's partition offsets.

The `truth-must-be-proven` doctrine enforces the consequence: because truth is only established through materialized projections, a claim about system state is only valid when it cites a projection value, not when it cites raw stream observation.

## Related ADRs

- `adrs/ADR-0003-registration-runtime-registry-boundary.md` — establishes that registry projections (not runtime memory or raw event stream observation) are the canonical truth for node registration state
- `adrs/ADR-0004-registry-owned-consumer-surface.md` — names the specific projection surface that is canonical, explicitly rejecting runtime in-memory state and raw stream subscriptions as truth sources

## Related Deep Dives

The registration system provided the most sustained evidence for this pivot. The initial implementation used runtime in-memory state and raw event stream subscriptions to track node registration. Multiple consumers subscribed to the same topic and each maintained independent state. They diverged. The ADRs establishing the registry boundary were the direct product of applying this pivot's conclusion to the most visible broken case.

## Evidence

The most direct evidence: the platform registry after switching from stream-derived state to projection-backed state. Before: inconsistent counts between browser windows, stale entries persisting after expiry, counts that varied depending on when the page loaded. After: consistent counts backed by a single projection, expiry enforced by the projection's reducer contract, immediate consistency across all consumers reading the same projection surface.

The theoretical validation: projection correctness under replay. A projection that materializes state from the event log through a declared reducer can be verified by replaying the log. A stream-reading consumer that derives state from event arrival cannot be verified by replay because its state depends on arrival order, which varies.

## Consequences

**Positive:**
- State queries have a single authoritative answer: what does the projection say?
- Duplicate events, out-of-order events, and superseded-version events are handled once, in the projection service, not in every consumer
- Consistency across consumers is guaranteed: all consumers that read the same projection surface see the same state
- State verification through replay becomes possible: rebuild the projection from the log and compare

**Negative / tensions:**
- Every piece of system state that must be queried requires a corresponding projection. This is upfront infrastructure work that raw stream reading avoids.
- Projection lag is real. There is a gap between when an event is written to the log and when the projection has processed and materialized it. Systems that require zero-lag consistency must account for this.
- Projection coverage must be maintained. As new event types are added, the projections that depend on them must be updated. A projection that does not handle a new event type will produce incomplete state silently.
- The projection layer becomes a complexity concentration point. All the deduplication, sequencing, and reduction logic that was previously scattered across consumers must now be in the projection service, which must be tested and versioned rigorously.
