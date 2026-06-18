---
type: deep-dive
status: public-curated
date: "2026-02-18"
title: "Dashboard Authority Shift: From Mock Data to Projection-Driven Truth"
period: "2026-01-15 to 2026-02-18"
topics:
  - observability
  - dashboard
  - projections
  - event-sourcing
  - data-authority
refs:
  - doctrine/state-is-materialized-projection.md
  - doctrine/authoritative-projections-own-truth.md
  - doctrine/ingestion-and-interpretation-separate.md
  - adrs/ADR-0003-registration-runtime-registry-boundary.md
  - adrs/ADR-0004-registry-owned-consumer-surface.md
---

# 2026-02-18: Dashboard Authority Shift — From Mock Data to Projection-Driven Truth

## Summary

The platform's observability dashboard crossed a threshold that had been approached gradually over several weeks: every data source that had previously shown mock or demo data was replaced with live projections backed by real event streams. This transition was not merely a matter of wiring up data sources — it forced a clarification of the fundamental authority model. The dashboard is a renderer of materialized projections, not an independent data store. State flows in one direction: events are produced by handlers, consumed by projection workers, and materialized into read models that the dashboard reads. The dashboard never creates or owns state.

## Core Work

The live data transition involved work across three layers:

**Projection handlers.** For each category of dashboard data (LLM cost trends, pattern enforcement events, validation lifecycle, baselines), a dedicated projection handler was written that subscribes to the relevant Kafka topics and writes materialized rows into PostgreSQL read-model tables. Each projection handler owns a specific table schema and the transformation logic from event envelope to table row.

**Dashboard API layer.** The dashboard server exposes API endpoints that query the read-model tables directly. No business logic lives in the API layer — it is a thin translation from database rows to JSON responses. The API has no write surface.

**Client rendering.** The dashboard client fetches data from the API and renders it. Crucially, the client retains a mock-data fallback pattern: if the API returns an empty result set, the client renders a clearly-labeled demo state rather than an error. This pattern allowed pages to ship before their projection handlers were complete and made it easy to verify that real data was flowing by observing the demo badges disappear.

A secrets-management migration also landed the same day, removing 11,416 lines of legacy secrets-configuration code and consolidating secrets management on a single backend. This was architecturally unrelated to the dashboard transition but removed a significant operational dependency.

## Architectural Pressure

**Mock data creates a false sense of completeness.** For several weeks, dashboard pages showed realistic-looking data that was entirely fabricated. The pages were technically functional — routing, rendering, API calls all worked — but they communicated nothing about actual platform state. The gap between "page renders" and "page shows true data" was invisible in screenshots and demo recordings.

**Multiple read models competing for authority.** Before consolidation, some dashboard pages read from different tables than others. Some tables were populated by one code path and queried by a different API endpoint. Schema drift between write and read paths produced subtle inconsistencies: a field that the projection handler wrote as `cost_usd` might be queried as `cost` elsewhere, causing silent zero-cost results that looked like real data.

**CI architecture guard was missing.** Several pages had begun querying upstream database tables directly rather than through the read-model layer. This created hidden coupling between the dashboard and upstream schemas. When upstream tables changed, dashboard queries broke silently in production. The pattern was caught by manual review; no automated check existed.

**The `mockOnEmpty` pattern solved a real problem.** Shipping pages before infrastructure is ready is a legitimate development strategy. The mock fallback made it possible to iterate on dashboard layout and user experience before the event pipeline was producing data. The key insight was that the mock state needed to be explicitly labeled — so that "the demo badge is gone" became a verifiable signal that real data was flowing.

## Discoveries

**Projection handlers must own their table schema.** Early implementations wrote to shared tables that multiple handlers read and wrote. When one handler changed its output schema, other handlers or queries broke unexpectedly. The resolution was table-per-projection-handler: each handler is the exclusive writer to its own table. Other components only read from those tables. Schema changes require only the owning handler and its readers to coordinate.

