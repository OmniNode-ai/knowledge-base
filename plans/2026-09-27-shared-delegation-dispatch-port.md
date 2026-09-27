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
placed so that each consuming layer can actually import it, and retire the always-run pre-commit
hook that currently catches a mismatch between the two repos by reading one repo's live source tree
from inside the other's commit hook.

This plan covers the model, protocol and hook work as one unit. The compat model shim's eventual
deletion, once every consumer has swapped to the core re-export path, is tracked as a separate,
smaller follow-on covered by Task F below.

## Existing-asset inventory

| Asset | Repo | State | Reuse or replace |
|---|---|---|---|
| `ProtocolDelegationDispatchPort` (consumer copy) | omnimarket | exists, takes ad hoc `**kwargs` at the call site | replace |
| `ProtocolDelegationDispatchPort` (provider copy) | omnibase_infra | exists, signature drifts from the consumer copy | replace |
| `RuntimeDelegationDispatchPort` (concrete implementation) | omnibase_infra | exists, already accepts the newest keyword | reuse, retarget to the new signature |
| always-run consumer-kwarg-parity pre-commit hook | omnibase_infra | exists, reads the consumer repo's live source tree unconditionally on every commit | replace with a diff-scoped provider-side hook plus a consumer-side CI check |
| core-resident protocol precedent (a documented layering exception for a protocol that core's own code must import directly) | omnibase_core | exists | reuse as the pattern for this protocol's exception entry |
| shared structural package (below the core layer, no upstream runtime dependencies, explicitly a temporary-shim mechanism with a migration-target/removal-date convention) | omnibase_compat | exists | reuse as the model's temporary home |

## Out of scope

- Retrying already-failed delegations, and any change to the attempt-ladder or escalation logic.
- Any change to production delegation behavior; this is a structural/type-sharing fix.
- The compat package's eventual full retirement plan beyond this one shim (tracked separately).

## Design

1. **One shared model pair.** A request model and a result model replace the ad hoc keyword
   arguments at the dispatch call site: `dispatch(request) -> result`. An option such as an
   escalation-skip flag becomes a defaulted field on the request model, not a keyword argument.
   This is the shape every future dispatch option extends, so a provider that does not yet know a
   new field simply sees its default.
2. **Model's home, now.** The shared structural package below the core layer (zero upstream runtime
   dependencies), as a declared temporary shim: an explicit migration-target comment naming its
   permanent home and an explicit removal date, per that package's own retention convention. That
   package releases independently of the two consumer repos, so one release plus two pin bumps
   retires both duplicated definitions in one pass.
2a. **Core also gets a permanent import path for the model, now, not deferred.** The core
   business-logic package already depends on the shim package under this codebase's own layering
   (shim → core → interface layer → implementation layer), so core re-exporting the shim's model is
   an ordinary, sanctioned import — not a second exception alongside the protocol's. One model body,
   two import paths (the shim package's own path, and core's re-export of it), added in the same
   change as Task A below, so a consumer can start importing from core immediately instead of
   waiting for the later graduation step. This closes a gap an earlier pass of this design left
   open: without it, the shim module would carry a removal-date comment with no follow-on that ever
   acts on it (see step 7 and Task F).
3. **Protocol's home, now.** The core business-logic package — not the shared structural package
   (whose own contributor documentation reserves protocol interfaces for the interface layer above
   it, not for itself) and not that interface layer either, because the validators that must use this
   protocol directly live in the core package, and core cannot depend on a layer above it without
   creating a cycle. Landing the protocol in core takes one documented, named exception to the normal
   "protocols live in the interface layer" placement rule, following the same pattern already used
   for another protocol family that is deliberately core-resident for the same reason (validators in
   core need to import it directly). This is a now-step: the placement follows from which layer needs
   to import it, not from a later convenience.
4. **Validators.** The validation engine and the validators themselves live in the core package.
   Each consuming repo runs the shared validators against only its own source tree and its own
   locked, installed dependencies — never a sibling repo's working copy, and never another repo's
   live upstream branch. A shared base configuration covers the common case; each repo may carry a
   short, explicit override.
5. **Retire the always-run hook.** Once both the provider repo and the consumer repo adopt the
   shared model and protocol, delete the pre-commit hook that read the consumer's live source tree
   on every provider-repo commit. Replace it with a CI check owned by the consumer repo that imports
   the provider's real protocol and real implementation and compares call signatures against them
   directly, so a mismatch is caught in the very change that introduces it, not on some later,
   unrelated commit in the other repo.
6. **Generalize the fix.** Apply the same shape — scope a same-repo check to the files it actually
   protects, and move the check that reads another repo's live tree onto a CI job owned by the repo
   that introduces the change — to the other pre-commit hooks in this codebase that unconditionally
   read a sibling repo's live source tree on every commit, regardless of what that commit touches.
