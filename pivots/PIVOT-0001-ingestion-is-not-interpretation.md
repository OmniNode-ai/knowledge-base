---
type: pivot
status: accepted
date: "2026-05-23"
title: "Ingestion Is Not Interpretation"
observed_date: "2026-01-15"
confidence: high
topics: [event-streaming, projection, ingestion, nondeterminism, replay]
refs:
  - doctrine/ingestion-and-interpretation-separate.md
  - doctrine/deterministic-under-replay.md
  - doctrine/state-is-materialized-projection.md
  - adrs/ADR-0002-data-verification-invocation.md
---

# PIVOT-0001: Ingestion Is Not Interpretation

## Original Assumption

Event consumers could safely handle the full pipeline — receive an event, apply projection logic, and update state — in a single pass. The boundary between "receiving an event" and "deciding what that event means for system state" was considered an implementation detail, not an architectural invariant.

Handlers that processed incoming events were expected to be self-contained: they would validate the payload, apply whatever reducer semantics were needed, and emit a result. Ingestion and interpretation were the same operation, distinguished only by where they happened to be located in the code.

## Pressure Encountered

As more consumer instances were deployed and as event replay scenarios became more common during development and debugging, a pattern emerged: the same event sequence produced different system state depending on which consumer instance processed which events, in what order, and at what time.

The coupling became visible when:

- A replay run produced different aggregate counts than the original ingestion
- Two consumer instances reading from different partition offsets converged on different totals for the same entity
- State observed immediately after ingestion differed from state observed after a restart and replay, even when the event log was identical
- Bugs were discovered that depended on the exact sequence in which events were processed at a specific consumer, not on any property of the events themselves

Each of these failures traced to the same root: the consumer was not just delivering events. It was also applying sequencing assumptions, deduplication heuristics, and stateful accumulation — all mixed into the transport layer.

## Failure Modes Observed

**Non-deterministic replay.** Running the same event sequence through two consumer instances produced different projected state because each instance tracked its own accumulator, cursor, or deduplication window. Replay correctness depended on which consumer had processed which events before the replay began.

**Stateful transport side effects.** Consumer-side state that was modified during ingestion persisted across restarts. A fresh consumer that had never seen a given entity would produce different state than a consumer that had previously processed events for that entity and maintained in-memory accumulation.

**Reducer semantics scattered across boundaries.** When business logic about what constitutes a "valid transition" or "superseding event" was embedded in consumers, that logic had to be replicated in every consumer that touched the same entity type. Divergences accumulated silently — two consumers would accept different transitions as valid, depending on which developer had added the consumer.

**Verification opacity.** Because state was being constructed inside the transport layer, there was no single auditable place to verify that a given event sequence had been correctly reduced. Tests that verified individual events passed, while tests that verified aggregate state over sequences failed intermittently.

## Pivot

Transport (ingestion) and state logic (interpretation) must be strictly separated. This is not a recommendation about code organization; it is a hard architectural boundary with different rules on each side.

**The consumer's authority is bounded to delivery.** A consumer may validate envelope integrity, check schema compatibility, route malformed messages to dead-letter, and deliver events to downstream handlers. A consumer must not accumulate state, apply reducer semantics, or make decisions about what an event means for the projected state of any entity.

**Interpretation belongs to projection services.** Projection services receive delivered events, sequence them using an explicit ordering contract, apply reducers defined by that contract, and materialize state. The projection service owns the cursor, the reducer, and the output shape. No other component shares those responsibilities.

**Mixing the two layers creates nondeterminism.** Any code path where a consumer modifies accumulated state as part of delivery — even incidentally — creates replay variance. The constraint is not "prefer to separate them" but "mixing them is incorrect."

## New Model

The pipeline has two distinct phases with different authority:

**Phase 1 — Ingestion (consumer authority):**
- Validate envelope structure and schema compatibility
- Reject or quarantine malformed messages
- Deduplicate by message identity where the contract explicitly defines identity-based deduplication
- Deliver to the downstream projection service

The consumer is stateless with respect to entity state. It does not know what a given event means for any projection. It only knows whether the envelope is valid and where to route it.

**Phase 2 — Interpretation (projection service authority):**
- Receive delivered events
- Assign or validate sequence position using the declared ordering contract
- Apply the projection's reducer to determine valid state transitions
- Materialize the new state
- Advance the cursor

The projection service is the only component that knows what an event stream means. It owns the full sequencing and reduction logic, and its output is the authoritative state for that projection.

Replay is correct by construction when these phases are separated: running any event sequence through a stateless consumer into a fresh projection service must produce the same output regardless of prior history.

## Preserved Invariants

- The event log remains the source of record. This pivot does not change what gets recorded, only who is authorized to interpret it.
- Schema validation belongs at ingestion. Consumers remain responsible for structural integrity checks before delivery.
- Dead-lettering remains a consumer responsibility. Routing malformed events to dead-letter or quarantine queues happens before delivery and does not require projection knowledge.
- Projections remain append-derived. The separation does not require projections to abandon event-sourcing semantics; it only specifies where the reduction logic lives.

## Doctrine Impact

This pivot directly shaped the doctrine article on ingestion and interpretation separation. The doctrine states that consumers may validate envelopes, route malformed messages, and deliver events — and must not apply projection reducers or infer authoritative system state. Projection services sequence events, apply reducers, and materialize state.

The doctrine also reinforced the replay determinism invariant: a valid system guarantees that the same canonical input sequence through the same contract and reducer version always produces the same projected state. That guarantee is only achievable when interpretation is entirely confined to projection services, where it can be versioned and tested independently of transport.

The `state-is-materialized-projection` doctrine article captures the consequence: there is no hidden authoritative state. All state is explicitly constructed by a projection service from delivered events.

## Related ADRs

- `adrs/ADR-0002-data-verification-invocation.md` — the data verification pipeline separates the ingestion of verification commands from their interpretation, applying this same boundary

## Related Incident Analysis

The pressure that made this pivot necessary was first documented during investigations into inconsistent aggregate counts between consumer instances, and later reinforced when replay runs for debugging purposes produced different state than the original ingestion runs.

## Evidence

The clearest evidence was the contrast between two types of tests:

- Tests that verified individual event handling (pass rate: high, stable)
- Tests that verified aggregate state over replay sequences (pass rate: variable, dependent on execution order)

The second category of test failures could not be fixed by correcting individual event handlers. They required isolating all state accumulation into projection services and stripping it from consumers entirely. After that structural change, replay tests became deterministic.

## Consequences

**Positive:**
- Replay correctness became a mechanical property of the architecture, not a property that needed to be verified per-consumer
- Projection services became the single auditable location for all state logic, enabling contract-driven verification
- Consumer testing became straightforward: verify that valid envelopes are delivered, invalid envelopes are quarantined
- Projection testing became independent of transport: feed any event sequence to a fresh projection service and assert the output

**Negative / tensions:**
- The boundary requires discipline. Code that "just needs to track a count" in a consumer is tempting and incorrect. The architectural invariant must be enforced through code review and, eventually, static analysis.
- Projection services become the complexity sink. Moving all state logic out of consumers concentrates it in projection services, which must be tested more thoroughly and versioned more carefully.
- Operational changes: consumers that previously reported derived state for monitoring purposes needed to be updated to read from projections instead.
