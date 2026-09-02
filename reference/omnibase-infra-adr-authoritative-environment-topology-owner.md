---
type: reference
status: current
date: "2026-09-02"
title: "ADR-010: OmniBase Infra Owns Authoritative Environment Topology"
topics: [omnibase-infra, adr, authoritative, environment]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-010-authoritative-environment-topology-owner.md on 2026-09-02. -->

# ADR-010: OmniBase Infra Owns Authoritative Environment Topology

## Status

Accepted

## Date

2026-07-29

## Context

the tracking ticket requires one checked-in, secret-free authority for application-database
topology. `omnibase_infra` already owns the typed Docker service catalog and its
generator, ships the runtime topology consumer package, and directly consumes
`omnibase_core.models.core.ModelDeploymentTopology`. `omninode_infra` owns Kubernetes
manifests, but those manifests are deployment projections and must not become a second
database-semantics registry. Host-local `~/.omnibase/topology.yaml` is mutable setup
state and cannot be platform authority.

## Decision

`omnibase_infra/src/omnibase_infra/topology/instances/*.yaml` is the authoritative
environment topology. Each file parses through the frozen, extra-forbid
`ModelDeploymentTopology` contract. The files may contain logical database names,
schema domains, NOLOGIN owner names, workload-principal names, explicit grant
declarations, and DSN environment-variable names. They contain no credentials or DSN
values.

Docker database bindings under `docker/catalog/` and Kubernetes database/secret
bindings under `omninode_infra/k8s/` are generated or parity-validated projections.
The Kubernetes secret-ownership manifest remains authoritative for credential
synchronization only; it does not own database, schema, or principal semantics.

The `omninode_runtime` service name and `omninode_runtime` PostgreSQL principal are
separate namespaces. The service consumes the `omninode_runtime_service` binding,
which resolves to the principal. Consumers load an explicitly named checked-in
environment and never fall back to a host-local file or an inferred database.

## Consequences

### Positive

- Docker, Kubernetes, runtime catalogs, and DSN maps can prove parity against one typed
  instance.
- Seeded database, schema, principal, or DSN-environment drift fails before deployment.
- Local setup remains useful without gaining authority over shared environments.
- Secret values remain solely in secret-management systems.

### Negative

- Cross-repository Kubernetes changes require an exact `omnibase_infra` source revision
  or projection checksum until the topology is distributed as a released artifact.
- A topology-model change must land in `omnibase_core` before consumer PRs may land.

### Neutral

- This decision declares target semantics only. It performs no DDL, GRANT, secret
  rotation, deploy, restart, workload cutover, or database retirement.
