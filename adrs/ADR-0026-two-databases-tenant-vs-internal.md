---
type: adr
status: accepted
date: "2026-07-29"
title: "ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops"
adr_id: ADR-0026
topics: [multitenancy, database, rls, tenant-isolation, postgres, data-topology]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops

## Context

Tenant isolation work (the RLS program) had been running on the premise that one shared
analytics database holds both tenant-facing data and the platform's own internal
telemetry, and that isolation would be achieved by adding `tenant_id` plus a row-level
security policy to every table in it.

That premise broke on the `baselines_*` family. Source verification of both the deprecated
`ServiceBatchComputeBaselines` and its canonical successor `HandlerBaselinesBatchCompute` /
`node_projection_baselines*` established that every `baselines_*` table is a
GROUP-BY-date/cohort/pattern **global aggregate with no tenant dimension anywhere
upstream** — the source tables (`agent_actions`, `agent_routing_decisions`) carry no
`tenant_id` either. Stamping a default `tenant_id` on them would mislabel blended
cross-tenant data as single-tenant: a misattributed control, worse than an absent one.
The family therefore could not satisfy the RLS program, and could not be honestly excluded
from it either, because "table in the tenant database with no `tenant_id`" is
indistinguishable from an unclosed isolation gap.

A live read-only census of the RDS instance on 2026-07-29 sharpened the picture. Of 317
application tables across eight databases, **18 carry `tenant_id`** — 10 in the tenant
control plane, 7 in the analytics warehouse, 1 in the runtime database. The overwhelming
majority of the analytics database is internal dev-loop telemetry: agent actions, pattern
lifecycle, gate decisions, PR lifecycle, evidence projections, validation runs. Applying
per-table RLS across it would have been a large program aimed mostly at data that has no
tenant and never will.

The same census found that the database boundary currently isolates nothing:
`pg_database.datacl` is NULL on every database, i.e. `CONNECT` is granted to `PUBLIC`, and
all seven application login roles can reach all nine databases including the identity
store.

The operator was asked to rule and reaffirmed a standing position: two databases, split by
purpose.

## Decision

**The platform runs two application databases, split by purpose, not by tenant and not by
service:**

1. A **tenant database**, holding every tenant-facing surface. Its invariant (**I-1**):
   every table carries `tenant_id NOT NULL`, has row-level security ENABLED and FORCED,
   and has a tenant-isolation policy. A table that cannot satisfy this does not belong in
   it.
2. An **internal database**, holding the platform's own operational and dev-loop data —
   `baselines_*`, agent telemetry, gate/PR/evidence surfaces. Its invariant (**I-2**): no
   table carries `tenant_id`, no table has RLS, and no tenant-facing reader connects to it.

`baselines_*` goes to the internal database. It is out of RLS scope permanently.

Tenant-isolation claims scope to the **tenant** database. "All tenant data is isolated" is
proven by I-1 over the tenant database, not by an unbounded table count over a mixed
warehouse.

The identity plane (Keycloak's database) and the per-service internal databases
(`omnibase_infra`, `omniintelligence`, `omniclaude`, `omnimemory`, `umami`) are out of this
split's scope and keep their own databases and roles.

**Both invariants must be enforced as required pre-merge CI gates, RED-proven against a
seeded violation, failing closed when a database is unreachable.** A stated invariant with
no mechanism is not a decision, it is a preference.

## Alternatives Considered

1. **One shared database, per-table RLS everywhere** (the prior working premise). Rejected:
   it forces a choice between a vacuous always-NULL `tenant_id` on global aggregates and a
   permanently ambiguous "table with no `tenant_id`" state that no gate can distinguish
   from a gap. It also spends the isolation program's budget on ~79 tables of internal
   telemetry that have no tenant.
2. **Per-tenant databases** (tenant A gets its own database). Already decided against on
   2026-07-07 and **not** revisited here — see "Relationship to the 2026-07-07 decision".
3. **Keep one database, exclude `baselines_*` by allowlist.** Rejected: an allowlist inside
   a fail-closed isolation gate is the exact shape that erodes. Every future untenanted
   table becomes an allowlist argument.
4. **Commission real per-tenant baselines** (add a tenant dimension to the aggregate chain
   end to end). Not rejected on merit — it is a genuine product option — but it is a
   redesign of the aggregation chain, not an isolation fix, and it does not resolve the
   other ~79 untenanted tables. It remains available later; the split does not foreclose it.

## Consequences

**What improves.** The isolation claim becomes small, total and checkable: two SQL
assertions, not a table census. `baselines_*` stops being an open RLS gap and becomes a
correctly-placed internal table. New tables get an unambiguous home question ("does this
have a tenant?") instead of a per-table RLS negotiation. The blast radius of an RLS
misconfiguration shrinks to the tenant database. A leaked internal-reader credential
reaches no tenant data.

**What becomes harder.** Cross-database joins between tenant data and internal telemetry
become impossible — no FDW, no dblink. Any analytic that needs both must move to the
application layer or become an explicitly tenant-dimensioned projection. Migration
sequencing gains a step: every table move must declare which migration ledger records it,
and there are currently three competing ledger shapes in the affected databases. Two
databases means two sets of roles, grants, connection secrets and backup/restore paths.

**What is required before the split means anything.** `REVOKE CONNECT … FROM PUBLIC` with
explicit per-role grants. Without it, the two databases are two names on one flat
permission surface, and the decision buys nothing.

## Relationship to the 2026-07-07 decision

The 2026-07-07 multitenancy plan records *"one DB, RLS — NOT per-tenant databases."* That
decides a **different axis**: whether to shard per tenant. This ADR does not disturb it.
All tenants continue to share one tenant database, isolated by RLS. This ADR adds a second
database that holds nothing tenant-facing at all. The two decisions are orthogonal and both
stand.

## Provenance

This ADR records an operator ruling. A search of every durable decision surface found no
prior written record of it: Linear (three targeted sweeps, ~75 issues inspected — the
nearest match, the February 2026 `[Epic] DB-Per-Repo Split`, is a per-service split), the
ADR corpus, the workspace decisions directory, the rolling work ledger, and the
`decision_store` table itself (which returns **zero rows** on the RDS instance and on both
local lanes — the surface exists but has never been written to). The ruling is therefore
recorded here as the decision of record rather than cited to an earlier artifact.

## Related Pivots

## Related Doctrine

## Derived From

Operator ruling, 2026-07-29.

## Evidence

Live read-only census of the development RDS instance, 2026-07-29, via SSM port forwarding,
connected as the master role with the credential resolved from Secrets Manager into process
environment only. No DDL, no DML, no GRANT, no RLS state change.

- 317 application tables across eight databases; 18 carry `tenant_id`.
- Tenant control plane: 16 tables, 10 tenant-stamped, `tenant_id` typed `uuid`.
- Analytics warehouse: 86 tables, 7 tenant-stamped, `tenant_id` typed `text`/`varchar`;
  3 tables with RLS ENABLED (not FORCED), 1 policy each.
- Runtime database: 72 tables, 1 tenant-stamped, no RLS.
- `baselines_*`: 8 physical tables across two databases, three names duplicated, none
  carrying `tenant_id`.
- `pg_database.datacl` NULL on all nine non-system databases; all seven application login
  roles hold `CONNECT` on every database.

Implementation plan and full inventory: `omni_home/docs/plans/2026-07-29-two-database-tenant-vs-internal-split-plan.md`.

## Supersedes
