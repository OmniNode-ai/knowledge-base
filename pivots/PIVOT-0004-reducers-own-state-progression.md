---
type: pivot
status: accepted
date: "2026-05-23"
title: "Reducers Own State Progression"
observed_date: "2026-01-28"
confidence: high
topics: [reducers, state, ordering, replay, last-write-wins, projection]
refs:
  - doctrine/reducers-define-state-progression.md
  - doctrine/ordering-must-be-explicit.md
  - doctrine/canonical-reducers-win.md
  - doctrine/deterministic-under-replay.md
  - doctrine/state-is-materialized-projection.md
---

# PIVOT-0004: Reducers Own State Progression

## Original Assumption

State could be derived from the most recent event, where "most recent" meant the event that arrived last or was produced most recently by wall-clock time. The system's implicit contract was that newer events supersede older events, and "newer" was defined by arrival order at the consumer or by the timestamp embedded in the event payload.

This model treated state derivation as a simple problem: take the stream of events, sort by some notion of recency, and the last entry is the current state. For simple scalar values, this felt correct — if an entity's status changes from A to B, the most recent event wins, and the status is B.

The assumption extended to aggregate values. When multiple events contributed to a count, total, or aggregate, the aggregate was computed by processing events in the order they arrived and applying whatever arithmetic made sense locally. Conflict resolution, when it was considered at all, was handled ad hoc by the component that happened to process the conflicting events.

## Pressure Encountered

The model broke down when the system encountered events that arrived out of order. Network partitions, consumer restarts, and partition rebalancing all produced scenarios where events were delivered to a consumer in an order different from the order in which they were produced.

The first category of failure was silent data corruption. An entity whose state had transitioned A → B → C would be left in state A if an older event (A) was delivered after the two newer events (B, C) and the consumer had no mechanism for rejecting out-of-order events. The "latest wins" assumption silently accepted the stale event.

The second category was non-reproducible aggregate values. Counts, totals, and aggregates that were computed by applying arithmetic to events in arrival order would produce different results on different runs if arrival order varied. Running the same event sequence twice could produce different totals if delivery order differed.

The third category was more subtle: UI sort order affecting truth. In the absence of explicit reducer semantics, the component that displayed events often made the conflict resolution decision implicitly. A table sorted by timestamp would "resolve" a conflict in one direction; sorted by arrival time it would resolve differently. The display layer was determining business truth.

The fourth category was "first write wins" by accident. When a reducer was not defined and events were processed in arrival order, the first event to arrive would set the initial state, and subsequent events — including updates — would be silently lost if the projection checked "already exists, skip" rather than "apply the defined transition."

## Failure Modes Observed

**Out-of-order event acceptance.** A stale event (lower sequence number) arriving after a fresh event caused the projection to overwrite the fresh state with the stale value. No error was raised. The corruption was detectable only by comparing the projection value to the event log.

**Arrival-order-dependent aggregates.** Aggregate projections that summed, counted, or accumulated values produced different totals on replay than on original ingestion because replay delivery order differed from ingestion delivery order, and the accumulation logic was sensitive to order.

**Undefined conflict semantics.** When two events modified the same entity concurrently, the outcome depended on which consumer processed which event first. The result was non-deterministic and varied across deployments, consumer instances, and restart scenarios.

**Display layer acting as arbiter.** Sorting, filtering, and display logic that happened to process events in a particular order was effectively making state transition decisions. Changing sort direction changed system truth, which is not the dashboard's role.

**Implicit "first write wins" in upsert patterns.** Projection handlers that checked for existing state before inserting would silently discard updates if the insert check succeeded (row exists) but the defined transition (update to newer value) was not explicitly implemented.

## Pivot

State progression is defined by the projection's declared reducer contract. Arrival order, wall-clock time, and UI sort order do not define state progression. The reducer does.

**Every projection must declare its ordering contract.** "Latest wins" is a valid reducer — but it is valid only when the projection explicitly declares last-write-wins semantics using a monotonic sequence value, not by relying on arrival order. A projection that does not declare its ordering contract does not have a valid reducer.

**Canonical ordering uses ingest-assigned sequence.** The ordering authority for events is the ingest-assigned sequence number, not event timestamps or arrival times. Event timestamps may be used only when their clock authority is explicitly defined by the contract; they must not be assumed to represent a globally comparable ordering.

