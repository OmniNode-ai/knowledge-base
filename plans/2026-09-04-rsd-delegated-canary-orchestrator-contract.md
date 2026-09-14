---
type: plan
status: draft
date: "2026-09-04"
title: "RSD Delegated Canary Orchestrator Contract"
topics: [delegation, authorization, durable-lifecycle, dispatch]
refs: []
---

# RSD Delegated Canary Orchestrator Contract

## Decision

Introduce one orchestrator as the only supported durable delegated-canary
dispatch entry point. It owns authority verification, target-configuration
binding, durable preparation, one-time dispatch permission, and terminal
recording. The OpenAI-compatible adapter remains ledger-agnostic: it receives a
validated request and a short-lived dispatch permit, makes at most one bounded
non-streaming call, and returns a redacted outcome. It does not own a database,
an attestation signer, raw credential material, or recovery policy.

This is not authorization by a Python boolean, a public DTO, or a caller-made
projection. Raw signed grant, activation, and route-authority bytes plus their
distinct trust anchors are the sole authority inputs. The store owns trusted
time; the durable boundary derives and verifies facts itself, then persists only
the resulting redacted facts.

## Immutable Starting Evidence and Gate

| Artifact | Immutable reference | Role |
|---|---|---|
| current RSD main | `97d07b584cf79c86ba393a702ecb63b1d1b85d16` | required implementation base |
| activation and projection baseline | `28c0cc005f8caec669d519709d3e3dcf5099237a` | historical source of raw authority verification and the redacted projection |
| authority-bound ledger | `4ad1752051ad80a695f388cc6050705bbef31c6e` | design evidence only; **HOLD**, not an implementation base |
| ledger cumulative binary delta | `2882641928b8114f5ce92680564ad0e23aef70a32e822416fc31ed2b188f46b6` | pinned review artifact |
| transplanted adapter | `f05a8ac97c599725187b31ca32a215fcc8f42081` | adapter composition starting point |
| adapter binary delta from the ledger baseline | `39fab87286939ee6e06b6b96d6de5ede930ad6f9f39dffa03dc1b4545a088d76` | pinned review artifact |

The ledger is held because its public `prepare` and `mark_dispatch_started`
paths accept constructible projection/identity values without re-verifying raw
authority, do not prove expiration at dispatch-start time, and let callers
supply the terminal outcome trust anchor. No implementation may stack on that
ledger until all three defects below are remediated and independently reviewed.

## Canonical Target Configuration

Add `DelegatedOpenAICompatibleTargetConfigurationV1`, a strict immutable model
whose canonical JSON is the sole preimage for
`target_configuration_sha256`. Its exact fields are:

```text
schema_version: "rsd.delegated-openai-target-configuration.v1"
backend_id
model_id
route_ref
endpoint_ref
credential_ref
timeout_seconds
```

The digest is `SHA-256(domain || canonical_json(model))`, with a new fixed
domain separator owned by the target-configuration module. The model contains
only identifiers and logical references; it contains no URL, address, header,
credential, private key, prompt, response, or transport implementation detail.
`timeout_seconds` is bounded by the adapter's existing finite maximum.

The configuration intentionally excludes `route_authority_sha256`: activation
already commits the route-authority digest, so including it in a configuration
whose digest is signed by that authority would create a hash cycle. The signed
route authority commits the acyclic configuration digest. Raw verification
projects the same digest. Before any dispatch permission is issued, the orchestrator
recomputes the digest from the resolver-supplied exact model and requires it to
equal the verified projection and the signed route authority. It also requires
every model field to equal the adapter-bound target and timeout. A nested
directory, resolver alias, changed model, route, logical endpoint or credential
reference, or timeout is a refusal with zero transport
calls.

## Versioned Route Authority and Persisted Outcome Anchor