7. **Deferred cleanup, tracked as its own follow-on.** At a later, natural release boundary — once
   every consumer has swapped its import from the shim package's path to core's re-export path
   (step 2a) — move the model's body out of the temporary shim package into core directly, and
   delete the shim copy. This step has no hard dependency on Tasks A-E's ordering among themselves,
   but it cannot start before Task A (the shim model) and step 2a (the core re-export) both exist,
   since there is nothing to delete and nowhere to move the body to before then. Tracked as its own
   follow-on (Task F below) so the removal date on the shim module is backed by something that acts
   on it rather than sitting past due with nothing scheduled.

## Dependency order

Step 1 (the model/protocol shape) precedes steps 2, 2a and 3. Steps 2, 2a and 3 can proceed in
parallel once step 1 is settled, and 2a lands in the same change as step 2 (both are Task A). Step 3
depends on the layering-exception documentation entry landing in the same change as the protocol
itself. Step 4 (validators) can proceed independently once the shared base configuration exists; it
does not block or get blocked by steps 2/2a/3. Step 5 depends on both the provider and the consumer
repo completing steps 2/2a and 3. Step 6 depends on step 5's pattern being proven once, in this one
seam, before it is generalized. Step 7 depends on step 2a (the core re-export must exist before a
consumer can swap to it) and on Task C (both consumer repos must have adopted the shared model
before their compat imports can be deleted); it is not blocked by steps 5 or 6 and has no ordering
requirement relative to them.

## Tasks

### Task A — shared request/result model in the shim package, plus its core re-export
- Files: a new module in the shared structural package's models directory (request model, result
  model), each carrying the package's own required migration-target and removal-date annotations;
  a re-export module in the core package's own models directory that imports and re-publishes the
  same two model classes (step 2a) — added in this same task, not a later one, so a consumer never
  has a release where only the shim path exists.
- Failing test first: a test in the provider repo that constructs the new request model and asserts
  the provider's dispatch implementation accepts it — written against the not-yet-published shim,
  so it fails until the shim is released and pinned. A second failing test imports the models from
  the core re-export path specifically (not the shim path) and asserts they are the same classes
  (`is`, not just structurally equal) — fails until the re-export module exists.
- Minimal change: add the two shim models and the core re-export only; no behavior change to any
  dispatch implementation yet.
- Focused test: the shim package's own unit suite plus its retention-check script; the core
  package's unit suite scoped to the new re-export module.
- Lab step: none — this is a structural/type change with no runtime behavior difference; a release
  build and install check stands in for a lab pass here.
- Acceptance -- falsifier: the shim package's retention-check script exits 0 over the new models,
  a release tag is published carrying them, and an import of the two model class names from the
  core package's own source tree succeeds and resolves to the same objects the shim package defines.

### Task B — protocol in the core package plus the layering exception
- Files: a new protocol module in the core package; one new entry in the layering-exceptions
  document naming the protocol and the reason (validators in core must import it directly).
- Failing test first: a test that imports the protocol from the core package and asserts the
  concrete provider implementation satisfies it — fails until the protocol module exists.
- Minimal change: add the protocol only; do not yet remove either repo's own duplicated copy.
- Focused test: the core package's own unit suite scoped to the new module.
- Lab step: none — structural only.
- Acceptance -- falsifier: the protocol module exists in the core package's source tree, and the
  layering-exceptions document contains a matching entry.

### Task C — provider and consumer adopt the shared model and protocol
- Files: the provider repo's own dispatch protocol module and its concrete implementation; the
  consumer repo's handler module that currently builds ad hoc keyword arguments at the call site.
- Failing test first: the provider repo's existing signature-parity test, pointed at the new shared
  protocol instead of its own local copy — fails until the provider repo's pins are bumped and its
  local copy is removed.
- Minimal change: bump both repos' pins to the new shim and core releases; delete each repo's own
  duplicated protocol class; update the consumer's call site to build the shared request model
  instead of splatting keyword arguments.
- Focused test: each repo's own delegation-dispatch integration test, scoped to the changed module.
- Lab step: a single dispatch exercised end to end on the shared runtime lane, confirming the new
  request/result model round-trips through the real dispatch path.
- Acceptance -- falsifier: a repo-wide search for a second definition of the protocol class in
  either repo returns no hits.

### Task D — retire the always-run hook, add the consumer-side CI check
- Files: the provider repo's pre-commit configuration (remove the always-run hook and its test
  module); a new CI workflow in the consumer repo that imports the provider's protocol and
  implementation directly and compares signatures.
- Failing test first: the new consumer-side CI check, run against a deliberately stale pin of the
  provider's release — fails (as intended) until the check is wired to actually import and compare.
