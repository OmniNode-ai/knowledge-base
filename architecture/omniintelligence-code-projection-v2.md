---
type: architecture
status: accepted
date: "2026-08-25"
title: "OmniIntelligence Deterministic Code Projection v2"
topics:
  - omniintelligence
  - code-projection
  - qdrant
  - memgraph
refs: []
---

# Deterministic code projection v2

**Status:** runnable, namespaced dev-lab application canary
**Production runtime authority:** none; the deployed event ingress remains held
**Last Updated**: 2026-08-25 — migrated from `omniintelligence` to the knowledge base, unchanged.

## Decision

`omniintelligence.code_projection` owns the source-scoped serialization contract
and a one-shot application command for the dev lab. The command reads a real
Python, TypeScript, or JavaScript file; applies the existing deterministic
extractors, classifier, quality scorer, and semantic analyzer; stages immutable
content-addressed evidence; materializes the result into the existing
OmniIntelligence Postgres tables, Memgraph, and a tenant-filtered Qdrant
semantic index using the lab's existing 1024-dimensional embedding model; and
reads all three projections back before advancing current state.

This is a real application feature, but it is deliberately namespaced to
logical repository IDs beginning with `lab/`. It does not register a node,
consumer, topic, API, or service entry point; publish source through Kafka;
or claim production ingress authority. It may create and validate one
namespaced shared Qdrant collection and its payload indexes. The operator
command runs inside the existing effects runtime so it uses the lab's injected
Postgres, Memgraph, Qdrant, and embedding clients without a service restart.

The package remains internal to this lane. A later OmniMemory implementation
must consume the checked-in canonical JSON and schema digest through its own
DTOs; neither product package may import the other. Public export, production
runtime activation, or an importer outside this lane triggers an
ownership-relocation review.

The two existing code-file-discovered runtime events remain unchanged. They are
both still imported by different live paths, so event reconciliation belongs to
a separate runtime effort.

## Contract shape

`ModelCodeProjectionBatch` is one full source snapshot or explicit tombstone.
Its header pins schema, projection, reducer, and identity versions. The batch
also contains:

- a required canonical tenant slug, logical repository ID, and normalized POSIX
  repository-relative path;
- a source-partition cursor with an explicit authority and monotonic sequence;
- content-addressed source and transform-manifest references;
- a closed privacy, access, trust, redaction, and retention envelope;
- source-owned nodes, closed relationship edges, and semantic-document refs;
- an exact replay manifest and record checksum.

An empty successfully processed source is a snapshot with no records. It is not
a deletion. Source deletion and policy revocation are distinct tombstone
operations. Parse or extraction failure does not produce an authoritative empty
snapshot.

## Identity rules

Every ID is a domain-separated SHA-256 over canonical JSON. The v2 domains,
prefixes, and payloads are:

| Record | Prefix | Canonical identity payload |
| --- | --- | --- |
| Source | `csrc_v2_` | identity version, tenant ID, logical repository ID, normalized relative path |
| Node | `cnode_v2_` | identity version, tenant-scoped source ID, entity kind, qualified name |
| Edge | `cedge_v2_` | identity version, tenant-scoped source ID, source node ID, relationship kind, target node ID |
| Semantic document | `cdoc_v2_` | identity version, tenant-scoped source ID/hash, chunk key/kind/span, anchor, chunker version, sanitized-content hash |
| Batch | `cbatch_v2_` | the complete versioned batch payload excluding the two self-referential batch-ID fields |

UUIDs, wall-clock time, checkout roots, absolute paths, transport correlation
IDs, and source revision labels never participate in identity or ordering. Any
formula change requires an identity-version and prefix/domain bump. Tenant IDs
are lowercase 3-63 character slugs containing letters or digits separated by
single hyphens. Because every source-owned identity includes the source ID,
equal repository paths in different tenants produce disjoint source, node,
edge, semantic-document, and batch identities.

## Canonical bytes

Wire output is UTF-8 JSON with NFC-normalized strings, lexicographically sorted
object keys, compact separators, no floating-point values, canonically sorted
and unique record arrays, and exactly one terminal LF framing byte. Confidence
is represented as integer basis points.