Do not mutate route authority V1. Add `DelegationRouteAuthorityV2` with the
separate `delegation-route-authority.ed25519.v2` signature domain. V2 carries
the acyclic target-configuration digest and the exact strict public
`DispatchOutcomeTrustAnchorV1` model itself as a signed field. The V2
canonicalization embeds that model using its canonical public serialization;
it does not accept a caller-supplied hash, key id, or fingerprint in place of
the model. Raw V2 verification derives all three persisted facts from that
signed field:

```text
outcome_trust_anchor_sha256 =
  SHA-256(outcome-anchor-domain || canonical_json(DispatchOutcomeTrustAnchorV1))
outcome_trust_anchor_key_id
outcome_trust_anchor_key_fingerprint_sha256
```

The derived three values must agree exactly with the embedded canonical anchor
model; they are never independent caller inputs. Raw V2 verification validates
the strict embedded model, recomputes its digest, derives its key id and
fingerprint, and emits all three values into the V2 projection. Preparation
persists the derived commitment and identity. At terminal time, the store asks
its injected trusted-anchor resolver for that stored identity, recomputes the
complete canonical returned `DispatchOutcomeTrustAnchorV1`, and requires
equality of the full anchor, derived digest, key id, and fingerprint before it
verifies the raw outcome attestation. An old V1 attempt, a row lacking all V2
anchor facts, or any resolver mismatch fails closed.

Add `DispatchOutcomeAttestationV2` under its own signature domain for V2
attempts. Its canonical signed facts include the exact activation identifier and
digest, route-authority digest, target-configuration digest, and complete
outcome-anchor digest in addition to the existing authorization, claim,
request, backend, model, route, terminal outcome, and replay facts. A V1
outcome attestation is not terminal evidence for a V2 attempt. This avoids an
attester signing an otherwise valid outcome that is detached from the exact
route target or activation lifetime it consumed.

## Authority and Durable APIs

Replace the constructible-projection authority inputs at the store boundary.
The store gains one raw-authority operation conceptually equivalent to:

```text
prepare_and_acquire_dispatch_permit(
  raw_signed_grant, raw_activation, raw_route_authority,
  grant_anchor, activation_anchor, route_anchor, target_configuration,
  run_id, attestation_id
) -> PreparedDispatchPermit | AlreadyStarted | Uncertain | Refused
```

The operation derives the claim internally from the raw signed grant and the
immutable packaged disabled policy, then invokes the canonical activation and
route V2 verifiers itself. A projection is an internal derived value used only
during the operation and for redacted persistence; it is never accepted from a
caller as proof. Terminal recording receives only raw signed outcome bytes and
stored/verifier-derived facts, never a caller-supplied claim or projection.
Exact public-model checks remain useful input validation, but they are not
authorization.

`PreparedDispatchPermit` is an opaque, module-private, single-use capability
created only after the transaction commits the prepared attempt and
`dispatch_started`. It carries no endpoint, credential, signing material, or
caller-controlled `verified` flag. The adapter verifies the raw authority again
at its entry and checks that the permit's immutable identifiers equal the raw
verification result. The package must not export a direct durable-lane adapter
entry point that can bypass this sequence. This is a trusted-runtime capability
boundary, not a claim that arbitrary hostile code already running in the same
Python process is sandboxed.

## Store-Owned Time, Expiry, and One-Call Semantics

The store constructor, not a per-call parameter, owns an injected trusted
exact-UTC time provider and a database-time provider. The latter obtains the
authoritative database transaction time after transaction initialization and
before any state transition. `prepare_and_acquire_dispatch_permit` begins its
transaction before its first query, acquires the canonical authorization/run
locks, and refuses unless `not_before <= database_now < expires_at`. In one
atomic transaction it persists the exact V2 attempt and writes
`dispatch_started`; it returns the one-use permit only after commit. Terminal
recording enforces the same stored lifetime against store-owned time before
persisting any receipt.

