# Architecture Decision Records

Architecture Decision Records (ADRs) are the formal decision ledger for OmniNode. Each ADR captures a specific architectural decision, the context that forced it, alternatives considered, and consequences.

## ADR Lifecycle

```
Proposed → Accepted → Superseded
              ↓           ↓
         Deprecated    (by newer ADR)
              ↓
          Rejected
```

### States

| State | Meaning |
|-------|---------|
| **Proposed** | Decision identified, under review — not yet in effect |
| **Accepted** | Decision ratified and actively governing the codebase |
| **Superseded** | Replaced by a newer ADR; links to its successor |
| **Deprecated** | No longer relevant but not replaced by a newer decision |
| **Rejected** | Considered and explicitly not adopted |

A decision moves from `Proposed` to `Accepted` via PR review. When a later ADR renders an earlier one obsolete, the earlier ADR is updated to `Superseded` with a `superseded_by` frontmatter link and the new ADR lists the older one in `supersedes`.

## How ADRs Relate to Other Artifacts

OmniNode uses four artifact types that work together:

- **Doctrine** — the principles and invariants that constrain all decisions. ADRs must not contradict doctrine; when they appear to, the doctrine must be updated first with explicit rationale.
- **Pivots** — explain why understanding changed, often triggering the need for a new ADR. A pivot identifies the insight; an ADR records the decision that follows from it.
- **Evidence** — validates that decisions produce their intended consequences. DoD receipts, integration test results, and projection snapshots live in OCC (`onex_change_control`), the sole evidence authority; an ADR cites the outcome (a PR, a CI run, an OCC receipt) rather than hosting it here.

The typical flow: an incident or operational pressure surfaces a gap → a pivot records the insight shift → an ADR formalizes the decision → a cited outcome proves the decision had the intended effect.

## How to Propose a New ADR

1. Copy `_template.md` to a new numbered file: `ADR-NNNN-descriptive-name.md`
2. Fill in all frontmatter fields (especially `topics`, `refs`, `supersedes`)
3. Set `status: proposed`
4. Complete the body sections: Context, Decision, Alternatives Considered, Consequences
5. Open a PR for review; link the relevant Linear ticket in the PR body
6. On approval, change `status` to `accepted` and update any superseded ADRs

Keep ADRs narrow — one decision per ADR. If the decision requires background explanation that would exceed ~400 words, trim it to what the decision needs — this repository does not carry a narrative-journal section to defer background into.

## Cross-References

Some ADRs build directly on others:

- **ADR-0004** follows from **ADR-0003**: once the registration/runtime/registry boundary was defined (ADR-0003), the consumer surface question required its own decision (ADR-0004).
- **ADR-0007** follows from **ADR-0005**: the same ambiguity that forced ADR-0005 (duplicate canonical source for dispatch lifecycle) recurred for skills migration plans, motivating the same pattern resolution.
- **ADR-0006** is architecturally adjacent to **ADR-0007**: both define where shared validator/migration logic lives in the repo layer hierarchy.

## Current ADRs

> **Known identifier collision — `ADR-0010`.** Two records below both carry
> `adr_id: ADR-0010` ("Adaptive Recursive Contract Bisection" and
> "Enforcement and Merge-Policy Parity Ratchet"). An ADR identifier is a
> published public reference, so renumbering it is a decision-record-owner
> call, not a unilateral edit — this table flags and indexes both files
> rather than picking a winner. `scripts/validate.py`'s `adr_id` uniqueness
> check tracks this exact pair as a known, pending exception; any other
> collision still fails validation.