The parser rejects duplicate keys (including keys that collide after NFC),
invalid UTF-8, noncanonical bytes, unknown fields, coercible-but-wrong scalar
types, unsorted or duplicate records, unstable IDs, checksum drift, manifest
drift, and inline source/docstring/chunk text.

## Endpoint, privacy, and retention rules

Every accepted edge endpoint and semantic-document anchor resolves to a node in
the same source-owned batch. A producer must materialize an unresolved symbol
as a deterministic `external_symbol` node or emit a separate typed extraction
diagnostic. Silent relationship drops and foreign-source ownership are invalid.

Raw source and sanitized semantic content live behind distinct
content-addressed artifact references. A batch contains their hashes and refs,
not their bytes. The lab command retains the exact authorized source bytes and
the exact extractor contract in its operator-supplied artifact root, so its
policy says `redaction_state=not_required`; it never falsely labels those bytes
as sanitized. Arbitrary docstrings, source text, vector bytes, model IDs, local
paths, and generic metadata dictionaries are not batch wire fields.

Staged source objects are immutable evidence. They can remain after a failed
application and remain available after a tombstone; tombstoning removes the
derived Postgres/Memgraph/Qdrant projection, not source history. Artifact-root
access, retention, and eventual purge are operator responsibilities in this
canary.

## Qdrant storage and multitenancy

The semantic projection uses one shared collection, `code_semantic_v2`, with a
named 1024-dimensional `code_semantic_v2` vector and DOT distance. The adapter
normalizes the pinned model output before upload. Collection metadata pins the
storage schema, vector name, embedding model, and model version. Required
keyword indexes are `tenant_id`, `source_id`, `repository_id`, and
`record_kind`; `tenant_id` is created with Qdrant's `is_tenant=true` setting.

Every scroll, query, count, and filtered delete performed by this adapter
injects the canonical tenant ID. Point UUIDs include the tenant ID and semantic
document ID, so equal source paths and documents in different tenants cannot
overwrite one another. Payloads contain identity, policy, provenance, and
content-addressed hashes only—never raw source, semantic content, vectors, or
credentials.

Each tenant/source retains one non-searchable source-manifest control point. It
pins the cursor, operation, batch digest, and exact semantic document/point
membership. Search accepts only documents present in both that manifest and the
independently promoted artifact-current batch. It resolves the immutable
content artifact and re-embeds it with the pinned model. Readback verifies the
exact stored float32 vector digest and requires at least 9,990 basis points of
cosine agreement with the live model output before returning metadata. The
bounded comparison is deliberate: the lab GPU endpoint exhibits small
run-to-run numeric jitter even for identical text. Material semantic drift still
fails closed, while storage truth remains independent of a mutable payload-only
claim.

Tenant filtering is an application authorization boundary, not Qdrant row-level
security for arbitrary direct database credentials. The shared collection key
must remain server-side. The lab endpoint may omit an API key. A Qdrant Cloud
database key is supported only with an explicit HTTPS `QDRANT_URL`; plaintext
key transport is rejected. The embedding response must explicitly return one
unique index per input and the requested model name. The endpoint does not
cryptographically attest model weights, so a deployment/weight change requires
an operator-supplied model-version and collection-contract bump.

The application client is endpoint-compatible with a self-hosted Qdrant server
over HTTP and Qdrant Cloud over HTTPS. The current effects compose overlay does
not inherit `QDRANT_URL`, so a cloud one-shot invocation must inject that URL
explicitly (alongside its server-side database key) until the deployment
overlay adds the binding. The v2 lab proof below exercises the self-hosted
server; it does not claim a write to a cloud tenant.

## Ordering, application, and recovery

Only `cursor.sequence`, compared within the same source partition and cursor
authority, orders facts. Source revision and Git SHA are provenance.

The planner is pure and the dev-lab command applies its decision as follows:

| Condition | Outcome |
| --- | --- |
| No current manifest or higher incoming sequence | `replace` with exact sorted delete/upsert sets |
| Same sequence and same batch ID | `noop` after live readback, or `repair` if drift is detected |
| Same sequence and different batch ID | `conflict` |
| Lower incoming sequence | `stale` |

Different source partitions or cursor authorities are not comparable. A→B→A
at increasing sequences restores A deterministically even when the third source
hash matches the first.