**Silent zero values are worse than errors.** Several projection handlers had bugs that caused them to write zero values rather than correct values (e.g., a cost field that received `None` and silently stored `0.0`). These produced dashboards that appeared to be working — data was flowing, rows were being written — but the data was wrong. The monitoring gap was that projection correctness was not validated, only projection presence. Adding assertions on value ranges to integration tests caught several of these.

**The API layer must not contain business logic.** An early iteration of the cost trend API computed running totals in the API handler rather than reading pre-computed values from the read model. This was technically correct but placed business logic outside the event-driven path. When the computation logic needed to change, it had to change in the API rather than in the projection handler where it belonged. Moving aggregations into projection handlers eliminated this coupling.

**Read-model isolation from upstream schemas is a hard boundary.** The CI architecture guard that blocks direct upstream database access in the dashboard was written as an automated test, not documentation. The guard prevents the pattern of reading from upstream tables by checking import paths and query patterns during CI. Making this a CI gate rather than a code review guideline meant it was enforced consistently without depending on reviewer attention.

## Decisions Made

**Dashboard reads only from read-model tables.** The dashboard API layer has no access to upstream database schemas. All data visible in the dashboard was written by a projection handler that subscribes to the event bus. This boundary is enforced by the CI architecture guard.

**Table-per-projection-handler ownership.** Each projection handler declares and exclusively owns a specific set of tables. Other components may read from those tables but never write. Schema evolution is the owning handler's responsibility.

**Mock fallback as a first-class development pattern.** The `mockOnEmpty` pattern — render labeled demo data when the API returns empty results — is the approved approach for shipping dashboard pages before their projection handlers are complete. The demo label is the signal that real data is not yet flowing.

**Aggregations belong in projection handlers, not in API handlers.** Any computation that requires historical event data (running totals, time-windowed aggregates, percentiles) is computed by projection workers and stored in read-model tables. The API layer reads pre-computed results.

## Candidate ADRs

- Dashboard data authority: read-model tables are the exclusive source of truth for dashboard rendering
- Table-per-handler ownership: each projection handler owns a specific set of tables exclusively
- CI architecture guard: automated enforcement of the dashboard read-model boundary

## Candidate Pivots

The transition from mock to live data was a milestone, not a pivot — the architecture was always designed for projection-driven rendering. The pivot was the introduction of the `mockOnEmpty` pattern, which changed the shipping strategy: pages could ship before their data pipelines were complete, using mock data as a clearly-labeled placeholder rather than blocking on pipeline completion.

## Related Doctrine

- **Section 2 (Event Sourcing as Truth):** The projection-driven dashboard is the observability expression of this doctrine. The database contains materialized views derived from events; it is not the source of truth. Events are.
- **Section 5 (Clients Render Truth, Clients Do Not Create It):** The dashboard renders what the projection layer has materialized. It has no write surface, no local state, no business logic. This doctrine is enforced structurally by the architecture guard.

## Related Evidence

- LLM cost trend page: mock badge disappeared when `llm_cost_aggregates` table started receiving rows
- Pattern enforcement dashboard: data visible within minutes of the projection handler deployment
- CI architecture guard: blocks any PR that adds direct upstream table queries to the dashboard codebase

## Open Questions

- How should projection handlers handle schema evolution? Currently, schema changes require coordinated deployment of the handler and any downstream readers. A migration pattern for non-breaking and breaking changes would reduce deployment coupling.
- What is the correct behavior when a projection handler falls behind on its topic (consumer lag spikes)? The dashboard currently shows stale data without indicating staleness. A staleness indicator driven by consumer lag metrics would improve observability of the projection layer itself.

## Follow-up Work

- Add a projection lag indicator to the dashboard that shows last-updated timestamps for each data category
- Formalize the table ownership model in the contract YAML schema — each node contract should declare which tables it owns as a write surface
- Extend the CI architecture guard to cover integration tests, not just application code
