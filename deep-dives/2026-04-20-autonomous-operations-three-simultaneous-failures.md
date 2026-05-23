---
type: deep-dive
status: public-curated
date: 2026-04-20
title: "Autonomous Operations Under Three Simultaneous Infrastructure Failures"
period: "2026-04-19 to 2026-04-21"
topics:
  - autonomous-agents
  - infrastructure-resilience
  - measurement-discipline
  - failure-modes
  - overnight-operations
refs:
  - adr/ADR-010-agent-autonomy-limits.md
  - doctrine/01-deterministic-truth.md
  - doctrine/12-verification-before-completion.md
---

# 2026-04-20: Autonomous Operations Under Three Simultaneous Infrastructure Failures

## Summary

An autonomous overnight session ran against a known hazard inventory: the Kafka telemetry path was dead, the dispatch orchestrator was unwired and silently dropping published messages, and the runtime was running a stale image generating thousands of attribute errors per minute. This deep dive documents the discipline of writing explicit hypotheses before results are known, the failure modes that made the session different from prior overnight runs, and the architecture of trust that allowed meaningful work to proceed despite three simultaneous infrastructure failures. The most important architectural finding: systems that report success by default, rather than proving success, cannot be trusted for autonomous operations.

## Core Work

The day's operational session merged 31 pull requests across nine repositories, resolved the root cause of a complete merge-pipeline stall (a missing `enqueuePullRequest` mutation call that caused the merge-sweep skill to silently arm pull requests without actually queuing them), landed two structural fixes to the automated merge method, and diagnosed three distinct root causes that had been contributing to apparently unrelated symptoms.

Before the autonomous overnight session started, a pre-results document was written. It stated seven explicit hypotheses — each with a pass/fail criterion — about what the overnight session would accomplish. This was an intentional departure from the standard practice of writing deep dives after results are known. A document written after the fact cannot distinguish between "we predicted this would work" and "we rationalized that this worked after it happened." The pre-results discipline forced explicit commitments before outcomes were observable.

## Architectural Pressure

Three infrastructure subsystems were simultaneously degraded going into the overnight session:

**The Kafka telemetry path was dead.** The macOS operating system's local network access model grants network permissions per binary signature, not per Python version. Certain Python runtimes used for the event publisher did not hold the required local network permission, causing all Kafka connection attempts to fail silently with a socket error at the syscall level. No visible error was logged in the application layer — only the absence of published messages indicated the problem. Every telemetry event emitted by the merge-sweep automation was lost. The automation reported "complete" based on its own exit code, not based on whether Kafka received anything.

**The dispatch orchestrator was unwired.** The dispatch engine handler existed as code: a correctly-structured handler with a contract YAML, an entry point declaration, and test coverage. But it was not registered in any deployed runtime container's auto-wiring manifest. Every message published to the dispatch engine's input topic was consumed by no one. The topic's consumer group had zero active consumers. All dispatch commands were silently dropped. Forty-plus messages had been published before the silent drop was confirmed via consumer group state inspection.

**The runtime was running a stale image.** A bundle decomposition refactor had been merged to the infrastructure repository but not yet deployed. The running runtime container was importing a module path that no longer existed in the refactored codebase, producing an attribute error on every event it processed. The error rate was approximately 6,400 per 10 minutes — visible in health monitoring, but the symptom (high error rate) looked like a code bug rather than a deployment lag.

The combination of these three failures produced a system that appeared to be running normally by most operational metrics: the merge automation was running (it completed without crashing), the dispatch system was running (it completed without crashing), and the runtime was running (it was accepting connections and processing requests). The failures were only detectable by examining side effects: no Kafka events received, no dispatch commands consumed, no events processed without errors.

## Discoveries

**Systems that report success by default cannot be trusted.** The merge automation, the dispatch system, and the runtime container all reported operational status based on their own execution completing without an error. None of them had a mechanism for verifying that their intended side effects had occurred. A merge-sweep that emits zero Kafka messages and a merge-sweep that emits a hundred messages look identical in their exit codes. This is the same failure mode as the silent projection failure — success is reported based on "ran without crashing" rather than "produced the expected outcome."

**A pre-written hazard inventory creates a different kind of accountability.** The documented failure modes — dead Kafka path, unwired dispatch orchestrator, stale runtime image — were not surprises. They had been diagnosed before the overnight session started. The hazard inventory did two things: it allowed the team to design around the failures (using direct CLI calls instead of relying on Kafka telemetry) and it created a testable prediction surface (if H1 fails, fall back to documented alternative path). A session that runs without a hazard inventory either discovers these failures during the session (expensive) or never discovers them at all (dangerous).