**Out-of-order events must be handled explicitly.** The reducer must specify what happens when a lower-sequence event arrives after a higher-sequence event has already been processed. The valid options are: ignore it, quarantine it, treat it as a no-op, or explicitly reject it. Silently accepting it and overwriting newer state is not a valid option.

**Undefined conflict behavior is a system defect.** If a projection can reach different states by processing the same events in different orders, the projection is incorrect. This is not a race condition to be tolerated; it is a design defect to be corrected by defining reducer semantics.

## New Model

Every projection has a reducer contract that consists of:

1. **Ordering authority**: which field defines canonical sequence (ingest-assigned sequence number, explicit version counter, or another contracted monotonic value)

2. **Conflict semantics**: what happens when two events claim to update the same entity — last-write-wins by sequence, FSM transitions, idempotent merges, or explicit rejection

3. **Out-of-order handling**: what happens when an event arrives with a sequence number lower than the last-processed sequence for that entity — ignore, quarantine, or reject; never silently apply

4. **Terminal state semantics**: for lifecycle projections, what events are valid after a terminal state is reached

These four elements are defined in the projection's contract, not inferred from the code that happens to process the events. When a new event type is added, the reducer contract is updated before the event handler is written.

Replay correctness follows from the reducer contract: if the same event sequence is processed by the same reducer contract version, the output must be identical regardless of which machine processed it, when it was processed, or in what order events were delivered within the contracted sequencing.

## Preserved Invariants

- The event log remains the source of record. The reducer contract determines how to interpret it, but the log itself is not modified.
- Idempotency at the event level. The same event processed twice must produce the same result as processing it once.
- Contract versioning. When reducer semantics change, the contract version changes. Old events are processed by the reducer version that was active when they were produced.

## Doctrine Impact

This pivot directly shaped three doctrine articles:

The `reducers-define-state-progression` doctrine establishes that state progression is defined by the projection's reducer contract, that out-of-order events must be handled according to contract and must never silently corrupt state, and that valid handling options are: ignored, quarantined, treated as no-op, or explicitly rejected.

The `ordering-must-be-explicit` doctrine establishes that every projection must declare its ordering contract, that canonical ordering must be based on ingest-assigned sequence or another explicitly contracted monotonic value, and that event timestamps may be used only when their clock authority is explicitly defined.

The `canonical-reducers-win` doctrine addresses the "latest wins" fallacy directly: last-write-wins is valid only when the projection contract explicitly defines it. The system must never allow first-write-wins by accident, arrival order to determine truth, or UI sort order to determine truth.

## Related ADRs

None of the current ADRs address the reducer contract pattern directly, but the registration boundary ADRs demonstrate its application: the registration orchestrator's contract explicitly defines which lifecycle facts represent valid state transitions and which ordering authority governs their sequence.

## Related Deep Dives

The pressure that made this pivot necessary was observed first in aggregate projection discrepancies, where replay runs produced different totals than original ingestion runs. The root cause in every investigated case was a reducer that relied on arrival order rather than declared sequencing semantics.

## Evidence

The structural change that proved the model: projections that had arrival-order-dependent aggregates were migrated to explicit reducer contracts with declared ordering authorities. After migration, replay runs became deterministic — the same event sequence produced identical totals regardless of delivery order. Projections that had not been migrated continued to show replay variance.

The secondary evidence was test stability: tests that replayed event sequences against explicit reducer contracts became reproducible. Tests that replayed event sequences against implicit arrival-order reducers remained intermittently flaky.

## Consequences

**Positive:**
- Replay correctness became verifiable through contract inspection, not runtime observation
- State corruption from out-of-order events became detectable and rejectable rather than silent
- Projections gained a formal specification that could be used for both testing and verification
- The "UI sort order affecting truth" failure mode was eliminated by confining state decisions to the backend reducer

**Negative / tensions:**
- Every projection must now have a declared ordering contract, which is additional upfront specification work before a handler can be written
- Reducer contracts must be versioned alongside event schemas. A change to reducer semantics requires a version bump, not just a code change.
- Out-of-order handling must be explicitly implemented for every projection. There is no universal default behavior; the correct handling is specific to the projection's domain semantics.
- Historical projections that were built without explicit reducer contracts must be audited and migrated. During migration, they may produce incorrect state.
