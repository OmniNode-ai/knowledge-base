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

The protocol and both models are born in the core package, in one core release. No part of this
plan places them in the shared structural package below core, and there is no shim to delete later.

## Revision notes

### Revision 2: core first

The open premise that blocked Task A in revision 1 is settled: the request and result models are
born in core, next to the protocol. The reason is structural. The request model must carry a
`provenance` field typed with core's `ModelDelegationProvenance`, the structural package below core
is forbidden from importing core, and core has no runtime dependency on that package today. A home
below core could only type the field by holding a third copy of the provenance model.

What changed:

1. **Task A now creates the protocol and both models in core,** plus the layering-exception entry,
   in one core release. Revision 1's Task B (the protocol alone) is folded into Task A, and the
   letter B is retired, so that Tasks C, D and E keep their letters.
2. **Every compat step is deleted:** the compat module and its retention annotations, core's
   re-export of it, the new core-to-compat dependency and its upper bound, and all of Task F (the
   graduation into core, the consumer pin updates for it, the compat deletion release, and the
   installed-release import matrix).
3. **The install matrix is dropped rather than rescoped.** Its subject was the compat seam: a core
   release that re-exports a module a later compat release deletes. Without compat, every remaining
   cross-release fact already has a test that runs on a real lock. The consumer's provider floor
   and the provider's request shape are checked by D2 on the consumer's lock. The provider's
   conformance to the protocol is checked by D1 on the provider's lock. The one mixed-version
   window that ships (a new provider with the previous consumer) is exercised in the C3 lab step.
   A matrix over core, provider and consumer releases would re-run those same assertions and test
   nothing new.
4. **The release chain is re-checked end to end** below. It is now six steps, down from eleven.

### Revision 1: review findings

A review of the first version of this plan found three gaps, each verified against the live source
before this revision:

1. Task C migrated only the provider repo's implementation. The consumer handler selects among
   three implementations, and two of them live in the consumer repo. All three take keyword-only
   arguments today, so a `dispatch(request)` call site breaks the two that were left out with a
   `TypeError`. Task C now migrates all three, including their result conversion, and tests each
   path.
2. Task F deleted the compat models without giving them their permanent home. Revision 2 removes
   the problem at its source: the models never live anywhere but core.
3. Task D removed the provider-side check and replaced it only with consumer CI, which runs
   against a locked, already-published provider release. A provider regression could therefore
   ship before anything caught it. Task D now keeps a provider-local conformance check against the
   shared protocol alongside the consumer check.

Re-checking the release chain surfaced an ordering constraint that the first version missed: the
provider's parity gate has to be replaced before the consumer deletes its protocol copy. It is
recorded under "Release chain and dependency order".

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
| provenance model | omnibase_core `src/omnibase_core/models/delegation/wire/model_delegation_provenance.py`, `ModelDelegationProvenance` | typed field of every dispatch today | reuse as the request's `provenance` field type (Task A) |
| delegation wire package | omnibase_core `src/omnibase_core/models/delegation/wire/` and its `__init__.py` | holds the canonical delegation wire models, including the provenance model | home of the two new models (Task A) |
| core runtime protocol package | omnibase_core `src/omnibase_core/protocols/runtime/` and its `__init__.py`, tests under `tests/unit/protocols/runtime/` | holds the core-resident runtime protocols | home of the new protocol (Task A) |
| core's dependency on compat | omnibase_core `pyproject.toml` `[project] dependencies` | **none,** and this plan keeps it that way | unchanged |
| core-resident protocol precedent | a documented layering exception for a protocol that core's own code must import directly | exists | reuse as the pattern for this protocol's exception entry (Task A) |

## Out of scope

- Retrying already-failed delegations, and any change to the attempt-ladder or escalation logic.
- Any change to production delegation behavior. This is a structural and type-sharing fix.
- Any change to the shared structural package below core. Nothing in this plan touches it.

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
2. **Models' home: core, from the start.** Both models live in core's delegation wire package,
   next to the provenance model that the request types its `provenance` field with. There is one
   definition and one import path. Every consumer imports the models from core from its first
   adoption (Task C), so no second class ever exists in any repo. Core gains no new dependency.
3. **Protocol's home: core, in the same release.** The core package, under one documented, named
   layering exception, because the validators that must use this protocol live in core and core
   cannot depend on the interface layer above it. The protocol is the single definition that all
   three implementations satisfy.
