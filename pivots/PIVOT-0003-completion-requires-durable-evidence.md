---
type: pivot
status: accepted
date: "2026-05-23"
title: "Completion Requires Durable Evidence"
observed_date: "2026-01-20"
confidence: high
topics: [evidence, completion, done-definition, receipts, verification]
refs:
  - doctrine/evidence-is-first-class-output.md
  - doctrine/truth-must-be-proven.md
  - adrs/ADR-0002-data-verification-invocation.md
---

# PIVOT-0003: Completion Requires Durable Evidence

## Original Assumption

A task is done when the code is merged and tests pass. The definition of completion was implicitly: code that was merged into the main branch, with a green CI status, had been verified. If the feature was described in a ticket, and a PR was merged that addressed the ticket, and CI passed, the ticket was done.

This assumption extended to feature validation. A feature that had a corresponding test was considered verified. A projection that had a corresponding unit test was considered correct. If the test passed, the feature worked.

The operational model treated CI as the final arbiter of correctness. What CI checked was correct. What CI did not check was assumed to be covered by the code change itself.

## Pressure Encountered

The assumption broke down repeatedly in a specific pattern: a ticket would be marked Done after a PR merged with green CI, and then the feature would be discovered to be broken in production days later — not because the code was wrong, but because the code's correctness in production depended on runtime state that CI never exercised.

The most concentrated example: a ticket marked Done after several PRs landed across multiple repositories with fully passing CI. The feature involved populating a projection with registered node data. The integration test verified that the count in the projection was greater than zero. The test passed. The projection was populated — with data from a stub, not from real node registration events.

Days after marking the ticket Done, the dashboard still showed stale garbage entries. The integration test had verified that the projection code path ran and produced output; it had not verified that the output reflected correct system state. "Tests pass" was true. "The feature works" was false.

A second pattern: code that was correct at merge time but whose correctness depended on downstream systems being configured correctly. The code was right. The runtime wiring was missing. CI passed because CI ran in an isolated environment without the runtime dependency. Production failed because the runtime dependency was not configured.

A third pattern: claims about system behavior that were based on reading test output rather than observing the running system. An agent reporting "feature X works" based on a test pass was not evidence that feature X worked; it was evidence that the test passed.

## Failure Modes Observed

**The integration test passes, the feature is broken.** Tests that verified "something was written to the projection" passed even when the projection contained garbage. The test checked `count > 0`; the production feature required the projection to contain accurate, current data from real events.

**The PR merged, the runtime is not wired.** Code that depended on Kafka topic subscriptions, environment variable configuration, or handler wiring was correct in isolation and non-functional in production because the runtime configuration was not updated.

**Agent self-reports without evidence.** Automated systems reported tasks complete based on successful function calls or test passes without verifying that the claimed output was present and correct in the running system. The claim existed in a log. The claimed state did not exist in the system.

**Ephemeral artifacts mistaken for evidence.** Build logs, scratch files, and local test runs were cited as completion evidence. These artifacts were not accessible after the run that produced them and could not be independently verified.

**DoD as checkbox, not gate.** Tickets had completion criteria listed as checkboxes. The checkboxes were checked off by the person marking the ticket Done. There was no mechanical gate that prevented marking Done when the criteria had not been met.

## Pivot

Completion requires durable evidence outside the originating workstation. Code merged and tests passing are necessary conditions for completion — they are not sufficient.

**Evidence is a first-class output.** Every operation that changes system state, every completion claim, every deployment must produce an artifact that is:
- Outside ephemeral runtime state (not a log, not a local file, not a build artifact)
- Accessible through approved system boundaries (not "trust the agent's report")
- Independently verifiable by a party other than the one making the claim

**The distinction between "tests pass" and "the feature works" is real.** Tests verify code logic in the test environment. Evidence verifies system behavior in the deployed environment. A test that passes in CI is not evidence that the feature works in production. A receipt that records a successful projection verification in the running system is evidence.

**Done gates must be mechanical.** A Done gate that depends on someone reading a checklist and deciding it is satisfied is not a gate — it is a ceremony. A Done gate that mechanically checks for the presence of required evidence receipts and refuses to advance the ticket until they exist is a gate.

