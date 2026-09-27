---
type: plan
status: active
date: "2026-09-27"
title: "Shared delegation dispatch port: one protocol, one model, validators that read only their own repo"
topics: [delegation, protocol-layering, validators, pre-commit-hooks]
---

# Shared delegation dispatch port: one protocol, one model, validators that read only their own repo

## Goal

Replace two duplicated definitions of a delegation dispatch protocol (one per repo, with ad hoc
keyword arguments) with one shared request/result model pair and one shared protocol definition,
placed so that each consuming layer can actually import it. Migrate every implementation of that
protocol, not only the one in the provider repo. Replace the always-run pre-commit hook that
catches a mismatch between the two repos by reading one repo's live source tree from inside the
other's commit hook with a provider-local conformance check plus a consumer-side check. Neither
replacement reads a sibling clone.

The compat model shim's deletion is covered in this plan as Task F. It is an explicit core
implementation and core release, then consumer pin updates, then the compat deletion and release.

## Revision note

A review of the first version of this plan found three gaps, each verified against the live source
before this revision:

1. Task C migrated only the provider repo's implementation. The consumer handler selects among
   three implementations, and two of them live in the consumer repo. All three take keyword-only
   arguments today, so a `dispatch(request)` call site breaks the two that were left out with a
   `TypeError`. Task C now migrates all three, including their result conversion, and tests each
   path.
2. Task F deleted the compat models without ever giving them their permanent home. The design said
   the bodies move into core. Task F only repointed imports and deleted the compat module, which
   core's own re-export from Task A still imports. Task F is now a core implementation and release,
   then consumer pin updates, then the compat deletion. Its acceptance imports from installed
   release combinations instead of running a grep, and a negative control proves that the check
   fails when a model is missing.
3. Task D removed the provider-side check and replaced it only with consumer CI, which runs
   against a locked, already-published provider release. A provider regression could therefore
   ship before anything caught it. Task D now keeps a provider-local conformance check against the
   shared protocol alongside the consumer check.

Re-checking the release chain with these changes surfaced two ordering constraints that the first
version missed. They are recorded under "Release chain and dependency order": the provider's
parity gate has to be replaced before the consumer deletes its protocol copy, and consumers have to
import the models from the core path from the start.

## Existing-asset inventory

Paths and line numbers were read at the `dev` heads of each repo on 2026-09-27.