One durable artifact root is the cursor authority for this canary. A per-source
interprocess file lock covers current-state read, extraction, application,
readback, and pointer promotion. A Postgres tenant/source advisory lock also
serializes cooperating multi-host writers before any of the three derived
stores mutate. Operators must use the same artifact root and tenant/repository
namespace. Copying or discarding the root creates a different authority and is
not supported.

Postgres applies each source in a transaction. Memgraph is a derived index and
Qdrant is a derived semantic index; neither can participate in the Postgres
transaction. Qdrant rejects stale/conflicting cursors before the companion
stores mutate, writes document points first, and switches its retained source
manifest last. An interrupted cross-store apply can still be briefly partial.
The artifact current pointer advances only after Postgres, Memgraph, and Qdrant
all pass exact readback. Search additionally gates each Qdrant manifest against
that pointer, so an unpromoted generation is not served. Retrying from the same
artifact root deterministically reapplies or repairs the projection.

## Operator surface

```text
uv run python -m omniintelligence.code_projection ingest \
  --tenant-id <canonical-tenant-slug> \
  --root <mounted-repository-root> \
  --repository-id lab/<ticket>/<repository> \
  --path <repository-relative-source-path> \
  --artifact-root <durable-artifact-root>

uv run python -m omniintelligence.code_projection inspect \
  --tenant-id <same-canonical-tenant-slug> \
  --repository-id lab/<ticket>/<repository> \
  --path <repository-relative-source-path> \
  --artifact-root <same-durable-artifact-root> \
  --symbol <exact-qualified-name>

uv run python -m omniintelligence.code_projection tombstone \
  --tenant-id <same-canonical-tenant-slug> \
  --repository-id lab/<ticket>/<repository> \
  --path <repository-relative-source-path> \
  --artifact-root <same-durable-artifact-root>

uv run python -m omniintelligence.code_projection search \
  --tenant-id <same-canonical-tenant-slug> \
  --repository-id lab/<ticket>/<repository> \
  --artifact-root <same-durable-artifact-root> \
  --query <semantic-query> \
  --limit 5
```

Composition reads `QDRANT_URL`, or `QDRANT_HOST` plus optional `QDRANT_PORT`.
`QDRANT_API_KEY` is optional for the lab and requires an HTTPS URL when set.
`CODE_PROJECTION_QDRANT_COLLECTION`, `LLM_EMBEDDING_URL`,
`CODE_PROJECTION_EMBEDDING_MODEL`, and
`CODE_PROJECTION_EMBEDDING_MODEL_VERSION` pin the storage/model contract.

`ingest` emits a JSON receipt containing the replay decision, source and batch
IDs, artifact digests, three-store write counts, and verified readback counts
and ID-set digests. `inspect` proves an exact symbol, its deterministic labels,
and its relationships from the live read model. `search` returns tenant-filtered
metadata and a query SHA-256 receipt, never the raw query or source content.
`tombstone` proves zero source-owned data records in all three stores while
preserving immutable evidence and Qdrant's non-searchable cursor manifest.

Readback verifies every source-owned ID and endpoint, complete canonical
node/edge payload digests, label payloads, relationship
trust/confidence/context properties, batch identity, and policy/provenance
digests in Postgres and Memgraph. Qdrant readback separately proves exact
tenant/source/batch/document membership, model/vector identity, policy and
provenance digests, content-addressed bytes, and the retained cursor manifest.
All readback fails closed on missing, duplicate, stale, fabricated, or foreign
records.

## Tenant-aware v2 dev-lab execution proof

The v2 command was executed on 2026-08-14 inside the healthy existing
`omninode-runtime-effects` container. It used the injected Postgres, Memgraph,
Qdrant, and 1024-dimensional `text-embedding-qwen3` endpoint. No runtime
restart, Kafka publish, schema migration, new service, or hosted CI run was
used.

- The command created and validated the shared `code_semantic_v2` collection:
  named 1024-dimensional DOT vector, float32 storage, no multivector mode,
  model/version/9,990-basis-point re-embedding metadata, and keyword indexes
  for tenant, source, repository, and record kind. The tenant index reports
  `is_tenant=true`.
- Real `qdrant.py` extraction promoted 59 nodes, 104 edges, and 61 semantic
  documents. Real `materializer.py` extraction promoted 62 nodes, 106 edges,
  and 61 semantic documents. Every source passed Postgres, Memgraph, Qdrant,
  and artifact-current readback before promotion.