The permit carries the verified expiration and a dispatch deadline. The adapter
performs its final trusted-clock deadline check at the transport-call boundary;
the transport capability must enforce that deadline at its own request-entry
boundary as well. A timeout, expired permit, rollback, failed commit, or
ambiguous database result produces `Uncertain` and no call. `ALREADY_STARTED`
and `UNCERTAIN` are terminal recovery dispositions for this operation: neither
permits a resend.

This establishes a transaction-time proof for durable start. A database
transaction and an HTTP request cannot be made globally atomic. Therefore the
transport boundary must either enforce the signed expiration itself or use a
provider-side request contract that rejects expired authority. An implementation
that merely compares a clock before calling a generic transport does not meet
this plan's no-post-expiry-call invariant.

## Outcome Attestation and Terminal Recording

Terminal recording accepts raw signed `DispatchOutcomeAttestationV2` bytes and
redacted response/output material; it does not accept a caller timestamp,
caller-supplied outcome trust anchor, claim, projection, or caller-made receipt
as proof. It loads the anchor through an injected trusted-anchor resolver using
the persisted V2 identity, recomputes the complete canonical anchor digest, and
then cryptographically verifies the raw attestation before the terminal
transaction.
The attestation must match the stored authorization, claim binding, request,
backend, model, route, target configuration, activation/route anchor identities,
and attestation identity. Any absence, mismatch, duplicate replay identity, or
verification failure rolls back and fails closed.

The least-authority outcome-attester is an injected interface, not a private key
argument or boolean:

```text
attest_outcome(raw_verified_authority, dispatch_permit, redacted_outcome)
  -> raw_signed_outcome_attestation_bytes
```

It may issue one signed receipt only for the exact permit and redacted adapter
outcome. The orchestrator immediately submits those raw bytes to terminal
recording. It never persists signing input, a private key, endpoint, headers,
prompt, or raw response body.

## State Machine and Crash Recovery

| State / crash point | Required result | Later behavior |
|---|---|---|
| raw verification or target binding fails | `REFUSED` | no preparation and zero calls |
| transaction before commit fails | `UNCERTAIN` | no call; operator reconciliation only |
| prepare/start transaction reaches neither commit nor a known commit result | `UNCERTAIN` | no call; no automatic retry |
| prepared without `dispatch_started` | impossible by contract | preparation and start are one atomic transaction |
| dispatch-start commit succeeds, before adapter entry | `UNCERTAIN` | no resend; reconcile as possibly dispatched only if evidence appears |
| adapter returns or raises after one call | raw outcome handled once | submit exactly one terminal attestation path |
| attester fails or process dies after call | `UNCERTAIN` | no resend; reconcile against durable start and external evidence |
| terminal transaction fails | `UNCERTAIN` | no resend; a separately governed reconciliation may replay the identical signed receipt only |
| identical terminal receipt reappears | `IDEMPOTENT` | no second lifecycle event |
| divergent receipt or replay identity | `REFUSED` / conflict | no state overwrite |

The only normal call path is:

```text
raw authority verify → canonical target digest check → transaction-time prepare
→ committed STARTED permit → adapter re-verifies raw authority → one transport call
→ least-authority attester → raw-attestation verification → atomic terminal record
```

## Error Taxonomy

| Class | Meaning | Transport allowed? |
|---|---|---|
| `AuthorityRefused` | malformed, expired, unsigned, mismatched, or forged authority/target | never |
| `DurableConflict` | an identity exists with different durable facts | never |
| `AlreadyStarted` | a prior start is durable but outcome is unknown | never |
| `Uncertain` | a durable or external outcome is ambiguous | never automatically |
| `AdapterFailure` | one permitted call produced a finite redacted failure | no further call |
| `TerminalConflict` | raw signed receipt diverges from stored attempt or replay identity | never |

Errors must not retain endpoint values, headers, credentials, raw authority
bytes, prompts, response bodies, exception representations, or private key
material. Diagnostics use stable class names plus redacted digest/identity facts
only where those facts are already durable.

## Ownership and Migration Rules