| Asset | Repo and file | State | Reuse or replace |
|---|---|---|---|
| `ProtocolDelegationDispatchPort` (consumer copy) | omnimarket `src/omnimarket/nodes/node_delegate_skill_orchestrator/handlers/handler_delegate_skill.py` (class at line 83) | keyword-only `dispatch(*, prompt, task_type, ..., no_escalation=False) -> dict[str, object]` | delete (Task C2) |
| the dispatch call site | same file, `HandlerDelegateSkill`, the call at line 952 | 19 explicit keyword arguments plus `**_no_escalation_dispatch_kwargs(request)` (helper at lines 145-163) | rewrite to build the request model (Task C2) |
| result conversion | same file, `_response_from_result` (line 620) and the cost/token/attempt helpers (lines 352-600) | read about 40 keys from an untyped `dict[str, object]`, several under two legacy names | retype to the result model (Task C2) |
| port selection | omnimarket `.../node_delegate_skill_orchestrator/ports/port_selection.py`, `select_delegation_dispatch_port` | `None` or in-memory bus: `LocalDelegationDispatchPort`. Any other bus: omnimarket's own `RuntimeDelegationDispatchPort`. A constructor-injected port bypasses selection | reuse unchanged |
| implementation 1, local | omnimarket `.../ports/port_local_delegation_dispatch.py`, `LocalDelegationDispatchPort.dispatch` (line 970) | keyword-only, returns `dict[str, object]` | migrate (Task C2) |
| implementation 2, market bus | omnimarket `.../ports/port_runtime_delegation_dispatch.py`, `RuntimeDelegationDispatchPort.dispatch` (line 82). Also constructed by `src/omnimarket/adapters/codex/local_runtime_dispatch.py` | keyword-only, returns `dict[str, object]` | migrate (Task C2) |
| implementation 3, injected infra | omnibase_infra `src/omnibase_infra/runtime/service_delegation_dispatch_port.py`, `RuntimeDelegationDispatchPort.dispatch` (line 255). The runtime injects it into the consumer handler as `dispatch_port` in `src/omnibase_infra/runtime/auto_wiring/handler_wiring.py` (line 8743) | keyword-only, carries an extra `output_schema_key` keyword the consumer never sends, returns `dict[str, object]` | migrate (Task C1) |
| `ProtocolDelegationDispatchPort` (provider copy) | omnibase_infra `src/omnibase_infra/runtime/protocols/protocol_delegation_dispatch_port.py` (line 27) | keyword-only, drifts from the consumer copy | delete (Task C1) |
| always-run parity hook | omnibase_infra `.pre-commit-config.yaml`, hook `onex-delegation-dispatch-consumer-kwarg-parity` (line 841), `always_run: true` | reads the consumer's handler source from a sibling clone (`omnimarket`) or an env-var path on every commit | delete, and replace with a scoped provider-local check (Task D1) |
| parity test module | omnibase_infra `tests/integration/runtime/test_delegation_dispatch_port_consumer_kwarg_parity.py` | parses the consumer's protocol and call site with `ast`. Marker `cross_repo_consumer` (registered in `pyproject.toml` line 524, deselected in `ci.yml` lines 2447/2478) | delete (Task D1) |
| parity CI workflow | omnibase_infra `.github/workflows/delegation-consumer-kwarg-parity.yml` | sparse-checks-out the consumer handler from the consumer repo's live `dev` branch on every PR. Context `consumer-kwarg-parity` is required through `scripts/ci/ci_summary_gate.py` (lines 486, 728) and routed in `config/runner_routing_policy.yaml` (line 1063) | delete together with both registrations (Task D1) |
| handler-compat test | omnibase_infra `tests/integration/runtime/test_delegation_dispatch_port_handler_compat.py` | drives the provider port only, reads no consumer source | keep, retarget to the request shape (Task C1) |
| provenance model | omnibase_core `src/omnibase_core/models/delegation/wire/model_delegation_provenance.py`, `ModelDelegationProvenance` | typed field of every dispatch today | reuse. See "Open premise" |
| core's dependency on compat | omnibase_core `pyproject.toml` `[project] dependencies` | **none.** Every `omnibase_compat` mention under `src/omnibase_core` is a comment about an earlier graduation, and core's compat parity tests use `importorskip` on an optional extra | Task A adds the edge and Task F1 removes it |
| compat retention convention | omnibase_compat `scripts/check_compat_retention.py` | requires `COMPAT_MIGRATION_TARGET` and `COMPAT_REMOVAL_DATE` on class-defining modules | reuse |
| core-resident protocol precedent | a documented layering exception for a protocol that core's own code must import directly | exists | reuse as the pattern for this protocol's exception entry |

## Out of scope

- Retrying already-failed delegations, and any change to the attempt-ladder or escalation logic.
- Any change to production delegation behavior. This is a structural and type-sharing fix.
- The compat package's eventual full retirement, beyond this one shim.

## Open premise (blocks Task A)

The request model has to carry `provenance: ModelDelegationProvenance | None`, and that type lives
in omnibase_core. omnibase_compat is forbidden from importing core, so a compat-homed request model
cannot type that field as written. The current ruling places the models in compat, and this plan
follows it. Task A does not start until an operator ruling settles one of these two options:

- **(a)** The models are born in core next to the protocol. They ship in the same core release
  Task B already needs. Task A shrinks to core only, and Task F has nothing left to do.
- **(b)** compat carries its own copy of the provenance model, which must then be kept equal to
  core's. That is a third copy of exactly the kind of definition this plan exists to remove.

Everything after Task A is written for the ruling as it stands. Under (a), Task F is dropped and
core's re-export becomes the definition itself. Nothing else in the chain changes, because every
consumer already imports from core's path.

## Design

1. **One shared model pair.** A request model and a result model replace the ad hoc keyword
   arguments at the dispatch call site: `dispatch(request) -> result`. Options such as the
   escalation-skip flag and the provider's `output_schema_key` become defaulted fields on the
   request, not keyword arguments. Every future dispatch option extends this shape, so a provider
   that does not yet know a new field simply sees its default. The result model's field set is the
   union of the keys the consumer handler reads today. Each implementation, not the handler,
   normalizes the legacy alias pairs into one canonical field each:
   - `failure_reason` to `error_message`
   - `model_used` to `model_name`
   - `delegated_to` to `provider`
   - `baseline_model` to `model_cloud_baseline`
   - `quality_passed` to `quality_gate_passed`
   - `prompt_tokens` and `completion_tokens` to `input_tokens` and `output_tokens`