4. **Validators.** The validation engine and validators live in core. Each repo runs them against
   only its own source tree and its own locked, installed dependencies. None of them reads a
   sibling repo's working copy or another repo's live branch.
5. **Retire the always-run hook, and keep enforcement on both sides.**
   - **Provider side.** A conformance check local to the provider repo asserts that the provider's
     implementation satisfies the shared protocol, which it imports from its own locked core
     release. It runs in the provider's ordinary CI test split on every PR, and as a pre-commit hook
     scoped by `files:` to the implementation, its wiring and the dependency manifests.
     It is never `always_run` and never reads a sibling clone. It catches a provider-side
     regression in the provider's own PR, before that release is published.
   - **Consumer side.** A test in the consumer repo drives the consumer handler with the provider's
     real implementation, imported from the consumer's locked provider release. It catches a
     provider upgrade that breaks the consumer in the PR that bumps the lock.
6. **Generalize the fix.** Apply the same shape to the other pre-commit hooks that unconditionally
   read a sibling repo's live source tree. A same-repo check gets scoped to the files it protects.
   A cross-repo check moves to a job owned by the repo that introduces the change, running against
   locked dependencies.

## Release chain and dependency order

The chain is written as releases, because every seam below crosses a published package boundary.
R-names are placeholders for the concrete version each release step records.

1. **core R-core-1** (Task A): the protocol, both models and the layering-exception entry. Core's
   dependencies are unchanged.
2. **infra R-infra-1** (Tasks C1 and D1, one PR or two PRs with D1 merged first). The provider:
   - raises its core floor to `>=R-core-1`
   - adds the request path to its implementation, keeping a transition window for the old keyword
     call
   - deletes its own protocol copy
   - replaces the parity hook, test module and workflow with the provider-local conformance check

   **D1 must merge in the provider before C2 merges in the consumer.** The parity workflow reads
   the consumer's live `dev` branch and fails closed when the consumer's protocol class is absent.
   C2 deletes that class, so from then on every provider PR would go red on a required context.
3. **omnimarket R-market-1** (Tasks C2 and D2): the consumer raises its floors to provider
   `>=R-infra-1` and core `>=R-core-1`. The handler and both consumer-side implementations switch to
   `dispatch(request)`, the consumer's protocol copy is deleted, and the consumer-side test is
   added. The `>=R-infra-1` floor guarantees that the injected provider accepts the request shape.
4. **Lab step** (Task C3): a runtime image carrying R-infra-1 and R-market-1, with all three paths
   exercised, plus the mixed-version window check.
5. **infra R-infra-2** (Task C4): the provider's transition window closes. This happens only once
   the runtime image's lock resolves the consumer at `>=R-market-1`.
6. **Task E** starts after D1 and D2 have both run green on real PRs, once each.

Hard edges:

- 1 before 2 and 3, because both import the protocol and models from core's path.
- 2 before 3, because of the consumer's provider floor.
- D1 merged before C2 merged.
- 3 before 4 before 5.

Checked end to end, each release installs from the package index against only releases published
before it. Core depends on nothing new. The provider's core floor names R-core-1, which step 1
publishes. The consumer's provider floor names R-infra-1, which step 2 publishes, and R-infra-1's
own core floor is satisfied by the consumer's core floor. No step needs a later release to resolve,
and the provider and consumer lock files already pin core within a shared range, so raising both
floors to R-core-1 keeps them co-resolvable.

## Tasks

### Task A — the protocol and the request/result models, in core
- Repo: omnibase_core, one PR, released as R-core-1.
- Files:
  - `src/omnibase_core/models/delegation/wire/model_delegation_dispatch_request.py`:
    `ModelDelegationDispatchRequest`. Its fields are every argument the consumer's dispatch call
    sends today (the call at line 952 of the consumer handler, including `no_escalation` from the
    helper at lines 145-163), plus the provider's `output_schema_key`. Every option is a defaulted
    field. `provenance` is typed `ModelDelegationProvenance | None`, imported from the same
    package.
  - `src/omnibase_core/models/delegation/wire/model_delegation_dispatch_result.py`:
    `ModelDelegationDispatchResult`. Its fields are the union of the keys the consumer handler
    reads today, with one canonical field per legacy alias pair from design step 1.
  - `src/omnibase_core/models/delegation/wire/__init__.py`: export both models.
  - `src/omnibase_core/protocols/runtime/protocol_delegation_dispatch_port.py`:
    `ProtocolDelegationDispatchPort`, `@runtime_checkable`, with one method
    `async def dispatch(request: ModelDelegationDispatchRequest) -> ModelDelegationDispatchResult`.
    It is async because the consumer handler awaits every implementation today, inside
    `asyncio.wait_for`.
  - `src/omnibase_core/protocols/runtime/__init__.py`: export the protocol.
  - one new entry in the layering-exceptions document, naming this protocol module and following
    the existing core-resident runtime protocol precedent
