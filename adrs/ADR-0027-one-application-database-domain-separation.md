---
type: adr
status: accepted
date: "2026-07-29"
title: "ADR-0027: One Application Database with Contract-Classified Domains"
adr_id: ADR-0027
topics: [multitenancy, database, rls, tenant-isolation, postgres, data-topology, contracts]
refs: [adrs/ADR-0026-two-databases-tenant-vs-internal.md]
supersedes: [ADR-0026]
superseded_by: []
---

# ADR-0027: One Application Database with Contract-Classified Domains

## Context

ADR-0026 correctly separated customer-owned data from platform-internal data, but it
made that semantic distinction a physical two-database boundary. Further review showed
that physical placement is not the source of truth for ownership or authorization.
Database names cannot distinguish a deliberately global table from an unclassified
tenant table, and a second database adds cross-database joins, duplicated migration
state, and a larger cutover without replacing the need for explicit grants and
row-level controls.

The read-only inventory and failure analysis in ADR-0026 remain valid. They establish
the need for complete classification, least-privilege identities, canonical tenant
keys, and fail-closed row-level security. They do not require two physical application
databases.

## Decision

The platform uses **one physical application database** for tenant-control-plane,
application-projection, and platform-operational data. Three contract-declared schema
domains provide the authoritative boundary:

1. **Tenant** — customer-owned relations use a canonical immutable tenant identifier,
   forced row-level security, and fail-closed read and write policies.
2. **Platform internal** — registry, orchestration, evidence, telemetry, baseline, and
   operational relations require no authorization tenant key and grant no access to
   tenant-facing roles.
3. **Platform catalog** — genuinely global product catalogs receive narrow declared
   reads and a dedicated writer or migration path.

Typed deployment topology owns schemas, owners, workload principals, connection
bindings, and migration streams. Typed node and service declarations own each
relation's database reference, schema, access, and migration source. Generated or
parity-validated deployment configuration consumes those contracts; database names,
table-name allowlists, and runtime defaults are not authoritative.

Schema owners are non-login roles. Runtime identities own no objects, have no DDL or
row-security bypass, and receive only domain-specific privileges. A process that needs
tenant and internal data uses separate pools and credentials even though both resolve
to the same physical database. Identity-plane and independently service-owned databases
remain separate and are not merged merely to satisfy this decision.

Migration is additive-first. Source relations remain intact until transformation,
cutover, and rollback evidence pass. Retiring a prior database or source relation is a
separate destructive decision.

## Alternatives Considered

1. **Two application databases split by tenant versus internal purpose.** Superseded:
   it preserves the semantic distinction but turns it into unnecessary physical
   topology, duplicates migration and connection surfaces, and still requires the same
   role, grant, and row-level controls.
2. **One mixed schema with table-by-table exceptions.** Rejected: a missing tenant key
   is indistinguishable from an intentional internal classification without a typed
   domain contract.
3. **Per-tenant databases or schemas.** Rejected: tenancy is shared-database and
   row-level; operational complexity would scale with tenant count.
4. **Infer domain from current columns or writers.** Rejected: existing drift and
   blended aggregates prove that storage shape and producer identity are not reliable
   ownership signals.

## Consequences

Classification becomes total and mechanically checkable while preserving local,
schema-qualified access for legitimate cross-domain application workflows. The
physical database is not treated as the security boundary; compromise resistance
depends on separate identities, explicit privileges, forced row-level security for
tenant data, and denial of tenant-role access to internal schemas.

The migration must reconcile historical ledgers, table ownership, tenant identifier
types, grants, policies, and adapters before workload cutover. Every relation needs one
declared owner and domain. Unclassified or ambiguous relations fail closed and do not
move, lose protection, or gain runtime access.

## Related Pivots

## Related Doctrine

Contract authority, fail-closed validation, least privilege, and durable evidence.

## Derived From

An approved architecture review that retained ADR-0026's evidence while rejecting its
physical-topology conclusion.

## Evidence

- The read-only inventory and failure analysis preserved in ADR-0026.
- Required static, fresh-install, legacy-upgrade, role, row-security, cutover, rollback,
  and staged behavioral proof defined by the approved implementation plan.

Implementation evidence is intentionally pending; accepting this decision does not
claim that the migration or runtime cutover is complete.

## Supersedes

[ADR-0026](ADR-0026-two-databases-tenant-vs-internal.md).

## Superseded By