2. **Model's home, now.** The shared structural package below core, as a declared temporary shim
   carrying the package's migration-target and removal-date annotations. This depends on the open
   premise above.
2a. **Core also gets the permanent import path now.** Core re-exports the two models in the same
   change as Task A, so one model body has two import paths. Core has no runtime dependency on the
   compat package today, so this change adds `omnibase-compat` to core's `[project] dependencies`.
   The pin has an upper bound that excludes the future compat release which deletes the shim
   (Task F3), so no resolver can ever pair this core release with a compat release that lacks the
   module it imports. **Every consumer imports the models from the core path from its first
   adoption (Task C).** No consumer ever imports the compat path, so Task F never has a window in
   which two repos hold two different classes.
3. **Protocol's home, now.** The core package, under one documented, named layering exception,
   because the validators that must use this protocol live in core and core cannot depend on the
   interface layer above it. The protocol is the single definition that all three implementations
   satisfy.
4. **Validators.** The validation engine and validators live in core. Each repo runs them against
   only its own source tree and its own locked, installed dependencies. None of them reads a
   sibling repo's working copy or another repo's live branch.
5. **Retire the always-run hook, and keep enforcement on both sides.**
   - **Provider side.** A conformance check local to the provider repo asserts that the provider's
     implementation satisfies the shared protocol, which it imports from its own locked core
     release. It runs in the provider's ordinary CI test split on every PR, and as a pre-commit hook
     scoped by `files:` to the implementation, its wiring, the models and the dependency manifests.
     It is never `always_run` and never reads a sibling clone. It catches a provider-side
     regression in the provider's own PR, before that release is published.
   - **Consumer side.** A test in the consumer repo drives the consumer handler with the provider's
     real implementation, imported from the consumer's locked provider release. It catches a
     provider upgrade that breaks the consumer in the PR that bumps the lock.
6. **Generalize the fix.** Apply the same shape to the other pre-commit hooks that unconditionally
   read a sibling repo's live source tree. A same-repo check gets scoped to the files it protects.
   A cross-repo check moves to a job owned by the repo that introduces the change, running against
   locked dependencies.
7. **Graduation, as its own follow-on.** Move the model bodies into core, so that core stops
   importing compat and drops the dependency, and release core. Bump every consumer's core floor to
   that release, then delete the compat copy and release compat. The order matters because each
   step is only safe once the one before it is installed everywhere (Task F).

## Release chain and dependency order

The chain is written as releases, because every seam below crosses a published package boundary.
R-names are placeholders for the concrete version each release step records.

1. **compat R-compat-1** (Task A1): the two models. Blocked on the open premise.
2. **core R-core-1** (Tasks A2 and B): the protocol, the model re-export, the new compat dependency
   (`>=R-compat-1`, upper bound below R-compat-2), and the layering-exception entry.
3. **infra R-infra-1** (Tasks C1 and D1, one PR or two PRs with D1 merged first). The provider:
   - pins R-core-1, which brings R-compat-1 transitively
   - adds the request path to its implementation, keeping a transition window for the old keyword
     call
   - deletes its own protocol copy
   - replaces the parity hook, test module and workflow with the provider-local conformance check
   **D1 must merge in the provider before C2 merges in the consumer.** The parity workflow reads
   the consumer's live `dev` branch and fails closed when the consumer's protocol class is absent.
   C2 deletes that class, so from then on every provider PR would go red on a required context.
4. **omnimarket R-market-1** (Tasks C2 and D2): the consumer pins provider `>=R-infra-1` and core
   `>=R-core-1`. The handler and both consumer-side implementations switch to
   `dispatch(request)`, the consumer's protocol copy is deleted, and the consumer-side test is
   added. The `>=R-infra-1` floor guarantees that the injected provider accepts the request shape.
5. **Lab step** (Task C3): a runtime image carrying R-infra-1 and R-market-1, with all three paths
   exercised, plus the mixed-version window check.