- Repeating `qdrant.py` returned `noop` with the identical batch ID, 59/104
  graph counts, 61 Qdrant documents, and the same document/point ID-set
  digests.
- Semantic search returned five verified metadata-only results for a
  Qdrant/vector-repair query. A second query returned ten results spanning both
  active files, all carrying exactly the requested tenant and repository.
- One tenant/source Qdrant vector was deliberately replaced with a wrong
  normalized vector. Identical ingestion returned `repair`, rewrote all three
  projections, and restored the original 61-point ID-set digest.
- The same `materializer.py` path was ingested under tenant
  `omninode-sibling`. It produced a disjoint source/batch/document identity and
  sibling-only search results. The primary tenant query returned only
  `omninode-dev`; the sibling query returned only `omninode-sibling`.
- Tombstoning the sibling source removed 62 nodes, 106 edges, and 61 searchable
  Qdrant documents. Its subsequent search returned zero results while the
  retained non-searchable source manifest preserved cursor sequence 2.
- An independent final read-only audit found 125 Qdrant points: 122 active
  documents, two active source manifests, and one sibling tombstone manifest.
  All payloads matched their canonical batches, all vectors were normalized
  1024-dimensional values with matching stored digests, tenant point-ID sets
  were disjoint, and no payload exposed source/content/query/credential fields.
  Postgres and Memgraph matched at 59/104 and 62/106 records with identical
  per-source ID-set digests. The production artifact loader closed all three
  current pointers and every raw, batch, semantic-document, transform, and
  evidence reference.

## Historical dev-lab execution proof (pre-v2)

The execution below predates the tenant-aware v2 identity migration and is
retained only as evidence for the underlying application path. It is not
runtime proof of the v2 tenant contract; v2 requires a fresh tenant-scoped
canary before production activation.

The hardened command was executed on 2026-08-14 inside the existing
`omninode-runtime-effects` container, with its injected Postgres and Memgraph
connections and durable `/app/data` volume. No service restart, Kafka publish,
model call, schema migration, collection creation, or new infrastructure was
used.

- Real `materializer.py` extraction wrote and read back 57 nodes and 100 edges
  in each store at cursor sequence 4 after the final integrity hardening.
- Real `extraction.py` extraction wrote and read back 63 nodes and 104 edges in
  each store without overwriting the first source.
- The final independent read-only audit found 120 distinct nodes and 204
  distinct edges across two current sources in each store. Full parsed node and
  edge payload digests matched between Postgres and Memgraph, with zero
  duplicates, missing fields, cross-source endpoints, or batch/repository
  mismatches.
- An identical replay returned `noop` with the same batch and ID-set digests.
- `inspect` resolved the exact
  `omniintelligence.code_projection.materializer.apply_code_projection` symbol,
  its source span, visibility, three deterministic labels, canonical payload
  digest, and its `defines` edge.
- After the exact namespaced Memgraph label payload for
  `materializer.apply_code_projection` was deliberately replaced with malformed
  JSON, the identical command returned `repair`, reapplied both stores, and
  restored the exact 57-node/100-edge readback and ID-set digests.
- Tombstoning `extraction.py` proved zero source-owned rows/nodes/edges while
  the materializer source remained exactly queryable; re-ingestion restored the
  63-node/104-edge projection at the next cursor sequence.
- The production artifact parser validated both current pointers, all ten
  historical canonical batches, and all six content objects with zero
  unresolved references or unreferenced content.

## Evidence and evolution

`tests/fixtures/code_projection/v2/replay_manifest.json` pins the tenant,
source, schema, transform, and batch hashes plus the exact no-network contract
test.
`code_projection_batch_v2.schema.sha256` is the portable handoff digest. Tests
rebuild every vector, verify exact bytes, exercise hostile parsing, and prove
duplicate/stale/conflict/replacement/tombstone behavior. They also cover real
extraction, source isolation, artifact integrity, concurrent-operator
serialization, drift repair, live-adapter readback, and command receipts.

Any compatible implementation must validate these serialized vectors without a
cross-package Python import. Any schema, identity, canonicalization, privacy, or
ordering change must add new versioned vectors rather than silently rewriting
v2.
