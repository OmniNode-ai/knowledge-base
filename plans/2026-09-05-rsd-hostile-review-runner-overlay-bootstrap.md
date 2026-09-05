---
type: plan
status: draft
date: "2026-09-05"
title: "Typed Runner-Side Contract Overlay Bootstrap for RSD Hostile Review"
topics: [configuration, ci, security, contract-overlay, secret-resolution]
refs: []
---

# Typed Runner-Side Contract Overlay Bootstrap for RSD Hostile Review

## Decision

The public RSD hostile-review workflow must not make GitHub Actions secrets,
ambient process configuration, or application defaults the authority for local
reviewer routing. Contract overlays own all configuration. Legacy
environment-file configuration is not an allowed fallback.

This plan replaces that authority with a typed, fail-closed provider-mediated
bootstrap. Public and governed contracts carry only opaque capability references
and logical credential references. They never contain a live endpoint, network
topology, port, credential, token, or secret-derived value. A private canonical
provider resolves those references only after a trusted workflow has proved its
identity and the signed overlay is valid; the provider, rather than a shared
Actions runner, performs the one reviewer execution in disposable containment.

No private overlay path, storage service, signer, GitHub App, provider executor,
or restricted runner entry point is claimed to exist today. Selecting those
authorities is an explicit prerequisite, not an implementation detail to invent
in a workflow.

## Pinned Evidence

| Surface | Pinned evidence | Current role and gap |
| --- | --- | --- |
| Public RSD | `97d07b584cf79c86ba393a702ecb63b1d1b85d16` | `.github/workflows/hostile-reviewer.yml` maps trusted-job Actions secrets directly into reviewer environment variables and invokes a local-review CLI. |
| Reviewer dependency | `12aaf67a782befad3e500b6b7d0fc3bc8826a0d9` | `omniintelligence` loads its packaged `review_pairing/model_registry.yaml`; its loader and adapter still permit ambient endpoint override/default resolution. |
| Runner infrastructure | `c901c57e636eba305731ad8dbcff3a7e1776cf9f` | `config/runner_fleet.yaml` has inactive opaque model-review reference IDs; `docker/runners/model-review-healthcheck.sh` consumes a sanitized observation; `docker/runners/entrypoint.sh` registers/supervises Actions runners. None bootstraps reviewer route/model/credential inputs. |
| Existing RSD overlay | same infrastructure revision | `docker/lane-overlays/dev.rsd-live-delegation.yaml` is schema `rsd_live_delegation_overlay.v1` and `runtime/rsd_live_delegation_overlay.py` loads an inert authorization preflight. It is not a CI reviewer bootstrap. |

The public RSD release validator correctly rejects topology and secrets in
repository source, but allowing GitHub-secret expression syntax merely prevents
false positive disclosure findings. It does not make a secret reference a
configuration contract.

## Authority Boundary

Endpoint/model routing and credential material have different authorities:

| Fact | Classification | Allowed representation in this plan |
| --- | --- | --- |
| Reviewer model slot and route selection | Nonsecret configuration | Stable model identity plus opaque route capability reference. |
| Endpoint address, protocol, port, and transport policy | Provider-resolved configuration | Never serialized into public/governed contract or receipt. |
| Shared transport authentication or provider Bearer material | Secret | Logical credential reference only; provider returns an ephemeral value to the bootstrap. |
| Runner eligibility and attestation | Governed policy/evidence | Signed runner identity, group/label constraints, freshness, and opaque reference-health facts. |

The implementation owner must select, document, and independently review all
of the following before code is written:

1. the private canonical provider that stores route and credential capabilities;
2. the signing/trust-anchor authority for runner overlays and runtime identity;
3. a provider-owned disposable executor, or (only if independently proven
   equivalent) a new repository-restricted ephemeral/JIT model-review runner;
4. the governed selection policy that maps a same-repository job to one signed
   overlay version; and
5. the operational owner that canary-deploys and revokes an overlay.

If any authority is absent, the result is a blocking design HOLD. A GitHub
secret, runner shell profile, or untyped variable must not fill the gap.

The current shared self-hosted fleet is categorically ineligible for this
protocol: it exposes Docker socket/control-group capability and has no supported
`bwrap`, rootless-container, or systemd-scope isolation boundary. It cannot be
used for a canary. The preferred authority is therefore a provider-owned
disposable executor with immutable image, no Docker socket, host mount,
workspace/cache reuse, or GitHub token, and restricted egress. A new
repo-restricted ephemeral/JIT model-review runner is an alternative only after
it demonstrates those same containment properties.

## Contract Schema

Introduce a strict, versioned `model_review_runner_overlay.v1` contract. Its
canonical JSON signature covers every field below, rejects duplicate keys and
unknown fields, and has an explicit issued-at and expires-at window.