6. **infra R-infra-2** (Task C4): the provider's transition window closes. This happens only once
   the runtime image's lock resolves the consumer at `>=R-market-1`.
7. **Task E** starts after D1 and D2 have both run green on real PRs, once each.
8. **core R-core-2** (Task F1): the bodies move into core, core stops importing compat and drops the
   dependency.
9. **infra R-infra-3 and omnimarket R-market-2** (Task F2): core floors are bumped to `>=R-core-2`.
   These are pin changes only, because the import paths were already core paths from step 3.
10. **compat R-compat-2** (Task F3): the shim is deleted.
11. **Install matrix** (Task F4): the acceptance check over the released combinations.

Hard edges:

- 1 before 2, because the re-export imports the compat module.
- 2 before 3 and 4.
- D1 merged before C2 merged.
- 3 before 4, because of the consumer's provider floor.
- 4 before 5 before 6.
- 8 before 9 before 10 before 11.
- F1 can start once 4 is released, because no consumer imports the compat path. It does not wait
  for 5-7.

## Tasks

### Task A — the shared request/result models, plus the core re-export
- Blocked on the open premise.
- Files:
  - A1 (compat): a new module under `src/omnibase_compat/contracts/delegation/` carrying the
    request and result models, each with the `COMPAT_MIGRATION_TARGET` and `COMPAT_REMOVAL_DATE`
    annotations
  - A2 (core): a re-export module under `src/omnibase_core/models/delegation/`, plus the
    `omnibase-compat` dependency line in core's `pyproject.toml` with the bounded range from
    design step 2a
- Failing test first: a core test that imports both names from the core path and asserts that they
  are the same objects as the compat definitions (`is`). It fails until the re-export exists. A
  compat test constructs a request carrying every field the call site sends today and asserts
  their defaults. The field list comes from the consumer's dispatch call at line 952 plus the
  provider's `output_schema_key`.
- Minimal change: the models and the re-export only. No implementation changes yet.
- Focused test: compat's unit suite plus `scripts/check_compat_retention.py`, and core's unit suite
  scoped to the re-export module.
- Lab step: none. This is a structural change. A release build and an install check stand in for a
  lab pass.
- Acceptance -- falsifier: `check_compat_retention.py` exits 0. R-compat-1 and R-core-1 are
  published. In a fresh venv holding only R-core-1 installed from the package index, importing
  `ModelDelegationDispatchRequest` and `ModelDelegationDispatchResult` from core's path succeeds,
  and `uv pip show omnibase-compat` in that venv reports R-compat-1.

### Task B — the protocol in core, plus the layering exception
- Files: a new protocol module in core. It types `dispatch(request) -> result` against the models
  from Task A's core path. The change also adds one entry to the layering-exceptions document.
- Failing test first: a core test that imports the protocol and asserts that a minimal conforming
  stub satisfies it, while a stub with a keyword-only signature does not. The test uses a mypy
  structural assignment in a typed test module, so `mypy --strict` enforces it.
- Minimal change: the protocol only.
- Focused test: core's unit suite scoped to the new module, plus `mypy --strict` over it.
- Lab step: none.
- Acceptance -- falsifier: R-core-1 carries the protocol, and the negative stub makes the typed test
  module fail `mypy --strict`.

### Task C — migrate all three implementations and the call site to `dispatch(request)`

**C1 — provider (omnibase_infra, release R-infra-1).**
- Files:
  - `src/omnibase_infra/runtime/service_delegation_dispatch_port.py`: `dispatch` takes `request` as
    its first positional parameter and returns the result model, normalizing the legacy alias keys
    from design step 1 into canonical fields.
  - Transition window: when `request` is absent, the old keyword-only call is still accepted and
    still returns the old dict, because the deployed consumer is one release behind by
    construction. Passing both a request and keywords, or neither, raises `TypeError`.
  - `src/omnibase_infra/runtime/protocols/protocol_delegation_dispatch_port.py` is deleted, and
    every importer switches to core's protocol.
  - `src/omnibase_infra/runtime/auto_wiring/handler_wiring.py` is unchanged apart from the import.
  - `tests/integration/runtime/test_delegation_dispatch_port_handler_compat.py` is retargeted to
    the request shape.
  - Every provider test that calls the port's `dispatch` directly moves to the request shape.