- Minimal change: delete the old hook; add the new check; no other behavior change.
- Focused test: the new consumer-side check's own test suite.
- Lab step: none — this is a CI/tooling change.
- Acceptance -- falsifier: the provider repo's pre-commit configuration no longer names the retired
  hook, and a probe run of the new consumer-side check against a stale pin exits non-zero.

### Task E — generalize the fix to the other always-run sibling-reading hooks
- Files: each of the other pre-commit hooks identified as unconditionally reading a sibling repo's
  live source tree (spread across the provider repo, the core package, and the consumer repo).
- Failing test first: for each hook, a test that the hook is scoped to a file pattern rather than
  running unconditionally — fails against the current configuration.
- Minimal change: add a file-pattern scope to each hook; add the equivalent consumer-side check
  where one does not yet exist.
- Focused test: each repo's own pre-commit configuration test.
- Lab step: none.
- Acceptance -- falsifier: each listed hook's configuration entry carries a `files:` pattern instead
  of an unconditional trigger.

### Task F — delete the shim copy once every consumer has swapped
- Files: the shim package's request/result model module (deleted); every consumer import statement
  that still names the shim path (repointed to the core re-export path from Task A); the shim
  package's changelog/release notes recording the deletion.
- Failing test first: a repo-wide grep for the shim import path, run before this task starts —
  returns hits (that is the starting condition this task exists to make return zero).
- Minimal change: repoint each consumer's import, delete the shim module, publish the shim release
  that ships without it.
- Focused test: each consumer repo's own unit suite scoped to the changed import; the shim
  package's own retention-check script (should no longer have this module to flag).
- Lab step: none — import-path and deletion change only, no runtime behavior difference once Task C
  has already proven the shared model/protocol round-trips through the real dispatch path.
- Acceptance -- falsifier: a repo-wide grep for the shim's import path across every consumer repo
  and the core package returns zero hits, and a grep for the model class definitions inside the
  shim package's own source tree also returns zero hits.
- Depends on: Task A (the shim model and its core re-export must exist) and Task C (both consumer
  repos must have adopted the shared protocol/model before their compat imports can be removed).
  Not blocked by Task D or Task E. Tracked as a separate follow-on to the main body of this plan
  rather than left as untracked prose, so its own removal-date obligation has something scheduled
  against it.

## Doctrine gates

- **Rendered content, no placeholder counts:** the acceptance criteria above name exact greps and
  exit codes, not "some" or "a few" hits.
- **Column ownership / multi-path writes:** not applicable — no shared writable column is introduced
  by this change.
- **Model-before-build gate:** not applicable — no new mechanism with a lease, more than one writer,
  or a terminal-emitting component is introduced. This is a type-sharing and validator-placement
  change over an existing, already-modeled dispatch call.
- **FAIL-not-WARN degradation:** the new consumer-side CI check must fail closed on a signature
  mismatch, never warn-and-continue (Task D's acceptance criterion states the non-zero exit
  explicitly).

## Adversarial pass (R1-R8)

- **R1 count integrity:** eight design steps (1, 2, 2a, 3-7), six tasks (A-F) — both counts checked
  against the lists above.
- **R2 criteria strength:** every task's acceptance criterion names an exact check (a script exit
  code, a grep with an expected hit count, a workflow file's presence) rather than "tests pass".
- **R3 scope:** each task's stated files match what its acceptance criterion can actually verify —
  no task claims to enforce runtime behavior through a documentation-only change.
- **R4 integration traps:** the exact protocol class name and its two current file locations are
  named in the existing-asset inventory; a follow-up resolves the exact module paths for the
  new shared model and protocol at implementation time, since those paths do not exist yet.
- **R5 idempotency:** Task A's shim release and Task B's protocol addition are both additive and
  re-runnable; Task C's pin bump is idempotent (re-running it against an already-bumped pin is a
  no-op); Task D's hook deletion is a one-time structural change with no rerun concern.
- **R6 verification grade:** Task A/B acceptance criteria are strong (exact script exit code, exact
  grep). Task C/D/E acceptance criteria are medium (grep-based absence checks) — acceptable here
  because the change is a deletion/rename, not a core invariant needing a strong proof.
- **R7 expansion:** Task B's layering exception is a deliberate, documented expansion of where a
  protocol may live; the document entry itself is the reconciliation record.
- **R8 prerequisites:** Task C cannot start until Tasks A and B have each published a release; Task D
  cannot start until Task C is complete in both repos; Task E cannot start until Task D's pattern is
  proven once; Task F cannot start until Task A's core re-export exists and Task C is complete in
  both repos (it deletes the compat imports Task C repointed). Each precondition is a hard dependency
  listed in the dependency-order section above, and an attempt to skip ahead fails loudly because the
  unmet pin or module simply does not exist yet to import. Task F is tracked as its own separate
  follow-on, blocked on this plan's Task A landing, rather than left as untracked prose, so its own
  removal-date obligation has something scheduled against it.