```text
schema_version: "model_review_runner_overlay.v1"
overlay_id: UUIDv4
issued_at: exact UTC instant
expires_at: exact UTC instant
signer_key_id: opaque key identity
runner_policy:
  required_group: stable logical group name
  required_labels: sorted stable logical labels
  runner_identity_claim: signed identity digest/reference
reviewers:
  - slot: "primary" | "secondary"
    expected_model_identity: stable model identity
    route_capability_ref: opaque capability reference
    credential_ref: logical credential reference
    transport_policy_ref: opaque capability reference
signature: detached signature bytes
```

The schema must require exactly the reviewed slots and reject duplicate slots,
duplicate references, noncanonical timestamps, invalid identities, absent
signatures, expired overlays, and a model identity that does not match the
resolved capability attestation. It contains no endpoint fallback field and no
default-route field. A signer may rotate only through a separately signed trust
anchor transition; changing an identifier in a workflow is not a rotation.

The public source may package a schema and static policy fixture containing
synthetic opaque references. The actual signed overlay and provider records live
only in the selected private authority. Public release validation must reject a
real address, port, URL, credential, or secret-derived literal in either the
schema, workflow, tests, generated artifact, or receipt.

### Bootstrap Request Schema

The workflow submits a strict canonical `model_review_bootstrap_request.v1`,
not an open-ended JSON body. It contains only `schema_version`, UUIDv4 `run_id`,
decimal-string `repository_id`, and a bounded request nonce. There are no PR,
head SHA, diff, route, model, endpoint, credential, or override fields. The
provider rejects duplicate/unknown fields, aliases, noncanonical bytes, invalid
identities, and a reused nonce. Before any GitHub-App query or capability
resolution it requires exact equality:

```text
request.run_id       == verified_oidc.claims.run_id
request.repository_id == verified_oidc.claims.repository_id
```

The request cannot select authority; it merely identifies the already attested
workflow invocation. A request/OIDC mismatch is a zero-reviewer-call failure.

## Provider Bootstrap Protocol

The workflow is only a receipt verifier/gate. The provider is the typed
executable boundary, owned by runner infrastructure rather than RSD or the
reviewer library. It receives a signed identity request, obtains the diff itself,
and launches exactly one isolated pinned reviewer. It does not read arbitrary
environment variables for route or credential discovery.

1. The trusted same-repository job requests a GitHub OIDC token with only
   `id-token: write`, fixed audience
   `urn:omninode:model-review-bootstrap:v1`, and no reviewer credential. The
   provider verifies issuer and JWKS plus exact `repository_id`, `repository_owner_id`,
   `event_name=pull_request_target`, `runner_environment=self-hosted`, protected
   base, exact `workflow_ref`, allowlisted `workflow_sha`, time window, and a
   non-replayable `jti` tuple.
2. OIDC does not assert PR number or head repository. After exact request/OIDC
   equality, the provider uses its GitHub App/API to fetch the asserted run and
   its single associated PR. It requires the fetched run to equal the verified
   OIDC repository ID, owner ID, event name, workflow ref, workflow SHA, base
   ref/SHA, head SHA, and run ID; it then requires fetched base repository ID to
   match and fetched head repository ID to equal the base repository ID. The
   provider, never the workflow, pins the fetched head SHA and computes the
   diff digest. It re-fetches the run and PR immediately before launch and
   requires all of those pinned facts and the diff digest to be byte-identical.
   Any API multiplicity, cross-run substitution, changed fact, mismatch, or
   unavailable fact fails closed.
3. Only after those checks, select the overlay through the governed authority.
   Load strict bytes; verify schema version, canonical signature, signer trust
   anchor, issuance/freshness, and policy binding.
4. Resolve each opaque route capability and logical credential reference through
   the selected canonical provider. Require provider attestation that every
   route is healthy and returns the expected model identity. Reject substituted,
   stale, missing, duplicate, or extra facts.
5. Launch exactly one reviewer in the disposable executor with the pinned image
   and bounded fetched diff. The executor begins with no inherited descriptors,
   `close_fds=True`, and an explicit empty `pass_fds` allowlist except for a
   bounded read-only diff descriptor and, only when unavoidable, one short-lived
   credential descriptor. Every provider, GitHub-App, OIDC, control, and
   temporary descriptor is marked close-on-exec/non-inheritable and is absent
   from that allowlist. Standard input is `/dev/null`; standard output and error
   are dedicated bounded provider-owned pipes for sanitized capture, never the
   workflow terminal or log descriptor. Clear the child environment of
   route/credential ambient variables, close descriptors in `finally`, and
   never return resolved values to the workflow. On exit, deadline, setup
   failure, or signal, reap/destroy the executor and emit a sanitized result
   only.
6. Emit a provider-signed sanitized receipt containing overlay ID/version and
   digest, signer identity, OIDC/run/diff-binding digests, model identities,
   opaque reference digests, freshness verdict, child lifecycle/cleanup verdict,
   and outcome digest. It contains no resolved values.

Every failure before child creation produces zero reviewer transport calls.
Every failure after creation is terminal and fail-closed. There is no retry,
ambient lookup, model-registry default, Actions-secret fallback, or workflow
execution bypass path.

## Workflow Selection

