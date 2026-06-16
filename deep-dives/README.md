# Deep Dives

Deep dives are the narrative and discovery layer of the knowledge base. They capture what happened during significant work periods — not just what was built, but what was discovered, what assumptions failed, and how understanding evolved.

## What Makes a Good Deep Dive

Deep dives explain *why* understanding changed. They are not changelogs or status reports. A good deep dive captures:

- **Architectural pressure** — what became difficult or unstable
- **Discoveries** — new understanding that emerged from the work
- **Decisions forced** — choices made under pressure, with reasoning
- **Failed assumptions** — beliefs that proved wrong and what replaced them

## Relationship to Other Artifacts

Deep dives are the raw material from which other artifacts emerge:

- **Candidate ADRs** — decisions identified during deep dives become formal ADRs
- **Candidate Pivots** — recurring pressure patterns surface system-model shifts
- **Doctrine validation** — deep dives test whether current doctrine holds under operational pressure
- **Evidence** — deep dives reference the PRs, CI runs, and runtime findings that prove their claims

## Curated Deep Dives

| Date | Title | Key Topics |
|------|-------|------------|
| [2026-02-04](2026-02-04-zero-code-runtime-contract-driven-autowiring.md) | Zero-Code Runtime: Contract-Driven Handler Discovery and Dependency Injection | runtime, contracts, dependency-injection, plugin-architecture, auto-wiring |
| [2026-02-18](2026-02-18-dashboard-mock-to-live-authority-shift.md) | Dashboard Authority Shift: From Mock Data to Projection-Driven Truth | observability, dashboard, projections, event-sourcing, data-authority |
| [2026-02-27](2026-02-27-kafka-connection-limit-outage.md) | Kafka Connection Limit Outage: TCP Socket Leak Under Reconnect Storms | kafka, resilience, event-bus, connection-management |
| [2026-03-28](2026-03-28-multi-session-coordination-stack.md) | Multi-Session Coordination: Building the Session Intelligence Stack End-to-End | session-management, knowledge-graph, embeddings, multi-agent, coordination |
| [2026-04-14](2026-04-14-silent-projection-failure-autowiring-gap.md) | Silent Projection Failure: The Auto-Wiring Engine's Database Injection Gap | projections, auto-wiring, dependency-injection, observability, silent-failures |
| [2026-04-20](2026-04-20-autonomous-operations-three-simultaneous-failures.md) | Autonomous Operations Under Three Simultaneous Infrastructure Failures | autonomous-agents, infrastructure-resilience, measurement-discipline, failure-modes |
| [2026-05-30](2026-05-30-public-ci-validation-architecture.md) | Public CI and Validation Architecture | ci, validation, governance, release-gates, evidence-systems, replay-correctness |

## Cross-References to Doctrine

Each deep dive is grounded in one or more doctrine files. The table below shows which doctrine principles each deep dive tests or validates.

| Deep Dive | Doctrine Cross-References |
|-----------|--------------------------|
| [Zero-Code Runtime](2026-02-04-zero-code-runtime-contract-driven-autowiring.md) | [contracts-define-reality](../doctrine/contracts-define-reality.md), [ingestion-and-interpretation-separate](../doctrine/ingestion-and-interpretation-separate.md) |
| [Dashboard Authority Shift](2026-02-18-dashboard-mock-to-live-authority-shift.md) | [state-is-materialized-projection](../doctrine/state-is-materialized-projection.md), [authoritative-projections-own-truth](../doctrine/authoritative-projections-own-truth.md) |
| [Kafka Connection Limit Outage](2026-02-27-kafka-connection-limit-outage.md) | [fail-fast-and-loud](../doctrine/fail-fast-and-loud.md), [degrade-safely](../doctrine/degrade-safely.md) |
| [Multi-Session Coordination](2026-03-28-multi-session-coordination-stack.md) | [state-is-materialized-projection](../doctrine/state-is-materialized-projection.md), [contracts-define-reality](../doctrine/contracts-define-reality.md) |
| [Silent Projection Failure](2026-04-14-silent-projection-failure-autowiring-gap.md) | [fail-fast-and-loud](../doctrine/fail-fast-and-loud.md), [truth-must-be-proven](../doctrine/truth-must-be-proven.md), [authoritative-projections-own-truth](../doctrine/authoritative-projections-own-truth.md) |
| [Autonomous Operations](2026-04-20-autonomous-operations-three-simultaneous-failures.md) | [truth-must-be-proven](../doctrine/truth-must-be-proven.md), [evidence-is-first-class-output](../doctrine/evidence-is-first-class-output.md), [deterministic-under-replay](../doctrine/deterministic-under-replay.md) |
| [Public CI and Validation Architecture](2026-05-30-public-ci-validation-architecture.md) | [truth-must-be-proven](../doctrine/truth-must-be-proven.md), [evidence-is-first-class-output](../doctrine/evidence-is-first-class-output.md), [contracts-define-reality](../doctrine/contracts-define-reality.md), [fail-fast-and-loud](../doctrine/fail-fast-and-loud.md), [deterministic-under-replay](../doctrine/deterministic-under-replay.md) |
