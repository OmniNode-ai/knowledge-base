---
type: reference
status: current
date: "2026-09-01"
title: "OmniMarket Node Metadata Reference"
topics:
  - omnimarket
  - nodes
  - onex-runtime
refs: []
---

<!-- Migrated from omnimarket:docs/reference/node-metadata.md on 2026-09-01 -->

# Node Metadata Reference

Every direct node package should have a `metadata.yaml` file beside its
`contract.yaml`.

## Required Fields

```yaml
name: node_example
version: "1.0.0"
description: "Short node description"
omnibase_core_compat: ">=0.39.0,<1.0.0"
entry_points:
  onex.nodes:
    node_example: "omnimarket.nodes.node_example"
capabilities:
  standalone: true
  full_runtime: true
  requires_network: false
  requires_repo: false
  requires_secrets: false
  requires_docker: false
  side_effect_class: read_only
dependencies:
  - "omnibase_core>=0.39.0"
authors:
  - "OmniNode Platform Team"
license: "MIT"
tags:
  - example
```

## Optional Package Fields

```yaml
pack: diagnostics
display_name: Platform readiness
node_role: compute
entry_flags:
  dry_run: "Run without mutation"
deprecated: false
deprecated_by: null
deprecated_reason: null
```

Use these fields when a node is part of a domain package or when wrapper
generation needs a user-facing name and entry flags.

## Capability Fields

| Field | Meaning |
| --- | --- |
| `standalone` | Can run with local/in-memory runtime support. |
| `full_runtime` | Can run when full event-bus/runtime services are configured. |
| `requires_network` | Needs network access. |
| `requires_repo` | Needs a checked-out repository path. |
| `requires_secrets` | Needs secrets or credentials. |
| `requires_docker` | Needs Docker host access. |
| `side_effect_class` | One of `read_only`, `mutating`, `deploy`, or `release`. |

Set capabilities conservatively. A missing prerequisite should fail clearly
rather than silently degrading.

## Dependency Declarations

Declare node-owned imports in `dependencies`. The metadata dependency check
normalizes common import names to distribution names, so use package
distribution names rather than module names when they differ.

Run:

```bash
uv run python scripts/ci/check_node_metadata_dependencies.py
```

## Entry-Point Rule

The entry point must resolve to the package directory:

```toml
[project.entry-points."onex.nodes"]
node_example = "omnimarket.nodes.node_example"
```

It must not point to a factory function, handler class, or registration helper.
The runtime loads `contract.yaml` from the package root.
