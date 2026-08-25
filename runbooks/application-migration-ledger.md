---
type: runbook
status: current
date: "2026-08-04"
title: "Application migration ledger"
topics: [omnibase-infra, application, migration, ledger]
refs: []
---

# Application migration ledger

**Ticket:** <ticket>
**Target database:** `omnidash_analytics`
**Canonical relation:** `platform_catalog.schema_migrations`

This runbook defines the deterministic migration-history boundary for the
unified application database. It does not merge the separate
`omnibase_infra.public.schema_migrations` service ledger into the application
database.

## Canonical model

The selected application ledger is the existing checksum-capable
`public.node_schema_migrations` table. The bootstrap moves that table into
`platform_catalog` in one PostgreSQL transaction and keeps its relation OID,
rows, timestamps, and owner. It then adds the contract dimensions required by
the deployment topology:

| Column | Meaning |
| --- | --- |
| `migration_stream` | Exact producer stream, such as `node:<node>` |
| `owner` | Checked-in producer owner; never inferred from the login role |
| `domain` | `tenant` or `omninode_internal` for executable node migrations |
| `version` | Exact historical runner identity |
| `checksum` | Lowercase SHA-256 |
| `checksum_kind` | `content_sha256` or quarantined `legacy_attestation` |
| `applied_at` | Original application timestamp |
| `provenance` | Deterministic source relation/file identity |

The primary key is `(migration_stream, domain, version)`. An active node row
must match the checked-in file SHA-256 exactly. A `legacy_attestation` row can
never satisfy an active migration probe.

## Historical import policy

Source ledgers remain intact. Import is additive to the selected canonical
ledger and rerunning it must produce an identical row set.

| Source | Authority | Canonical treatment |
| --- | --- | --- |
| `public.node_schema_migrations(version, applied_at, checksum)` | Applied node set | Move in place; require exact manifest identity and file SHA-256 |
| `public.omnimarket_schema_migrations` | Applied projection set | Normalize `(node_name, filename)` to the exact node version; require manifest checksum; reject overlap with node history |
| Filename-only `public.schema_migrations(filename, applied_at)` | Applied legacy set without checksums | Preserve source and import a deterministic source-record attestation under `legacy:filename-only` |
| `public.schema_migrations(migration_id, applied_at, checksum, source_set)` with `source_set = 'node'` | Applied node set written by the pre-<ticket> runner | Preserve source and adopt under the manifest's exact stream/owner/domain; see <ticket> below |
| Cloud `public.schema_migrations(version, applied_at, checksum)` | Applied cloud set | Preserve source and import under exact producer stream `omninode-cloud` |
| Cloud `public.migrations_log` | Audit/attempt evidence only | Enrich matching applied rows through the checked-in alias map; a log-only alias is fatal |

Filename-only and cloud records currently use domain
`legacy_unclassified`. This is an explicit non-executable quarantine, not a
claim that the migrations target `tenant`. <ticket> must provide
per-artifact topology domains before those rows can be promoted. Cloud SQL is
cross-domain, so a blanket domain default is prohibited.

### <ticket> — adopting the predecessor `migration_id` node ledger

**Operator ruling, 2026-08-04: ADOPT/CONVERT.**

The four-column `public.schema_migrations(migration_id, applied_at, checksum,
source_set)` relation is ambiguous by column signature alone. The
pre-<ticket> runner created it in **both** databases: in the service database
it is the service-owned ledger (`source_set = 'docker'`, ids `docker/<file>`),
and in the **application** database it is the predecessor **node** ledger
(`source_set = 'node'`, ids `node:<node>:<file>.sql`). The original arm refused
the shape outright, which was a false negative for the application database and
left the dev lane unable to bootstrap.

The bootstrap now partitions on row content before deciding:

| Source row | Treatment |
| --- | --- |
| `source_set = 'node'` and id matches `node:<node>:<file>.sql` | Adoptable |
| `source_set = 'docker'` and id matches `docker/…` | Ignored — service-owned |
| anything else | Fatal: `unknown migration ledger shape: … unrecognized migration_id rows` |

A relation with zero adoptable rows is still refused with the original
`unknown migration stream: service-owned migration_id ledger cannot be selected
for the application database`. **The guard is narrowed for exactly this shape;
it is not weakened generally.**