| ID | Title | Status | Date | Topics |
|----|-------|--------|------|--------|
| [ADR-0001](ADR-0001-dependabot-approval-manual.md) | Dependabot PR Approval Remains Manual | Accepted | 2026-03-25 | ci, dependabot, automation, github-actions |
| [ADR-0002](ADR-0002-data-verification-invocation.md) | Data Verification Node Invocation Policy | Accepted | 2026-04-23 | data-verification, dod, kafka, receipts, evidence-gates |
| [ADR-0003](ADR-0003-registration-runtime-registry-boundary.md) | Registration Runtime / Registry Boundary | Accepted | 2026-04-23 | registration, runtime, registry, projections, architecture-boundary |
| [ADR-0004](ADR-0004-registry-owned-consumer-surface.md) | Registry-Owned Consumer Surface | Accepted | 2026-04-23 | registry, projections, consumer-surface, api, architecture-boundary |
| [ADR-0005](ADR-0005-dispatch-lifecycle-canonical.md) | Dispatch Lifecycle Canonical Source | Accepted | 2026-04-28 | dispatch, lifecycle, fsm, event-bus, canonical-model |
| [ADR-0006](ADR-0006-skill-liveness-validator-home.md) | Skill Liveness Validator Home | Accepted | 2026-04-28 | validators, skills, architecture-layers, pre-commit, ci |
| [ADR-0007](ADR-0007-skills-canonical-plan.md) | Canonical Skills Migration Plan | Accepted | 2026-04-28 | skills, migration, planning, canonical-source |
| [ADR-0008](ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md) | Delegation Config Authority and Budget-Aware Tier Cost | Proposed | 2026-06-18 | delegation, config-authority, cost-model |
| [ADR-0009](ADR-0009-complexity-aware-delegation-routing.md) | Complexity-Aware Delegation Routing | Proposed | 2026-06-18 | delegation, routing, complexity, learned-routing |
| [ADR-0010](ADR-0010-adaptive-recursive-contract-bisection.md) | Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure) | Proposed | 2026-07-06 | rsd, decomposition, delegation, local-first, contracts, micro-factories |
| [ADR-0010](ADR-0010-required-context-parity-ratchet.md) | Enforcement and Merge-Policy Parity Ratchet | Proposed | 2026-07-10 | ci, branch-protection, enforcement, parity, governance, merge-gates, required-status-checks, merge-queue, config-as-data |
| [ADR-0011](ADR-0011-rsd-recursive-system-design-naming.md) | Name the Discipline RSD = Recursive System Design | Proposed | 2026-07-06 | rsd, naming, recursive-system-design, pipeline-fill |
| [ADR-0012](ADR-0012-seams-first-class.md) | Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing | Proposed | 2026-07-06 | rsd, seams, tdd, tree-pr-composition, selective-testing, ws-t |
| [ADR-0013](ADR-0013-deterministic-fsm-control-plane.md) | No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators | Proposed | 2026-07-06 | rsd, fsm, control-plane, determinism, gates, archetypes |
| [ADR-0014](ADR-0014-factory-economics-frontier-fissions-locals-build.md) | Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug | Proposed | 2026-07-06 | rsd, economics, delegation, disposable-implementations, distillation |
| [ADR-0015](ADR-0015-steel-live-play-non-deterministic.md) | Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic | Proposed | 2026-07-06 | steel-onslaught, llm, non-determinism, local-first, golden-fixtures |
| [ADR-0016](ADR-0016-one-contract-configured-pilot.md) | One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy | Proposed | 2026-07-06 | steel-onslaught, pilot, contracts, archetypes, rule-7a |
| [ADR-0017](ADR-0017-no-deterministic-champion-llm-pilots.md) | No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots | Proposed | 2026-07-06 | steel-onslaught, learning-loop, llm-pilots, non-determinism, evolutionary-search |
| [ADR-0018](ADR-0018-delegation-graded-benchmark-ladder.md) | Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling | Proposed | 2026-07-04 | delegation, benchmark, graded-eval, local-first, tier-separation |
| [ADR-0019](ADR-0019-no-self-authored-evidence.md) | No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only | Proposed | 2026-07-06 | evidence, occ, verification, doctrine, receipt-gate |
| [ADR-0020](ADR-0020-branch-preview-verification.md) | Branch-Preview Verification (proof_class=branch-preview) | Proposed | 2026-07-06 | verification, dev-lane, proof-class, pre-merge, evidence |
| [ADR-0021](ADR-0021-beta-ships-first-priority-lock.md) | Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes | Proposed | 2026-07-06 | prioritization, beta-launch, ws-b, planning, roadmap |
| [ADR-0022](ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md) | Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency) | Proposed | 2026-07-07 | build-efficiency, ci, pre-commit, occ, evidence-only, shift-left |
| [ADR-0023](ADR-0023-remove-occ-merge-queue.md) | Remove the onex_change_control Merge Queue | Proposed | 2026-07-07 | merge-queue, occ, ci, throughput, branch-protection |
| [ADR-0024](ADR-0024-merge-stall-tooling-not-capacity.md) | Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock | Proposed | 2026-07-06 | merge-sweep, runners, ci-capacity, root-cause, runbook |
| [ADR-0025](ADR-0025-occ-validator-redesign-option-a.md) | OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones) | Proposed | 2026-07-03 | occ, validator, evidence, receipts, supersession, dod-verify |
| [ADR-0026](ADR-0026-two-databases-tenant-vs-internal.md) | Two Databases — Tenant-Facing vs Internal/Ops | Superseded | 2026-07-29 | multitenancy, database, rls, tenant-isolation, postgres, data-topology |
| [ADR-0027](ADR-0027-one-application-database-domain-separation.md) | One Application Database with Contract-Classified Domains | Accepted | 2026-07-29 | multitenancy, database, rls, tenant-isolation, postgres, data-topology, contracts |
| [ADR-0028](ADR-0028-receipt-type-consolidation.md) | Receipt Type Consolidation onto ModelDodReceipt | Accepted | 2026-04-27 | omnibase_core, receipts, dod-evidence, schema-consolidation |
| [ADR-0029](ADR-0029-model-b-failing-rollup-validator-enforcement.md) | Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core) | Accepted | 2026-06-24 | omnibase_core, ci, branch-protection, validator-enforcement |
| [ADR-0030](ADR-0030-protocol-based-di-architecture.md) | Protocol-Based Dependency Injection Architecture | Implemented | 2025-10-30 | omnibase_core, dependency-injection, protocols, service-registry, architecture |
| [ADR-0031](ADR-0031-centralized-field-limit-constants.md) | Centralized Field Limit Constants | Accepted | 2025-12-27 | omnibase_core, pydantic, validation, constants |
| [ADR-0032](ADR-0032-reducer-output-exception-consistency.md) | Reducer Output Exception Consistency | Implemented | 2025-12-16 | omnibase_core, reducers, error-handling, pydantic, sentinel-pattern |
| [ADR-0033](ADR-0033-registration-trigger-architecture.md) | Registration Trigger Architecture | Accepted | 2025-12-19 | omnibase_core, registration, events, commands, orchestrator, node-lifecycle |
| [ADR-0034](ADR-0034-core-infra-dependency-boundary.md) | Core-Infra Dependency Boundary | Implemented | 2025-12-26 | omnibase_core, dependency-inversion, architecture-boundary, ci-enforcement |
| [ADR-0035](ADR-0035-status-taxonomy-and-categorical-organization.md) | Status Taxonomy and Categorical Organization | Accepted | 2026-01-12 | omnibase_core, enums, status-taxonomy, type-system, governance |
| [ADR-0036](ADR-0036-context-mutability-design-decision.md) | Context Mutability Design Decision | Implemented | 2025-12-15 | omnibase_core, pydantic, immutability, workflow-state, fsm-snapshots |
| [ADR-0037](ADR-0037-validator-error-handling-modelonexerror.md) | Validator Error Handling with ModelOnexError | Accepted | 2026-01-18 | omnibase_core, pydantic, error-handling, validators |
| [ADR-0038](ADR-0038-ci-workflow-modification-risk.md) | CI Workflow Modification Risk (Transport Import Branch Protection) | Mitigated | 2025-12-10 | omnibase_core, ci, transport-imports, dependency-inversion, risk-mitigation |
| [ADR-0044](ADR-0044-event-fan-out-and-app-owned-catalogs.md) | Event Fan-Out Strategy and App-Owned Event Catalogs | Implemented | 2026-02-19 | omniclaude, eventing, catalogs, fan-out |
| [ADR-0045](ADR-0045-candidate-list-injection.md) | Candidate List Injection | Accepted | 2026-02-19 | omniclaude, hooks, routing |
| [ADR-0046](ADR-0046-no-fallback-routing.md) | No-Fallback Routing | Accepted | 2026-02-19 | omniclaude, routing, fail-fast |
| [ADR-0047](ADR-0047-dual-emission-privacy-split.md) | Dual-Emission Privacy Split | Accepted | 2026-02-19 | omniclaude, eventing, privacy, kafka |
| [ADR-0048](ADR-0048-delegation-orchestrator-quality-gate.md) | Delegation Orchestrator Quality Gate | Accepted | 2026-02-19 | omniclaude, delegation, quality-gate |
| [ADR-0049](ADR-0049-three-tier-agent-routing.md) | Three-Tier Agent Routing (LLM, Fuzzy, Explicit) | Accepted | 2026-02-19 | omniclaude, routing, llm |
| [ADR-0050](ADR-0050-ai-slop-checker-rule-set-v1.md) | AI-Slop Checker Rule Set v1.0 | Accepted | 2026-03-02 | omniclaude, omnibase_core, omnibase_infra, omnibase_spi, omniintelligence, omnimemory, onex_change_control, quality-gate |
| [ADR-0051](ADR-0051-sibling-plugin-strategy.md) | Sibling Plugin Strategy (omnigemini, omnimemory, omniintelligence) | Recorded | 2026-04-23 | omniclaude, plugins, packaging |
