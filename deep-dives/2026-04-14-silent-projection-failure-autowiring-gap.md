---
type: deep-dive
status: public-curated
date: 2026-04-14
title: "Silent Projection Failure: The Auto-Wiring Engine's Database Injection Gap"
period: "2026-04-10 to 2026-04-14"
topics:
  - projections
  - auto-wiring
  - dependency-injection
  - observability
  - silent-failures
refs:
  - adr/ADR-004-contract-first-definitions.md
  - adr/ADR-007-projection-authority.md
  - doctrine/03-no-silent-failures.md
---

# 2026-04-14: Silent Projection Failure — The Auto-Wiring Engine's Database Injection Gap

## Summary

For several days, the observability dashboard showed no node registrations despite the platform running and processing events normally. The root cause was not a data pipeline problem, a network issue, or a schema mismatch — it was a single missing injection in the auto-wiring engine. Projection handlers that needed database access were being instantiated and registered with the event bus, consuming events successfully, but their `handle()` method received an incompatible call signature that silently discarded every event without writing anything to the database. Zero errors were emitted. The fix was three lines; finding the root cause took days.

## Core Work

The ONEX platform's auto-wiring engine discovers handlers from installed node packages, instantiates them via dependency injection, and registers them with the event bus. At the time of the incident, the engine's dispatch callback construction had a subtle bug: it called `handler.handle(envelope)` — passing the raw Kafka event envelope. Projection handlers, which write to the database, expect `handle(input_data: dict)` with `_db` and `_event_type` injected by the engine.

The mismatch meant that every projection handler received an event envelope where it expected a dictionary, and the `_db` dependency was never injected. Handlers that tried to call `_db.write(...)` in their `handle()` implementation received an `AttributeError` internally, which the handler's error boundary caught and silently swallowed — returning normally while writing nothing.

The fix: the auto-wiring engine was updated to detect handlers that declared `db_io.db_tables` in their contract YAML, and for those handlers, to construct a dispatch callback that unpacks the envelope, injects the database adapter instance, and passes `_event_type` alongside the data. This detection-and-injection path was added as a three-layer test suite: a unit test for the injection logic, an integration test for the dispatch path, and an integration test for the database writes themselves.

## Architectural Pressure

**Kafka consumption and database persistence are independent observability surfaces.** Consumer group health metrics show whether events are being consumed. Database health metrics show whether tables are being written to. When a handler consumes events without writing to the database, both surfaces appear healthy. The gap between them — "events consumed, nothing written" — was not monitored.

**Error boundaries that silently succeed are worse than errors.** The handler's internal error boundary caught the `AttributeError` from the missing `_db` injection and returned a success status. This is a common defensive pattern, but it produced a false positive: the auto-wiring engine recorded the handler as dispatched and healthy. From the engine's perspective, the handler ran successfully. From the database's perspective, nothing happened.

**Contract YAML declared the dependency; the engine didn't read it.** The projection handlers had correctly declared `db_io.db_tables` in their contract YAML. The auto-wiring engine read this field for other purposes (topic routing, capability registration) but did not use it to determine whether to inject a database adapter. The contract contained the information needed to prevent the bug; the engine just wasn't looking at it.

**Visual verification gaps compound over time.** The dashboard showing zero node registrations was the first signal. But because the dashboard had previously shown mock data, the absence of real data was not immediately alarming — it looked like an unfilled mock state. Several days passed between the handler deployment and the decision to investigate the apparent absence of data. The lesson: mock data creates a visual baseline that makes real data absence harder to notice.

## Discoveries

**Silent event consumption without database writes requires its own health check.** The platform had consumer group lag monitoring (events are being consumed) and table health monitoring (tables exist and are not corrupted). It did not have cross-layer consistency monitoring (events consumed correlates with rows written). Adding a health check that detects consumer groups with activity but no corresponding table writes would have flagged the issue immediately.

