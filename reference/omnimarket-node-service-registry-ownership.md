---
type: reference
status: current
date: "2026-09-01"
title: "OmniMarket node_service_registry Ownership"
topics:
  - omnimarket
  - database
  - migrations
refs: []
---

<!-- Migrated from omnimarket:docs/migrations/node-service-registry-ownership.md on 2026-09-01 -->

# node_service_registry Migration Ownership

## Decision

`omnimarket.nodes.node_projection_registration` is the DDL owner for the
`node_service_registry` table.

`node_service_registry` is an omnimarket projection/API read model in
`omnidash_analytics`. It is not the canonical infra registration storage table.
`omnibase_infra` owns runtime registration storage and `registration_projections`;
it must not ship a duplicate `CREATE TABLE node_service_registry` migration.

## Evidence

- The live omnimarket projection node declares ownership for
  `node_service_registry` in
  `src/omnimarket/nodes/node_projection_registration/metadata.yaml`.
- The table is created by
  `src/omnimarket/nodes/node_projection_registration/migrations/0000_create_node_service_registry.sql`.

## Validation

Run the focused ownership proof:

```bash
uv run pytest tests/test_node_service_registry_migration_ownership.py -q
```
