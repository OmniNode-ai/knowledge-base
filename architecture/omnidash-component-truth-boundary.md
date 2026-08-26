---
type: architecture
status: accepted
date: "2026-08-26"
title: "Dashboard Component Truth Boundary"
topics: [omnidash, doctrine, projections, truth-boundary, widgets]
refs: [architecture/omnidash-composable-frame.md, doctrine/authoritative-projections-own-truth.md, doctrine/state-is-materialized-projection.md]
---

# Dashboard Component Truth Boundary

**Owner:** `omnidash` (`src/components/dashboard/`)

Dashboard components are presentation surfaces. They do not own platform truth.

All widgets in the dashboard component tree must follow the platform's deterministic truth doctrine — see [`doctrine/`](../doctrine/README.md), in particular [authoritative projections own truth](../doctrine/authoritative-projections-own-truth.md) and [state is a materialized projection](../doctrine/state-is-materialized-projection.md).

## Authoritative Data Boundaries

Dashboard components may consume data only through approved dashboard surfaces:

- `useProjectionQuery(...)` for projection snapshots.
- `src/data-source/` adapters selected by `VITE_DATA_SOURCE`.
- Contracted HTTP projection/API surfaces exposed through those adapters.
- Approved browser subscription surfaces when they invalidate or append display data from the same contracted topic.

Dashboard components must not:

- read Postgres or any backend database directly;
- import Kafka, Redpanda, Redis, Postgres, Prisma, Drizzle, or Node transport clients;
- infer authoritative state by merging unrelated streams;
- deduplicate authoritative records except by contracted message identity;
- implement projection reducers or lifecycle FSM semantics in React state;
- fabricate consistency when data is missing, stale, or degraded.

## Component State Is Presentation State

React state in widgets may hold presentation-only concerns:

- selected chart dimension or style;
- hover, tooltip, search, collapsed, paused-scroll, and active-tab state;
- bounded display buffers for already-authorized data;
- local loading, empty, and error presentation.

React state must not become the source of truth for:

- lifecycle status;
- queue position;
- build, dispatch, registration, or verification outcomes;
- cross-topic joins;
- freshness, ordering, or cursor progress.

If a widget needs one of those values, add or consume an authoritative projection/API surface first.

## Stories and Tests

Every data-driven widget story must seed deterministic fixture data through `makeDashboardDecorator(...)` or `DataSourceTestProvider`. Mocks and fixtures prove component behavior only; they do not prove runtime truth.

Runtime truth claims require durable evidence outside the dashboard repository — change-control receipts, CI checks, PR review records, issue-tracker evidence, or an approved artifact store.

## Evidence

Verified against the live omnidash tree at migration time: `useProjectionQuery`, the `src/data-source/` adapters, `DataSourceTestProvider` (`src/test-utils/dataSourceTestProvider.tsx`), and `makeDashboardDecorator` all exist.