- The orchestration module owns sequencing and recovery policy.
- The authority module owns raw signed grant derivation, V2 route verification,
  canonical target-configuration and outcome-anchor canonicalization.
- The adapter owns request projection, bounded one-call transport invocation,
  and strict response parsing; it stays ledger-agnostic.
- The ledger owns transactions, lock order, append-only lifecycle persistence,
  database-time expiry checks, stored authority facts, and raw terminal
  verification.
- The trusted resolver owns binding a logical target to a transport capability.
- The outcome-attester and anchor resolver are explicit injected authorities.

Migration ownership is external to runtime code. Add packaged append-only
migration `004`; never rewrite `003`. Migration `004` adds the V2 authority,
target configuration, exact signed outcome-trust-anchor commitment/identity,
V2 outcome-attestation
facts, lifetime, and permit
columns; establishes the necessary exact foreign keys and constraints; revokes
obsolete direct-write paths; and installs append-only UPDATE/DELETE/TRUNCATE
triggers for every affected ledger table. Existing rows without the complete V2
facts are deliberately unreadable for dispatch and terminalization: they fail
closed rather than receiving a guessed backfill. Never infer application state
from a source tree alone.

## Required Evidence

Unit tests must prove:

1. every target-configuration field and canonical serialization is pinned; one
   field change refuses before transport;
2. raw authority is verified inside the durable boundary; a constructible
   projection or claim cannot authorize preparation, start, adapter call, or
   terminal recording;
3. `not_before <= database_now < expires_at` at prepare/start, stored-lifetime
   terminal enforcement, adapter-entry expiration, and
   transport-entry expiration each produce zero calls;
4. only `STARTED` creates one permit and one call; `ALREADY_STARTED`,
   `UNCERTAIN`, rollback, and lock errors create zero calls;
5. the adapter receives and rechecks the exact activation, route, target,
   timeout, anchor, and permit identities; response parsing remains strict and
   non-streaming;
6. V1 is rejected for V2 execution; raw V2 verification derives the complete
   anchor, `outcome_trust_anchor_sha256`, key id, and fingerprint from its
   signed embedded anchor; an attester cannot sign for a changed authority or
   permit; terminal verification re-resolves and recomputes the persisted
   complete V2 anchor rather than accepting a caller argument. Full-anchor,
   key-id, and fingerprint divergence each fail closed before terminalization;
7. duplicate identical receipts are idempotent while changed receipt/replay,
   anchor, target, request, or attestation facts conflict;
8. each crash point produces the stated no-resend disposition and no leaked
   prompt, response, endpoint, header, or credential data.

Capability-gated disposable-PostgreSQL integration tests must prove canonical
lock order, transaction-time expiry, rollback, same-run serialization, stored
anchor lookup, terminal replay behavior, and append-only protection. They remain
skipped unless an isolated injected database factory is supplied; they must not
create fixtures in a shared database.

Acceptance requires strict typing, formatting/linting, public-release and
secret scans, package-artifact inclusion, the focused and full test suites, and
independent security review of the raw-authority, permit, and outcome-attester
boundaries.

## Rollout and Stacking Order

1. Land and independently approve the V2 signed grant, route-authority,
   projection, target-configuration, and complete outcome-anchor contracts with
   public vectors on current main.
2. Land the append-only migration `004` and the held ledger remediation:
   store-owned time, raw-only preparation, atomic prepare/start permit, stored
   lifetime, persisted V2 anchor, revokes, and append-only triggers.
3. Land the ledger-agnostic adapter update that accepts only the internal permit
   path and enforces the final deadline.
4. Land the orchestrator, injected attester, reconciliation surface, and
   end-to-end failure matrix as one reviewed composition change.
5. Publish a release artifact only after the acceptance evidence establishes
   that no legacy direct dispatch surface remains for the durable lane.

No step may be reordered to make the adapter callable before the durable start
permit and terminal-attestation authority are available.
