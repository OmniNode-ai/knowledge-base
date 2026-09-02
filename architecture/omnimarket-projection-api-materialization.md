---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Projection API Materialization"
topics:
  - omnimarket
  - projection
  - database
refs: []
---

<!-- Migrated from omnimarket:docs/migrations/projection-api-materialization.md on 2026-09-01 -->

# Projection API Materialization

`projection_api.expose: true` only exposes a contract-declared topic through
the projection API. It does not create the backing table or view.

Every exposed projection topic needs a separate materialization authority:

- a node-owned migration that creates the exposed table or view;
- or `db_io.db_tables`/`metadata.yaml` ownership that declares the DDL owner
  and migration path, backed by node-local cold DDL proof.

The projection validation ratchet lives in `omnimarket.projection.validation` and checks
the contract name, topic, table/view, declared materialization authority, and
cold migration proof. Missing authority is a contract error; missing table/view
DDL is a cold-runtime readiness error before a dashboard can treat the surface
as projection-backed.

## DB target split

Projection nodes write to one of two databases depending on their consumer:

| Target DB | Purpose | Example nodes |
| --- | --- | --- |
| `omnibase_infra` | Runtime and operational projections consumed by the ONEX runtime or the projection API | `node_projection_session_outcome`, `node_projection_baselines`, `node_log_projection` |
| `omnidash_analytics` | Dashboard analytics projections consumed by OmniDash | `node_projection_routing_decision`, `node_projection_pattern_learning`, `node_projection_cost_by_repo` |

`node_projection_routing_decision` was previously targeting `omnibase_infra`.
It was repointed to `omnidash_analytics` (the correct consumer), which
was verified by a runtime proof at deploy time.

When adding a new projection node, declare the target DB in `metadata.yaml`
(`db_io.target_db`) and in the node's cold DDL migration. Do not assume a
single materialization target — check which service will consume the table and
target accordingly.

The node was originally pointed to `omnibase_infra` and later repointed to
`omnidash_analytics` with an added runtime proof. This is the canonical example
of an incorrect DB target being caught and corrected post-merge.