**Different failure modes have different recovery paths.** The dead Kafka telemetry path was a hardware permission issue requiring a specific binary to hold the correct OS permission. The dispatch orchestrator being unwired was a deployment configuration issue requiring a manifest update and redeploy. The stale runtime image was a deployment lag requiring the merged changes to be built and deployed. All three look similar from the outside (something isn't working) but require completely different interventions. Conflating them would produce incorrect fixes.

**Retrospective narratives miss the distinction between prediction and rationalization.** A deep dive written after a successful overnight run has no way to distinguish "we correctly predicted that the critical-path merge would complete before the next autonomous cycle" from "the critical-path merge happened to complete and we described it as if we had planned it that way." The pre-results hypothesis format makes this distinction explicit and testable.

**The `gh` CLI is a more reliable primary execution path than Kafka-based automation when Kafka telemetry is degraded.** The merge automation is designed to use Kafka for coordination and telemetry. When Kafka is unavailable, the automation falls back to direct GitHub API calls. This fallback was intentional and worked: 31 pull requests merged in a session where zero Kafka telemetry events reached the broker. The lesson is that the primary execution path (merging pull requests) and the telemetry path (reporting what was merged) should be independent, so that telemetry failures do not block primary execution.

## Decisions Made

**Pre-results hypothesis documents are required for autonomous overnight sessions.** Sessions operating without human oversight must document their hypotheses before results are known. The format: explicit hypothesis statements, pass/fail criteria, fallback paths for each failure mode. This creates a measurement discipline that post-hoc write-ups cannot provide.

**Success verification must check side effects, not exit codes.** Any automation that reports status based on its own exit code, without checking whether its intended side effect occurred, is reporting an unreliable status. The required verification step is: after an action, confirm the expected side effect via an independent channel. After a merge attempt, confirm the pull request state via a direct API call. After a deployment, confirm the running container version via a health endpoint. After a Kafka publish, confirm message receipt via consumer group offset progression.

**Consumer group inspection is the ground truth for dispatch confirmation.** Whether a dispatch command was consumed cannot be inferred from the publisher's success status. The authoritative source is the consumer group state: zero consumers means the message was dropped, regardless of what the publisher reported.

**Hazard inventories must be written before autonomous sessions, not discovered during them.** Known infrastructure degradations, configuration gaps, and deployment lags should be documented as hazards before an autonomous session begins. The session then operates with explicit knowledge of its constraints rather than discovering them mid-execution.

## Candidate ADRs

- Pre-results hypothesis discipline for autonomous sessions: written before execution, evaluated against actual outcomes
- Success verification via side effect checking: exit codes are necessary but not sufficient
- Independent execution and telemetry paths: telemetry failures must not block primary execution

## Candidate Pivots

The recurring pattern across multiple incidents — silent projection failures, unwired dispatch handlers, stale runtime images, dead telemetry paths — all share the same root: systems that report operational status based on their own internal state rather than on verifiable external outcomes. The platform pivot is to make verification first-class: every system that performs an action must be capable of confirming that the action's expected outcome occurred, independent of whether its own execution completed.

## Related Doctrine

- **Section 1 (Deterministic Truth):** The dispatch orchestrator published to a topic with no consumers and reported success. This is the antithesis of deterministic truth — the system's self-reported state diverged from observable reality. The doctrine requires that truth be provable through external verification, not self-report.
- **Section 12 (Verification Before Completion):** No automated action is complete until its outcome is verified through an independent channel. This applies to merges, deployments, dispatch commands, and any other operation with a side effect.

## Related Evidence

- Consumer group state inspection: zero consumers on dispatch topic confirmed message drops
- Kafka telemetry path diagnosis: socket-level connection failures with no application-level error
- Runtime attribute error rate: 6,400 errors per 10 minutes in health monitoring output
- Post-redeploy verification: attribute error rate dropped to zero within minutes of deploying the updated container

## Open Questions

- What is the right signal for "the autonomous session produced meaningful work"? Currently this is assessed by examining merged pull request counts. A more rigorous definition would include verification that merged code produced its intended side effects (tests passing in CI, projections writing to databases, health checks improving).
- How should the hazard inventory surface be structured? Currently it is a prose section in a document. A structured format that could be parsed and checked against current system state would be more operational.

## Follow-up Work

- Build an infrastructure health pre-check that runs before any autonomous session and reports known degradations
- Add side-effect verification steps to the merge automation: after arming a pull request, verify that it entered the merge queue
- Add consumer group state to the dispatch system's operational status reporting
- Formalize the pre-results hypothesis format as a template for overnight session planning
