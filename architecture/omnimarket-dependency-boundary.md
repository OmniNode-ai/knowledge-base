---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Dependency Boundary"
topics:
  - omnimarket
  - dependencies
  - packaging
refs: []
---

<!-- Migrated from omnimarket:docs/architecture/dependency-boundary.md on 2026-09-01 -->

# Dependency Boundary

OmniMarket has two dependency layers today:

1. Root package dependencies in `pyproject.toml`.
2. Per-node package dependencies in each node's `metadata.yaml`.

The desired long-term model is node-scoped dependency ownership. The current
root distribution still exposes all `onex.nodes` entry points from one package,
so root dependencies remain broader until install isolation or lazy entry-point
loading is in place.

## Current Rule

- Keep every node's `metadata.yaml` accurate.
- Keep root dependencies sufficient for package importability.
- Do not remove broad root dependencies until the entry-point import path proves
  that nodes with optional or isolated dependencies do not break unrelated
  runtime discovery.
- Treat metadata checks as the current enforcement mechanism, not as proof that
  root dependencies can already be minimized.

## Shared Runtime Dependencies

The dependency-scope check treats a small set of packages as shared runtime
dependencies:

- `omnibase_core`
- `packaging`
- `pydantic`
- `python-dateutil`
- `pyyaml`

Other external imports under `src/omnimarket/nodes/node_*` should generally be
declared in that node's `metadata.yaml`.

## Root Dependencies With Node-Heavy Usage

Some dependencies are mostly or entirely used by node packages but remain in the
root package for current import safety:

- `httpx`
- `omnibase-infra`
- `omnibase-spi`
- `omninode-memory`
- `psycopg2-binary`
- `radon`

Dependencies that also support shared runtime or projection helpers need a more
careful classification before removal:

- `aiokafka`
- `asyncpg`
- `omnibase-compat`
- `onex-change-control`

## Validation

Run:

```bash
uv run python scripts/ci/check_node_metadata_dependencies.py
```

The check enforces:

- every direct node package has `metadata.yaml`;
- node-owned external imports are declared in metadata dependencies;
- test-only imports do not count as runtime dependency scope;
- import names are normalized to distribution names.

This check protects the future package model while the current root package still
serves as the import surface for all nodes.