**Contract YAML must be the engine's complete configuration source for injection.** The handler's contract declared the database dependency. The engine should have used that declaration to infer injection requirements. The root cause was that the engine read some contract fields (topics, capabilities) but not others (database dependencies). Making the engine read all contract fields for injection decisions, rather than having injection logic separately maintained, aligns with the contract-first principle.

**Three-layer testing for dispatch paths.** The fix was accompanied by tests at three layers: unit (injection logic), integration/dispatch (full auto-wiring cycle), and integration/database (actual write verification). Prior tests only covered the unit layer for similar components. The three-layer approach for any handler that writes to a database should be the standard.

**Deploy-agent hardening revealed a related pattern.** On the same day, the deployment agent was hardened with four fixes: container health verification (checking that containers are actually healthy before emitting completion signals), single-flight lock (preventing simultaneous deploys), authentication for trigger commands, and Kafka connectivity fixes. All four fixes share the same underlying pattern: previously, the deploy agent could report success while the actual work had not completed. The shared pattern — silent success that masks actual failure — suggests a systemic defensive posture: every handler that reports success must be verified against the side effect it was supposed to produce.

## Decisions Made

**The auto-wiring engine uses contract YAML exclusively to determine injection requirements.** Handlers that declare `db_io.db_tables` receive a database adapter injection. The injection detection is driven by contract field presence, not by handler type, class hierarchy, or registration metadata.

**Three-layer test coverage is required for any handler that writes to a database.** Unit tests verify the injection logic. Integration tests verify the dispatch path. Integration tests verify the database writes themselves. Missing any layer leaves a gap.

**Consumer-group-to-write correlation monitoring is added to platform health checks.** The platform health monitor tracks whether consumer groups that are expected to produce database writes are doing so. A consumer group with normal consumption metrics and zero write throughput triggers a health alert.

**Error boundaries must not convert errors to silent successes.** Handler error boundaries are allowed to catch exceptions and prevent them from propagating to the event bus. They are not allowed to return success status without logging the error. An error boundary that silences an exception must emit a structured error event before returning.

## Candidate ADRs

- Contract-driven injection: auto-wiring engine derives all injection requirements from contract YAML fields, not from separate configuration
- Three-layer test coverage requirement for projection handlers
- Error boundary contract: no silent success when an exception was caught

## Candidate Pivots

The root cause of this incident is not specific to projection handlers or to the database injection pattern. It represents a broader gap in the principle that "success means the side effect happened" rather than "success means the handler ran without crashing." Addressing this gap systematically — requiring every handler that declares a side effect to also declare a verification check — is a candidate platform pivot.

## Related Doctrine

- **Section 3 (No Silent Failures):** The handler's error boundary converted an injection failure into a silent success. This directly violates the doctrine that failures must be observable. The error boundary fix enforces this doctrine at the handler level.
- **Section 4 (Contract-First Definitions):** The contract contained the information needed to prevent the bug. The engine not reading that field was a violation of the principle that contracts are the authoritative specification. The fix restores alignment.

## Related Evidence

- Three-layer test suite: unit (212 lines), integration/dispatch (96 lines), integration/database (181 lines)
- Consumer group health monitoring: confirmed normal consumption throughput throughout the incident period
- Database table health check: confirmed zero rows in the affected tables during the incident period
- Post-fix verification: dashboard showed live node registrations within minutes of the patched engine deploying

## Open Questions

- Should the auto-wiring engine validate handler contract declarations against what the handler actually uses at runtime? Detecting a mismatch between "declared database dependency" and "no actual database calls made" could catch an entire class of bugs where the contract is correct but the implementation doesn't use what was declared.
- What is the correct scope for the consumer-group-to-write correlation monitoring? Every consumer group? Only groups declared in contracts as projection handlers?

## Follow-up Work

- Extend the boot-time invariant to include projection handler database access validation: if a handler declares `db_io.db_tables`, verify at startup that its `handle()` method will receive the database adapter
- Write a platform-level test that deploys a projection handler, publishes events, and asserts database writes occurred — testing the complete dispatch path, not just the handler in isolation
- Add consumer-group-to-write correlation to the runtime health monitor