Adoption is additive and non-destructive, exactly like the filename-only
import: the source relation is never renamed, updated, deleted, or moved. Each
adoptable row inserts one canonical row with `migration_stream`, `owner`,
`domain` and `checksum` taken verbatim from the checked-in manifest,
`version` = the source `migration_id` verbatim, `applied_at` = the source
timestamp verbatim, and
`provenance = adopted:<db>:public.schema_migrations:migration_id:<id>:raw-checksum=<raw>`.

**The one non-derivable point, stated plainly.** The historical runner wrote the
literal `applied-by-runner` in the `checksum` column — there is no byte evidence
in the database. `checksum_kind = 'legacy_attestation'` cannot be used, because
a legacy attestation can never satisfy an active node probe
(`run-forward-migrations.sh` FATALs with *"has only a legacy checksum
attestation"*), which would force re-application — the one thing the ruling
forbids. Adoption therefore writes `content_sha256` with the manifest checksum,
which **asserts** that the bytes applied historically equal today's checked-in
bytes. That assertion is the operator ruling made mechanical, not a derivation.
It is bounded three ways: only the exact `applied-by-runner` literal is
adoptable, a 64-hex source checksum that disagrees with the manifest is still
fatal, and `provenance` permanently records the raw source checksum under an
`adopted:` prefix so an adopted row is never confusable with a runner-verified
`file:nodes/…` row.

Evidence basis for the dev lane specifically (`omnidash_analytics`, read-only,
2026-08-04): all 80 source rows are `checksum='applied-by-runner'`,
`source_set='node'`; all 80 ids are present in the 94-row manifest, zero
live-not-in-manifest; and `git log --since='2026-07-31T06:44:00Z' --name-only --
docker/migrations/forward/nodes/` touches only files in the 14-entry
not-yet-applied set, so no applied artifact's bytes changed after the apply
timestamp. That corroboration is specific to this database and is **not** true
by construction for any other database with this shape.

`scripts/run-forward-migrations.sh` is unchanged: `migration_is_applied()`
already probes on `(migration_stream, domain, version)` + owner + kind +
checksum, which is exactly what an adopted row carries, and `record_migration()`
stays `content_sha256`-only so no forward path can mint an adopted row.

## Deterministic procedure

1. Validate every vendored node SQL file against
   `_ledger/application-migrations.tsv` or an explicit ticketed block in
   `_ledger/application-migration-blocks.tsv`.
2. Stop before migration DDL if an unresolved block is not protected by the
   existing operator fence.
3. Select and extend the checksum-capable node ledger in one transaction.
4. Import filename-only and omnimarket source rows without updating or deleting
   either source relation.
5. Read cloud applied state and audit aliases under one repeatable-read source
   snapshot; import it transactionally into the application ledger.
6. Probe active migrations by stream, domain, version, owner, checksum kind,
   and checksum. Apply and record only an absent, fully declared file.
7. Run the same process a second time and require an identical ledger signature
   with zero newly applied files.

Never insert, update, or delete migration-ledger rows by hand. A missing row is
an indeterminate apply: stop the lane, retain the source catalogs/logs, and
repair through a reviewed deterministic import or a new migration.

## Validation

```bash
uv run python scripts/validation/validate_application_migration_manifest.py
uv run python scripts/validation/validate_application_migration_manifest.py --require-complete
uv run pytest tests/unit/scripts/validation/test_application_migration_manifest.py \
  tests/integration/migrations/test_application_migration_ledger_omn15413.py -q
docker compose -f docker/legacy-rds-fixture/compose.yml up \
  --build --abort-on-container-exit --exit-code-from proof
```

The first command validates the checked-in surface and reports explicit
blocks. The completion command remains RED while any block exists. The
PostgreSQL 16 integration suite proves fresh and sanitized legacy execution
twice plus checksum, unknown-stream, and double-declaration RED controls. The
Docker fixture must also use `--build` so it contains the changed runner and
ledger artifacts.

## Landing holds

- <ticket> still leaves `delegation_judge_verdict_events` unclassified. Its
  unfenced `0016` migration makes the complete runner preflight RED.
- The Kubernetes runner still targets `public.node_schema_migrations`. This
  change cannot land until its exact stacked update targets
  `platform_catalog.schema_migrations`; otherwise it would recreate a second
  ledger after the in-place move.
- No live database query, deployment, grant/RLS change, cutover, or destructive
  action is part of this ticket.