- Failing test first: `tests/unit/runtime/test_delegation_dispatch_port_request_shape.py`. It
  covers four cases:
  - `dispatch(request)` returns the result model
  - the legacy keyword call returns the dict
  - both-or-neither raises
  - `request.no_escalation=True` reaches the published payload
  It fails until the request path exists.
- Focused test: the new module, the retargeted handler-compat module, and `mypy --strict` over the
  port.
- Acceptance -- falsifier: no `class ProtocolDelegationDispatchPort` remains under the provider's
  `src/`, and the new module's four cases pass in the provider's CI split.

**C2 — consumer (omnimarket, release R-market-1).**
- Files:
  - `handlers/handler_delegate_skill.py`: delete the protocol copy (line 83) and the
    `_NoEscalationDispatchKwargs` helper. The call at line 952 builds one request from the incoming
    skill request. `_response_from_result` and its helpers take the result model instead of a dict.
  - `ports/port_local_delegation_dispatch.py`: `LocalDelegationDispatchPort.dispatch(request)`
    returns the result model.
  - `ports/port_runtime_delegation_dispatch.py`: the consumer's own
    `RuntimeDelegationDispatchPort.dispatch(request)` returns the result model.
  - Both consumer implementations convert their current dict into the result model inside the
    port. They carry no transition window, because they ship in the same wheel as the handler that
    calls them.
  - Every importer switches to core's protocol and core's model path.
  - Every consumer test that calls either consumer implementation's `dispatch` directly (about
    fifty test modules reference the two ports) moves to the request shape.
- Failing test first:
  `tests/unit/nodes/node_delegate_skill_orchestrator/test_dispatch_request_three_paths.py`, with one
  test per selectable path. Each asserts that no `TypeError` is raised, that `no_escalation` and
  `provenance` travel as request fields, and that the typed result converts into the expected
  skill response:
  - **local:** `select_delegation_dispatch_port(None)` yields `LocalDelegationDispatchPort`, and a
    handler built with no injected port dispatches a request end to end against a stubbed effect.
  - **market bus:** `select_delegation_dispatch_port(<external-bus stub>)` yields the consumer's
    `RuntimeDelegationDispatchPort`. The published command carries the request's fields, and a fed
    terminal comes back as the result model.
  - **injected infra:** `HandlerDelegateSkill(dispatch_port=<omnibase_infra
    RuntimeDelegationDispatchPort over its in-memory transport>)`, with the provider imported from
    the consumer's locked R-infra-1. The handler dispatches through it and converts its result.
- Focused test: the new module, `tests/unit/nodes/node_delegate_skill_orchestrator/test_handler.py`,
  `test_runtime_dispatch_port.py`, the local-dispatch modules, and `mypy --strict` over the
  orchestrator package.
- Acceptance -- falsifier: the three-path module passes in the consumer's CI. No
  `class ProtocolDelegationDispatchPort` remains under the consumer's `src/`. Replacing any one of
  the three implementations with its pre-change keyword-only signature makes the matching path test
  fail with `TypeError`, which is the negative control, run once and recorded in the PR.

**C3 — lab.** Build a runtime image carrying R-infra-1 and R-market-1 on the shared lab runtime
lane, then exercise:
- one bus-less CLI delegation (local path)
- one delegation through the consumer's market-bus path
- one delegation through the runtime-injected provider port
- one delegation with R-infra-1 against the previous consumer release, which exercises the provider
  transition window

Acceptance -- falsifier: all four reach a terminal row with a typed result, and none terminates on
a `TypeError`.

**C4 — close the provider window (omnibase_infra, release R-infra-2).** Delete the legacy keyword
path and its test case. Start only when the runtime image's lock resolves the consumer at
`>=R-market-1`. Acceptance -- falsifier: a legacy keyword call to the port raises `TypeError`, and
the runtime image lock names the consumer at `>=R-market-1`.

### Task D — provider-local conformance plus consumer check; retire the always-run hook