Fork pull requests remain on hosted runners. They do not receive the private
overlay, local route capability, credential reference resolution, or trusted
runner bootstrap. A fork may run only a separately configured public,
credentialless review path with an explicit public contract; if that path is
not available, the hostile gate fails closed rather than silently using a local
default.

For a same-repository pull request, the base-controlled workflow may request the
fixed-audience OIDC token and call the provider. It does not receive route or
credential inputs and does not invoke the reviewer itself. Only a verified
provider receipt authorizes the hostile-review result. The workflow must remove
the three direct Actions-secret mappings and prohibit any reviewer-library
ambient/default local-route execution in the workflow.

The existing generic runner-selector fallback is not an authority-selection or
isolation mechanism. The workflow must fail closed until a provider executor or
new restricted ephemeral/JIT class is selected and attested; the current shared
fleet is never eligible.

## Migration and Rollback

1. **Authority decision.** Approve private provider, signer/trust anchor,
   bootstrap entry point, runner selection policy, and operator owner. Stop if
   this decision cannot name a canonical owner.
2. **Infrastructure contract.** Add the V1 schema, strict parser, signature and
   freshness verifier, provider protocol, and sanitized receipt model in runner
   infrastructure. The public `runner_fleet` reference remains opaque; no live
   route is added to a public file.
3. **Provider executor canary.** Build the bootstrap into the selected disposable
   provider executor (or independently qualified restricted JIT runner), deploy
   only a governed canary overlay, and prove OIDC/API identity, head/diff
   binding, isolation, model binding, cleanup, and receipt production before any
   RSD workflow depends on it.
4. **RSD workflow cutover.** Replace direct secret mappings and default route
   reliance with the OIDC provider call and receipt gate. Keep the
   base-controlled no-fork-checkout boundary and fail closed on any missing or
   invalid receipt.
5. **Reviewer hardening.** Remove or fence local-model ambient/default
   resolution for the bootstrap invocation in the pinned reviewer dependency.
   This is a separate compatibility review because the reviewer may have other
   callers.
6. **Revocation and cleanup.** Remove the obsolete Actions-secret configuration
   only after the cutover receipt and a clean hosted/fork proof. Revoke a bad
   overlay by selection-policy version, not by restoring a default endpoint.

Rollback selects the preceding still-valid signed overlay version through the
same provider and repeats the canary. It never restores direct workflow secret
mapping, ambient routing, or a default endpoint. If no valid version is
available, the hostile gate remains failed closed and the operator uses a
separately authorized manual review process.

## Test Matrix and Proof Receipts

Unit tests must prove:

- strict V1 parsing rejects unknown/duplicate fields, bad signatures, expired
  timestamps, cross-runner replay, duplicate reviewer slots, and model-identity
  substitution;
- an absent, unhealthy, stale, or mismatched opaque reference creates no child
  process and no transport call;
- only the selected two slots reach the child, and parent ambient values cannot
  authorize a route or credential;
- child setup failure, nonzero exit, timeout, and signal each reap the child,
  close owned descriptors, remove temporary material, and yield a sanitized
  fail-closed receipt;
- receipt serialization contains only approved identities/digests and is
  deterministic; and
- fork selection never requests private capability or credential resolution.

Adversarial protocol tests must also reject wrong audience, issuer/JWKS failure,
repository or owner mismatch, wrong event/runner/base/workflow ref/SHA, expired
or replayed `jti`, forged run ID, multiple/no associated PR, forked head,
head-SHA race, cross-run request substitution, fetched-run/OIDC fact mismatch,
fetched-fact revalidation TOCTOU, and diff-digest mismatch. Executor tests must
prove that socket, host mount, workspace/cache reuse, token inheritance, and
unrestricted egress are absent. They must enumerate the child descriptor table
and show that normal execution, setup failure, and signal termination leave only
the explicit standard streams plus approved diff/credential descriptors, with
all provider/GitHub-App/control descriptors close-on-exec and absent; the same
tests prove bounded stdio capture and environment scrubbing on every path.

Integration/canary tests must use an injected disposable provider with synthetic
references and verify bootstrap-before-review ordering, trusted runner identity,
model attestation binding, zero fallback, cleanup, and no residual child. They
must never connect to a shared lane or disclose real configuration.

RSD workflow tests must assert that no direct local-review secret mapping,
default-route branch, untyped route variable, or topology literal remains.
Public release, built-artifact, and exposed-identifier scans run on both
infrastructure and RSD changes. The final proof bundle records pinned source
revisions, schema digest, overlay/receipt digests, runner identity verdict,
model identity verdict, child cleanup verdict, and redacted test receipts.

## Acceptance Criteria

The change is ready for operator rollout only when an independently reviewed
canary produces a valid sanitized receipt on the selected runner, the same
workflow fails closed for every invalid authority fact, fork execution remains
credentialless and isolated, and public scans find no topology or secret
material. Until then, the existing RSD hostile-review configuration remains a
known authority gap rather than a basis for a live reviewer claim.
