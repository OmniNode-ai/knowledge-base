---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Build-Loop Migration Boundary"
topics:
  - omnimarket
  - build-loop
  - migrations
refs: []
---

<!-- Migrated from omnimarket:docs/migrations/build-loop.md on 2026-09-01 -->

# Build-Loop Migration Boundary

The build-loop migration moved portable workflow logic and handler contracts into
OmniMarket while leaving concrete runtime wiring and host services outside this
repo.

## What Market Owns

OmniMarket owns the contract-backed build-loop node packages:

| Node | Role | Boundary |
| --- | --- | --- |
| `node_build_loop_orchestrator` | Orchestrator | Coordinates the full build-loop workflow. |
| `node_loop_state_reducer` | Reducer | Pure FSM transition logic. |
| `node_rsd_fill_compute` | Compute | Ticket scoring and fill selection logic. |
| `node_ticket_classify_compute` | Compute | Buildability classification. |
| `node_closeout_effect` | Effect | Close-out side-effect boundary. |
| `node_verify_effect` | Effect | Verification side-effect boundary. |
| `node_build_dispatch_effect` | Effect | Delegation dispatch side-effect boundary. |

The implementation should depend on protocols, typed models, and injected
services rather than concrete infrastructure modules.

## What Runtime And Infrastructure Own

Runtime and infrastructure layers own:

- event-bus implementations;
- deployment topology;
- Kafka and database service configuration;
- Docker runtime and host lifecycle;
- secrets and environment injection;
- concrete adapters for ticket systems, code hosts, and runtime services.

Those layers may discover OmniMarket nodes through `onex.nodes` entry points or
explicitly instantiate handlers for operational wiring, but they should not
become the canonical owner of portable build-loop behavior.

## Current Semantics

"Migrated to OmniMarket" means workflow logic and contracts live here. It does
not mean every node can run in full production mode without runtime-provided
adapters, credentials, broker connectivity, or deployment wiring.

Standalone local proofs should use `EventBusInmemory` where the node declares
that capability. Full-stack execution requires the external services declared by
node metadata and runtime configuration.

## Dashboard And Projection Events

Build-loop and projection events emitted by Market nodes are dashboard input
surfaces. When adding or changing dashboard-visible events:

- declare the topic in `contract.yaml`;
- keep event names stable and versioned;
- update the relevant projection node or read-model docs;
- add a golden-chain or projection test that proves the emitted shape.

## Migration Guardrails

- Do not reintroduce business logic into platform wrappers.
- Do not make Market handlers import concrete runtime implementations when a
  protocol or adapter injection point is available.
- Do not delete runtime compatibility paths until consumers are rewired and the
  new Market path has proof coverage.
- Do not treat historical migration sequencing as current architecture. Current
  facts belong in this file, the package-model docs, and node contracts.