**D1 — provider (omnibase_infra, lands with or before C1 and merges before C2).**
- Delete:
  - `.pre-commit-config.yaml` hook `onex-delegation-dispatch-consumer-kwarg-parity`
  - `tests/integration/runtime/test_delegation_dispatch_port_consumer_kwarg_parity.py`
  - `.github/workflows/delegation-consumer-kwarg-parity.yml`
  - the `consumer-kwarg-parity` entries in `scripts/ci/ci_summary_gate.py` and
    `config/runner_routing_policy.yaml`, deleted in the same change, because a registered context
    that no longer reports wedges the summary gate
  - the `cross_repo_consumer` marker and its two `ci.yml` deselections, if nothing else uses them
- Add `tests/unit/runtime/test_delegation_dispatch_port_conforms_to_shared_protocol.py`. It imports
  the shared protocol and models from the provider's locked core release and asserts all of the
  following:
  - `RuntimeDelegationDispatchPort` satisfies the protocol under a `mypy --strict` structural
    assignment
  - its `dispatch` parameters and return annotation equal the protocol's under `inspect.signature`
  - a real `dispatch(request)` over the in-memory transport returns the result model
  - a negative-control stub with a keyword-only `dispatch` fails the same helper
- Add a pre-commit hook `onex-delegation-dispatch-provider-conformance` running that module, with
  `files:` scoped to:
  - `src/omnibase_infra/runtime/service_delegation_dispatch_port.py`
  - `src/omnibase_infra/runtime/auto_wiring/handler_wiring.py`
  - the test module itself
  - `pyproject.toml`
  - `uv.lock`

  The last two catch a core or compat bump that changes the protocol or the models. The hook has no
  `always_run` and reads nothing outside the provider's tree and installed environment.
- The module carries no deselecting marker, so it runs in the provider's ordinary CI split on every
  PR. That is where the unconditional enforcement lives.
- Failing test first: the new module against the provider as it stands before C1 fails, because
  the port is still keyword-only.
- Acceptance -- falsifier:
  - the provider's `.pre-commit-config.yaml` no longer names the old hook, and names the new one
    with a `files:` pattern and no `always_run`
  - `ci_summary_gate.py` no longer lists `consumer-kwarg-parity`
  - a probe that adds a required keyword-only parameter to the provider's `dispatch` on a scratch
    branch makes the new module fail locally and in CI before any release

**D2 — consumer (omnimarket, lands with C2).**
- Add `tests/integration/delegation/test_injected_provider_dispatch_port_conformance.py`. It
  imports `RuntimeDelegationDispatchPort` from the consumer's locked provider release, asserts that
  it satisfies core's shared protocol, and drives `HandlerDelegateSkill` with it injected.
- The test runs in the consumer's ordinary CI split, so no paths-filtered required context is
  needed. It reads no provider working copy.
- Failing test first: the module, run against the provider release that predates C1 (a lock pinned
  back to it on a scratch branch), fails.
- Acceptance -- falsifier: that stale-lock probe exits non-zero, and the module passes on the
  consumer's real lock.

### Task E — generalize the fix to the other always-run sibling-reading hooks
- Files: each of the other pre-commit hooks that unconditionally read a sibling repo's live source
  tree, in the provider repo, the core package and the consumer repo.
- Failing test first: for each hook, a test that the hook is scoped to a file pattern rather than
  running unconditionally. It fails against the current configuration.
- Minimal change: give each same-repo check a `files:` scope. Move each cross-repo read to a check
  owned by the introducing repo, running against locked dependencies.
- Focused test: each repo's own pre-commit configuration test.
- Lab step: none.
- Acceptance -- falsifier: every listed hook's entry carries a `files:` pattern and no `always_run`,
  and no hook entry references a sibling-clone path or environment variable.

### Task F — graduate the models into core, then delete the compat copy

Task F cannot start before R-market-1, the first release in which no consumer imports the compat
path. Under open-premise option (a), Task F is dropped.

**F1 — core implementation and release (R-core-2).** Move the two model bodies into core's module
from A2, where they are defined in place rather than re-exported. Remove every
`omnibase_compat` import from core and the `omnibase-compat` line from core's `pyproject.toml`.
- Failing test first: a core test asserting that
  `ModelDelegationDispatchRequest.__module__` and `ModelDelegationDispatchResult.__module__` start
  with `omnibase_core.`, and that importing core's delegation package with `omnibase_compat`
  blocked from `sys.modules` still succeeds. It fails while the re-export stands.
