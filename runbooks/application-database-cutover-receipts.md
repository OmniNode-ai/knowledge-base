---
type: runbook
status: current
date: "2026-07-31"
title: "Application database cutover receipts"
topics: [omnibase-infra, application, database, cutover, receipts]
refs: []
---

# Application database cutover receipts

<ticket> provides proof mechanics for one-application-database family cutovers.
It does not activate a writer, change a DSN, apply a grant or policy, or authorize a
live cutover. Each coherent relation family is registered and stopped independently.

## Contract and evidence boundary

`ModelCutoverFamilyContract` declares:

- a stable family ID and whether the family is a projection or control-plane family;
- secret-free source and target topology binding references;
- SHA-256 pins for the exact source and target evidence-query contracts;
- one post-checkpoint mode: proven reverse delta or explicit forward-fix-only;
- a hard maximum for any optional dual-write window (zero disables it); and
- the required observation-window duration.

`ModelPostgresEvidenceQuerySet` is a complete, read-only query contract. All ten
queries are required and must return one text signature column. A source query may
perform an explicit transformation such as legacy slug to canonical UUID. The
collector binds each query set by SHA-256 and reads the source/target pair in one
read-only, repeatable-read PostgreSQL snapshot.

The receipt evaluates every dimension in canonical order:

1. transformed key set and row count;
2. transformation-aware row hashes;
3. foreign keys and sequence state/ownership;
4. owners and explicit grants;
5. policies and dependent views/functions;
6. projection versions/event offsets or control-plane snapshot/final-delta evidence;
7. transformation collision scans; and
8. dependency signatures.

Every dimension is present even when it is expected to be empty. Any mismatch makes
the receipt `FAIL`, durably blocks only that family, and prevents further journal
transitions. A repair receipt must be a newly generated PASS that postdates the failed
receipt; an older PASS cannot be replayed to clear the block.

## Durable journal

`RepositoryPostgresCutoverJournal.initialize()` explicitly creates the proof tables
in `omninode_internal`. The bootstrap SQL is packaged with the library but is not in
the automatic forward-migration stream. Registration is immutable: changing a
same-ID family contract is rejected.

The repository serializes each family with a row lock and appends SHA-256-linked
events for backfill, optional bounded dual-write, final delta, writer checkpoint,
real application-path write, reader cutover, observation window, quiescence, and the
declared post-checkpoint proof. Event times must be monotonic. Foreign keys bind every
receipt, journal event, and reverse-delta proof to the same family.
Observation completion is refused before the family-specific durable deadline.

The journal records evidence references, not credentials or customer payloads. A
real application-path write proof names only the logical database, principal, schema,
and target sequence. Projection receipts retain versions and offsets. Control-plane
receipts retain source/target snapshot hashes, final-delta hashes, and watermarks.

## Rollback decision

| Family state | Direct DSN rollback |
| --- | --- |
| No target-only write | Allowed; source remains authoritative |
| Bounded dual-write still open | Refused until the window ends and writers quiesce |
| Target-only write, reverse delta incomplete | Refused |
| Target-only write, forward-fix-only | Refused; apply the declared forward fix |
| Writer quiesced, contiguous reverse delta applied, fresh reconciliation receipt and behavioral readback recorded | Allowed |

Reverse-delta entries must cover every target sequence from the first target-only
write through the quiesced final sequence. Merely retaining the source or recording a
proof ID is insufficient. The proof must cite the exact quiescence event, a fresh PASS
reconciliation receipt, and a behavioral readback artifact.

## Verification

Focused local proof:

```bash
uv run pytest \
  tests/unit/migration/cutover \
  tests/integration/migrations/cutover/test_cutover_receipts_postgres16.py \
  tests/ci/test_legacy_rds_fixture_contract.py -v
```

Rebuilt Docker proof (where Docker is available):

```bash
docker compose --project-name omn15420-cutover-proof \
  -f docker/legacy-rds-fixture/compose.yml \
  up --build --abort-on-container-exit --exit-code-from proof
docker compose --project-name omn15420-cutover-proof \
  -f docker/legacy-rds-fixture/compose.yml \
  down --volumes --remove-orphans
```

The Docker harness is wholly synthetic. It seeds RED controls for a family-local
metadata mismatch, expired blind dual-write, post-write direct rollback, incomplete
reverse-delta coverage, and forward-fix-only rollback. It grants no live execution or
retirement authority.