**Self-signed receipts are advisory.** A receipt generated by the same system that performed the work it attests to has limited evidentiary value. Valid evidence has a verifier that is distinct from the runner, and the verification result is written to a durable control-plane surface.

## New Model

Completion has two layers:

**Layer 1 — Code correctness (CI gate):**
Code is merged. CI passes: unit tests, contract tests, type checking, lint. This layer confirms that the code is internally correct and does not break known contracts.

**Layer 2 — Operational evidence (Done gate):**
The feature produces durable evidence that it behaves correctly in the operational environment. Evidence types include:
- Projection snapshots confirming that the correct data is present in the deployed projection
- Event receipts from the runtime event bus confirming that the expected events were emitted
- Verification artifacts from data checks run against live databases
- Replay verification outputs confirming that the event sequence produces the expected state
- CI checks confirming that integration paths are wired correctly

Evidence must be stored in approved surfaces: receipts repositories, CI pipelines, committed manifests, or approved artifact storage. Evidence that exists only in agent logs or local files does not satisfy the Done gate.

The ticket is not Done until both layers are satisfied. Green CI is not sufficient. A self-assessed checklist is not sufficient. The evidence must exist and be independently accessible.

## Preserved Invariants

- Code review and CI remain required. Durable evidence supplements them; it does not replace them.
- The event log remains the source of record. Evidence artifacts are generated from or reference events in the log.
- Tests remain valuable. Unit tests and contract tests catch code-level errors early. The pivot is not an argument against tests; it is an argument that passing tests are not evidence of system correctness.

## Doctrine Impact

This pivot directly shaped the doctrine on evidence as a first-class output. The doctrine codifies that every externally visible operation, state transition, deployment, and completion claim must produce durable, inspectable evidence. It lists approved evidence surfaces and explicitly states that a task is not complete without durable evidence.

The truth-must-be-proven doctrine reinforces the underlying principle: status is not truth, logs are not truth, completion signals are not truth. Truth is established only when authoritative downstream state reflects the result, outputs are observable through approved boundaries, results survive replay, and durable evidence exists outside the originating workstation.

The data verification invocation ADR is a direct application: it defines the exact receipt format, storage location, and blocking semantics for one category of completion evidence, embodying the principle that advisory verification is not evidence.

## Related ADRs

- `adrs/ADR-0002-data-verification-invocation.md` — defines the canonical evidence format and blocking semantics for data verification receipts, explicitly rejecting advisory-only modes

## Related Deep Dives

The pressure that crystallized this pivot was the investigation following the platform registry incident: a feature marked Done after multiple PRs and passing CI, discovered broken in production when the dashboard still showed stale data. The root cause was an integration test that checked `count > 0` against a projection populated with stub data, passing silently while real node registration events were not reaching the projection.

## Evidence

The architectural change that demonstrated this pivot's correctness: after implementing mechanical Done gates backed by durable receipts, the pattern of "Done tickets with broken features" became detectable at ticket close time rather than days later in production. The rate of features marked Done but discovered broken declined significantly once the gate checked for evidence rather than trusting agent self-reports.

The counter-evidence that proved the old model was broken: multiple features were discovered broken days after the Done marker, in every case the CI that covered them had passed, and in every case the failure mode was runtime behavior that CI never exercised.

## Consequences

**Positive:**
- "Done" means something provable, not something claimed
- Broken features are discovered at close time rather than in production
- Evidence artifacts provide an audit trail for what the system was doing when a feature was completed
- Mechanical gates remove the dependency on human judgment about whether completion criteria have been met

**Negative / tensions:**
- The evidence requirement extends the time to Done. A feature that would previously be marked Done at PR merge now requires a deployment and verification pass before it can be closed.
- Evidence collection infrastructure must be built and maintained. The system requires working projection verification, receipt storage, and Done gate enforcement.
- The definition of "valid evidence" must be agreed on and encoded mechanically. Ambiguity about what counts as evidence becomes a blocking issue rather than an interpretive question.
- Some features genuinely cannot produce evidence until after deployment. The ordering implication — deploy first, verify second, mark Done third — is the correct order, but it requires the development workflow to accommodate it.