- Failing tests first:
  - `tests/unit/models/delegation/wire/test_model_delegation_dispatch_request.py`: constructs a
    request carrying every field the call site sends today and asserts each default, including
    `no_escalation` false and `provenance` None. A second case asserts that an unknown field is
    rejected.
  - `tests/unit/models/delegation/wire/test_model_delegation_dispatch_result.py`: validates a
    result from a representative provider payload and asserts the canonical fields.
  - `tests/unit/protocols/runtime/test_protocol_delegation_dispatch_port.py`: a minimal conforming
    stub satisfies the protocol, and a stub with the old keyword-only signature does not. The
    check is a structural assignment in a typed test module, so `mypy --strict` enforces it, plus
    an `isinstance` check against the runtime-checkable protocol.
  All three fail until the modules exist.
- Minimal change: the two models, the protocol and the exception entry. No implementation changes.
  Core's `pyproject.toml` dependencies are not touched.
- Focused test: the three new test modules, plus `mypy --strict` over the three new source modules.
- Lab step: none. This is a structural change, and core is released on green `dev` CI. A release
  build and an install check stand in for a lab pass.
- Release step: cut R-core-1 from core's `dev` through the release train, and record the version in
  the Task A ticket.
- Acceptance -- falsifier:
  - R-core-1 is published.
  - In a fresh venv holding only R-core-1 installed from the package index, this import succeeds:
    `from omnibase_core.models.delegation.wire import ModelDelegationDispatchRequest, ModelDelegationDispatchResult`
    and `from omnibase_core.protocols.runtime import ProtocolDelegationDispatchPort`.
  - `uv pip show omnibase-core` in that venv lists no `omnibase-compat` requirement.
  - The negative stub in the protocol test makes the typed test module fail `mypy --strict`.

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

  The last two catch a core bump that changes the protocol or the models. The hook has no
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

## Doctrine gates

- **Rendered content, no placeholder counts:** each acceptance criterion names an exact test module,
  script or exit code. R-names are release placeholders that each release step replaces with the
  version it publishes.
- **Column ownership / multi-path writes:** not applicable. No shared writable column is introduced.
- **Model-before-build gate:** not applicable. No new lease, second writer or terminal-emitting
  component is introduced. The provider transition window (C1 to C4) is a bounded, named interval
  with its own closing task.
- **FAIL-not-WARN degradation:** the D1 and D2 checks fail closed, and each has a negative control
  that proves the non-zero exit.

## Adversarial pass (R1-R8)

- **R1 count integrity:** six design steps (1-6), four tasks (A, C, D, E; the letter B is retired by
  revision 2). Task C has four parts (C1-C4) and Task D has two (D1, D2). The release chain has six
  steps.
- **R2 criteria strength:** Tasks C and D use behavioral tests with negative controls rather than
  grep-based absence checks. Task A's acceptance is an import from a fresh install of the published
  release plus a typed negative stub. Every surviving grep is paired with an executed test.
- **R3 scope:** each task's files match what its acceptance criterion can verify. Task A names the
  exact core modules and tests, Task C names all three implementations and the converter, and
  Task D names both sides.
- **R4 integration traps:** two were found and are handled:
  - the provider's parity workflow reads the consumer's live `dev` branch, which is what forces D1
    to merge before C2
  - the request model needs a core-typed field, which is why the models are born in core
- **R5 idempotency:** the release and pin steps are idempotent. The hook replacement is a one-time
  structural change.
- **R6 verification grade:** strong for C (per-path tests with a negative control) and D
  (conformance tests with a probe). Medium for A (unit and typed tests plus an install check) and E
  (a configuration test per hook).
- **R7 expansion:** Task A's layering exception is deliberate and documented. No new cross-package
  dependency edge is introduced.
- **R8 prerequisites:** the hard edges are listed under "Release chain and dependency order". A
  skipped step fails loudly: a pin that does not resolve, or a required context going red.