- Acceptance -- falsifier: that test passes on R-core-2, and `uv pip show omnibase-core` for R-core-2
  lists no `omnibase-compat` requirement.

**F2 — consumer pin updates (R-infra-3, R-market-2).** Raise the core floor to `>=R-core-2` in the
provider and consumer `pyproject.toml` files and locks. Drop the direct compat pin wherever it
existed only for these models. There are no import-path edits, because C1 and C2 already use the
core path.
- Acceptance -- falsifier: each repo's lock resolves core at `>=R-core-2`, and the C2 three-path
  module and the D1 and D2 conformance modules pass on those locks.

**F3 — compat deletion and release (R-compat-2).** Delete the shim module and record the deletion
in compat's release notes. R-compat-2 is a minor bump, so R-core-1's upper bound excludes it.
- Acceptance -- falsifier: R-compat-2 is published, and `check_compat_retention.py` exits 0 with the
  module gone.

**F4 — installed-release import matrix (acceptance for all of Task F).** A script,
`scripts/check_delegation_dispatch_install_matrix.py` in core, runs in core CI path-scoped to the
model module and `pyproject.toml`. For each combination of released versions, it creates a fresh
venv from the package index:

- core in {R-core-1, R-core-2}
- compat in {R-compat-1, R-compat-2}
- provider in {R-infra-1, R-infra-3}
- consumer in {R-market-1, R-market-2}

Each combination is checked as follows:

- **combinations the resolver accepts:** import both models and the protocol from core's path,
  construct a request, import the provider's port and the consumer's handler, and assert that the
  provider's port satisfies the protocol
- **combinations that must be unresolvable:** assert that the resolver rejects them. Two
  combinations fall in this class: R-core-1 with R-compat-2, and R-infra-3 or R-market-2 with
  R-core-1
- **negative control:** a locally built compat wheel with the models deleted, paired with a locally
  built core wheel that still re-exports them. The script must exit non-zero on this pair, which
  proves that a missing model fails the check instead of passing it the way a grep would

- Acceptance -- falsifier: the script exits 0 over the released matrix and non-zero on the negative
  control, and both runs are recorded in the F3 PR.

## Doctrine gates

- **Rendered content, no placeholder counts:** each acceptance criterion names an exact test module,
  script or exit code. R-names are release placeholders that each release step replaces with the
  version it publishes.
- **Column ownership / multi-path writes:** not applicable. No shared writable column is introduced.
- **Model-before-build gate:** not applicable. No new lease, second writer or terminal-emitting
  component is introduced. The provider transition window (C1 to C4) is a bounded, named interval
  with its own closing task.
- **FAIL-not-WARN degradation:** the D1 and D2 checks and the F4 matrix fail closed, and each has a
  negative control that proves the non-zero exit.

## Adversarial pass (R1-R8)

- **R1 count integrity:** eight design steps (1, 2, 2a, 3-7), six tasks (A-F). Task C has four
  parts (C1-C4), Task D has two (D1, D2) and Task F has four (F1-F4). The release chain has eleven
  steps.
- **R2 criteria strength:** Tasks C, D and F moved from grep-based absence checks to behavioral
  tests with negative controls. Every surviving grep is paired with an executed test.
- **R3 scope:** each task's files match what its acceptance criterion can verify. Task C names all
  three implementations and the converter, Task D names both sides, and Task F names core's release
  as well as the deletion.
- **R4 integration traps:** three were found and are now handled:
  - the provider's parity workflow reads the consumer's live `dev` branch, which is what forces D1
    to merge before C2
  - core has no compat dependency today, so A2 adds it with an upper bound
  - the request model needs a core-typed field, which is the open premise
- **R5 idempotency:** the release and pin steps are idempotent. The hook replacement and the compat
  deletion are one-time structural changes.
- **R6 verification grade:** strong for C (per-path tests with a negative control), D (conformance
  tests with a probe) and F (the install matrix with a negative control). Medium for E (a
  configuration test per hook).
- **R7 expansion:** Task B's layering exception, and A2's temporary core-to-compat edge that F1
  removes, are each deliberate and documented.
- **R8 prerequisites:** the hard edges are listed under "Release chain and dependency order". A
  skipped step fails loudly: a pin that does not resolve, a required context going red, or a matrix
  combination that does not import.
