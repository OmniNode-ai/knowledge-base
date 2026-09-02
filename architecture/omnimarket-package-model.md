---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Package Model"
topics:
  - omnimarket
  - onex-runtime
  - packaging
refs: []
---

<!-- Migrated from omnimarket:docs/architecture/package-model.md on 2026-09-01 -->

# OmniMarket Package Model

OmniMarket exists to make ONEX automation portable, testable, composable, and
observable. The repo converts long-lived workflow behavior into contract-backed
node packages that can be loaded by local or full-stack runtimes.

## Layers

| Layer | Lives in | Responsibility | Owns business logic |
| --- | --- | --- | --- |
| Skill surface | Platform wrapper repos | User input, command publishing, progress display, result formatting. | No |
| Node unit | OmniMarket | Atomic executable contract package. | Yes |
| Workflow package | OmniMarket | Domain-scoped orchestration across node units. | Yes |
| Market artifact | Package/registry tooling | Installable distribution for a node or workflow package. | No |
| Runtime | Core and infrastructure repos | Contract loading, event transport, state, deployment, and external adapters. | No |

## Node Package Shape

Each node unit is a package directory:

```text
src/omnimarket/nodes/node_example/
  __init__.py
  contract.yaml
  metadata.yaml
  handlers/
    __init__.py
    handler_example.py
```

`contract.yaml` is the runtime interface. It declares handler bindings, command
topics, emitted events, input and output models, and the terminal event.

`metadata.yaml` is the package capability declaration. It declares dependency
scope, runtime prerequisites, side-effect class, package grouping, and entry
flags.

The root `pyproject.toml` exposes each node package through
`[project.entry-points."onex.nodes"]`. Each entry point resolves to a package
directory containing `contract.yaml`.

## Runtime Modes

OmniMarket supports two execution shapes:

| Mode | Transport | State | Typical use |
| --- | --- | --- | --- |
| Local proof | `EventBusInmemory` | Temporary or file-backed state root | Unit, golden-chain, and CI proofs. |
| Full runtime | External event bus and service adapters | Runtime-managed state and projections | Deployed automation and observability. |

The same contract should describe both modes. A node that requires network,
secrets, Docker, a repository checkout, or another external capability must say
so in `metadata.yaml` instead of silently degrading.

## Contract Rules

- Event topics belong in `contract.yaml`.
- Handlers should read configured topics from the runtime contract binding.
- Handlers should use protocols or injected adapters for external I/O.
- Cross-node shared models belong in shared Market packages, not in one node's
  private directory.
- Golden-chain tests should prove contract execution with the in-memory event
  bus whenever possible.

## Package Isolation Status

Per-node metadata already declares package dependencies, but the current root
distribution still exposes all nodes from one installed package. This means the
root dependency set remains broader than the ideal package model.

Do not remove a root dependency just because it is node-owned unless node package
install isolation or lazy entry-point loading protects imports for the rest of
the package. Use `scripts/ci/check_node_metadata_dependencies.py` to keep node
metadata honest while that transition is incomplete.
