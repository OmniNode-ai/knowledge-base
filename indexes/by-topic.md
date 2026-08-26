# Topic Index

Generated — do not edit manually. Run `uv run python scripts/generate_indexes.py` to regenerate.

Knowledge base artifacts grouped by topic.

## admission

- **[Runner disk-admission gate (<ticket>)](runbooks/runner-disk-admission-gate.md)** (runbook)

## agent-md

- **[AGENT.md Template](reference/agent-md-template.md)** (reference)

## agents

- **[Agent Routing Architecture](architecture/agent-routing-architecture.md)** (architecture)
- **[Adding an Agent](guides/adding-an-agent.md)** (guide)

## api

- **[ADR-0004: Registry-Owned Consumer Surface](adrs/ADR-0004-registry-owned-consumer-surface.md)** (adr)

## append-only

- **[DoD Receipt Hashing, Append-Only, and Supersession](reference/receipt-hashing-and-supersession.md)** (reference)

## application

- **[Application database cutover receipts](runbooks/application-database-cutover-receipts.md)** (runbook)

## apply

- **[Apply Migrations Runbook](runbooks/apply-migrations.md)** (runbook)

## archetypes

- **[ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators](adrs/ADR-0013-deterministic-fsm-control-plane.md)** (adr)
- **[ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy](adrs/ADR-0016-one-contract-configured-pilot.md)** (adr)

## architecture

- **[ADR-0030: Protocol-Based Dependency Injection Architecture](adrs/ADR-0030-protocol-based-di-architecture.md)** (adr)
- **[ONEX Four-Node Architecture in OmniIntelligence](architecture/omniintelligence-four-node-architecture.md)** (architecture)
- **[ARCH-002: Kafka Abstraction Rule (OmniMemory)](architecture/omnimemory-arch-002-kafka-abstraction.md)** (architecture)
- **[ONEX Four-Node Architecture in OmniMemory](architecture/omnimemory-four-node-architecture.md)** (architecture)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## architecture-boundary

- **[ADR-0003: Registration Runtime / Registry Boundary](adrs/ADR-0003-registration-runtime-registry-boundary.md)** (adr)
- **[ADR-0004: Registry-Owned Consumer Surface](adrs/ADR-0004-registry-owned-consumer-surface.md)** (adr)
- **[ADR-0034: Core-Infra Dependency Boundary](adrs/ADR-0034-core-infra-dependency-boundary.md)** (adr)

## architecture-layers

- **[ADR-0006: Skill Liveness Validator Home](adrs/ADR-0006-skill-liveness-validator-home.md)** (adr)

## asyncio

- **[Async Hang Debugging Guide](guides/async-hang-debugging.md)** (guide)

## authoring

- **[Handler Authoring Guide](guides/handler-authoring-guide.md)** (guide)

## authority

- **[Dashboard Authority Collapse](pivots/PIVOT-0002-dashboard-authority-collapse.md)** (pivot)
- **[Event Streams Are Not Authoritative State](pivots/PIVOT-0005-event-streams-are-not-authoritative-state.md)** (pivot)

## auto-wiring

- **[OmniIntelligence Contract Package Specification](architecture/omniintelligence-contract-package-spec.md)** (architecture)

## automation

- **[ADR-0001: Dependabot PR Approval Remains Manual](adrs/ADR-0001-dependabot-approval-manual.md)** (adr)

## benchmark

- **[ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling](adrs/ADR-0018-delegation-graded-benchmark-ladder.md)** (adr)

## beta-launch

- **[ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes](adrs/ADR-0021-beta-ships-first-priority-lock.md)** (adr)

## bifrost

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)

## branch-protection

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)
- **[ADR-0023: Remove the onex_change_control Merge Queue](adrs/ADR-0023-remove-occ-merge-queue.md)** (adr)
- **[ADR-0029: Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core)](adrs/ADR-0029-model-b-failing-rollup-validator-enforcement.md)** (adr)
- **[CI/CD Standards](reference/ci-cd-standards.md)** (reference)

## bringup

- **[Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)](runbooks/cold-lane-full-bringup.md)** (runbook)

## build-efficiency

- **[ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)](adrs/ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md)** (adr)

## bulk

- **[Bulk PR operations — mandatory throttled path (<ticket>)](runbooks/bulk-pr-operations.md)** (runbook)

## bus

- **[Event Bus Integration Guide](architecture/event-bus-integration.md)** (architecture)

## c2

- **[Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2](runbooks/c2-git-mirror-egress-rollout.md)** (runbook)

## cache

- **[PyPI pull-through cache (egress) rollout — <ticket> C1](runbooks/pypi-cache-egress-rollout.md)** (runbook)
- **[Runner-fleet local DNS cache rollout — <ticket>](runbooks/runner-dns-cache-rollout.md)** (runbook)

## canonical-model

- **[ADR-0005: Dispatch Lifecycle Canonical Source](adrs/ADR-0005-dispatch-lifecycle-canonical.md)** (adr)

## canonical-source

- **[ADR-0007: Canonical Skills Migration Plan](adrs/ADR-0007-skills-canonical-plan.md)** (adr)

## catalog

- **[Topic Catalog Architecture](architecture/topic-catalog-architecture.md)** (architecture)

## check-db-boundary

- **[DB Boundary Policy](reference/db-boundary-policy.md)** (reference)

## ci

- **[ADR-0001: Dependabot PR Approval Remains Manual](adrs/ADR-0001-dependabot-approval-manual.md)** (adr)
- **[ADR-0006: Skill Liveness Validator Home](adrs/ADR-0006-skill-liveness-validator-home.md)** (adr)
- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)
- **[ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)](adrs/ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md)** (adr)
- **[ADR-0023: Remove the onex_change_control Merge Queue](adrs/ADR-0023-remove-occ-merge-queue.md)** (adr)
- **[ADR-0029: Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core)](adrs/ADR-0029-model-b-failing-rollup-validator-enforcement.md)** (adr)
- **[ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)](adrs/ADR-0038-ci-workflow-modification-risk.md)** (adr)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)
- **[Async Hang Debugging Guide](guides/async-hang-debugging.md)** (guide)
- **[CI/CD Standards](reference/ci-cd-standards.md)** (reference)
- **[CI Documentation Validation Setup](reference/ci-validation-setup.md)** (reference)
- **[Cross-Repo Merge Dependency Graph](reference/merge-dependency-graph.md)** (reference)

## ci-capacity

- **[ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock](adrs/ADR-0024-merge-stall-tooling-not-capacity.md)** (adr)

## ci-cd

- **[CI/CD Standards](reference/omniclaude-ci-cd-standards.md)** (reference)

## ci-enforcement

- **[ADR-0034: Core-Infra Dependency Boundary](adrs/ADR-0034-core-infra-dependency-boundary.md)** (adr)

## client-state

- **[Dashboard Authority Collapse](pivots/PIVOT-0002-dashboard-authority-collapse.md)** (pivot)

## code-projection

- **[OmniIntelligence Deterministic Code Projection v2](architecture/omniintelligence-code-projection-v2.md)** (architecture)

## code-standards

- **[Typed-Metadata Policy](reference/typed-metadata-policy.md)** (reference)

## cold

- **[Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)](runbooks/cold-lane-full-bringup.md)** (runbook)

## commands

- **[ADR-0033: Registration Trigger Architecture](adrs/ADR-0033-registration-trigger-architecture.md)** (adr)

## completion

- **[Completion Requires Durable Evidence](pivots/PIVOT-0003-completion-requires-durable-evidence.md)** (pivot)

## complexity

- **[ADR-0009: Complexity-Aware Delegation Routing](adrs/ADR-0009-complexity-aware-delegation-routing.md)** (adr)

## compliance

- **[Compliance Enforcement Architecture](architecture/compliance-enforcement-architecture.md)** (architecture)

## compose

- **[Judge Compose Profile](runbooks/judge-compose-profile.md)** (runbook)

## config

- **[Volume Config Drift Gate + Re-seed Procedure](runbooks/volume-config-drift-and-reseed.md)** (runbook)

## config-as-data

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)

## config-authority

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)

## constants

- **[ADR-0031: Centralized Field Limit Constants](adrs/ADR-0031-centralized-field-limit-constants.md)** (adr)

## consumer-surface

- **[ADR-0004: Registry-Owned Consumer Surface](adrs/ADR-0004-registry-owned-consumer-surface.md)** (adr)

## context-injection

- **[Context Enrichment Pipeline Architecture](architecture/context-enrichment-pipeline.md)** (architecture)

## contract-governance

- **[Contracts Define Reality](doctrine/contracts-define-reality.md)** (doctrine)

## contract-hashing

- **[DoD Receipt Hashing, Append-Only, and Supersession](reference/receipt-hashing-and-supersession.md)** (reference)

## contract-yaml

- **[OmniIntelligence Contract Package Specification](architecture/omniintelligence-contract-package-spec.md)** (architecture)

## contracts

- **[ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)](adrs/ADR-0010-adaptive-recursive-contract-bisection.md)** (adr)
- **[ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy](adrs/ADR-0016-one-contract-configured-pilot.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## control-plane

- **[ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators](adrs/ADR-0013-deterministic-fsm-control-plane.md)** (adr)

## cost-model

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)

## cross-repo

- **[Cross-Repo Merge Dependency Graph](reference/merge-dependency-graph.md)** (reference)

## cross-repo-standard

- **[AGENT.md Template](reference/agent-md-template.md)** (reference)
- **[CI/CD Standards](reference/ci-cd-standards.md)** (reference)
- **[CI Documentation Validation Setup](reference/ci-validation-setup.md)** (reference)
- **[Standard Documentation Layout](reference/standard-doc-layout.md)** (reference)

## current

- **[ONEX Current Node Architecture](architecture/current-node-architecture.md)** (architecture)

## cutover

- **[Application database cutover receipts](runbooks/application-database-cutover-receipts.md)** (runbook)

## dashboard

- **[Dashboard Authority Collapse](pivots/PIVOT-0002-dashboard-authority-collapse.md)** (pivot)

## data-flow

- **[Hook Data Flow Architecture](architecture/hook-data-flow.md)** (architecture)

## data-ownership

- **[OmniMemory Data Ownership](reference/omnimemory-memory-data-ownership.md)** (reference)

## data-topology

- **[ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops](adrs/ADR-0026-two-databases-tenant-vs-internal.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)

## data-verification

- **[ADR-0002: Data Verification Node Invocation Policy](adrs/ADR-0002-data-verification-invocation.md)** (adr)

## database

- **[ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops](adrs/ADR-0026-two-databases-tenant-vs-internal.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)
- **[DB Boundary Policy](reference/db-boundary-policy.md)** (reference)
- **[Application database cutover receipts](runbooks/application-database-cutover-receipts.md)** (runbook)

## debugging

- **[Async Hang Debugging Guide](guides/async-hang-debugging.md)** (guide)

## decomposition

- **[ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)](adrs/ADR-0010-adaptive-recursive-contract-bisection.md)** (adr)

## delegation

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)
- **[ADR-0009: Complexity-Aware Delegation Routing](adrs/ADR-0009-complexity-aware-delegation-routing.md)** (adr)
- **[ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)](adrs/ADR-0010-adaptive-recursive-contract-bisection.md)** (adr)
- **[ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug](adrs/ADR-0014-factory-economics-frontier-fissions-locals-build.md)** (adr)
- **[ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling](adrs/ADR-0018-delegation-graded-benchmark-ladder.md)** (adr)
- **[Delegation Architecture](architecture/delegation-architecture.md)** (architecture)
- **[Delegation Dispatch Architecture](architecture/delegation-dispatch.md)** (architecture)
- **[Delegation Routing Contract](architecture/delegation-routing-contract.md)** (architecture)

## dependabot

- **[ADR-0001: Dependabot PR Approval Remains Manual](adrs/ADR-0001-dependabot-approval-manual.md)** (adr)

## dependency-injection

- **[ADR-0030: Protocol-Based Dependency Injection Architecture](adrs/ADR-0030-protocol-based-di-architecture.md)** (adr)

## dependency-inversion

- **[ADR-0034: Core-Infra Dependency Boundary](adrs/ADR-0034-core-infra-dependency-boundary.md)** (adr)
- **[ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)](adrs/ADR-0038-ci-workflow-modification-risk.md)** (adr)

## deployment

- **[Market Node Deployment Runbook](runbooks/market-node-deployment.md)** (runbook)

## determinism

- **[ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators](adrs/ADR-0013-deterministic-fsm-control-plane.md)** (adr)

## dev-lane

- **[ADR-0020: Branch-Preview Verification (proof_class=branch-preview)](adrs/ADR-0020-branch-preview-verification.md)** (adr)

## disk

- **[Runner disk-admission gate (<ticket>)](runbooks/runner-disk-admission-gate.md)** (runbook)

## dispatch

- **[ADR-0005: Dispatch Lifecycle Canonical Source](adrs/ADR-0005-dispatch-lifecycle-canonical.md)** (adr)
- **[Message Dispatch Engine Architecture](architecture/message-dispatch-engine.md)** (architecture)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## disposable-implementations

- **[ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug](adrs/ADR-0014-factory-economics-frontier-fissions-locals-build.md)** (adr)

## distillation

- **[ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug](adrs/ADR-0014-factory-economics-frontier-fissions-locals-build.md)** (adr)

## dlq

- **[Dead Letter Queue (DLQ) Message Format](architecture/dlq-message-format.md)** (architecture)
- **[Fault-injection fixture — DLQ offset-withholding proof](runbooks/fault-inject-fixture-dlq-offset-withholding.md)** (runbook)

## dns

- **[Runner-fleet local DNS cache rollout — <ticket>](runbooks/runner-dns-cache-rollout.md)** (runbook)

## doc-layout

- **[Standard Documentation Layout](reference/standard-doc-layout.md)** (reference)

## doctrine

- **[ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only](adrs/ADR-0019-no-self-authored-evidence.md)** (adr)

## documentation

- **[Standard Documentation Layout](reference/standard-doc-layout.md)** (reference)

## dod

- **[ADR-0002: Data Verification Node Invocation Policy](adrs/ADR-0002-data-verification-invocation.md)** (adr)

## dod-evidence

- **[ADR-0028: Receipt Type Consolidation onto ModelDodReceipt](adrs/ADR-0028-receipt-type-consolidation.md)** (adr)

## dod-receipts

- **[DoD Receipt Hashing, Append-Only, and Supersession](reference/receipt-hashing-and-supersession.md)** (reference)

## dod-verify

- **[ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)](adrs/ADR-0025-occ-validator-redesign-option-a.md)** (adr)

## done-definition

- **[Completion Requires Durable Evidence](pivots/PIVOT-0003-completion-requires-durable-evidence.md)** (pivot)

## drift

- **[Volume Config Drift Gate + Re-seed Procedure](runbooks/volume-config-drift-and-reseed.md)** (runbook)

## economics

- **[ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug](adrs/ADR-0014-factory-economics-frontier-fissions-locals-build.md)** (adr)

## egress

- **[Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2](runbooks/c2-git-mirror-egress-rollout.md)** (runbook)
- **[PyPI pull-through cache (egress) rollout — <ticket> C1](runbooks/pypi-cache-egress-rollout.md)** (runbook)

## emit-daemon

- **[Emit Daemon Architecture](architecture/emit-daemon-architecture.md)** (architecture)

## enforcement

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)

## engine

- **[Message Dispatch Engine Architecture](architecture/message-dispatch-engine.md)** (architecture)

## enum

- **[Untitled](architecture/shared-enum-ownership.md)** (architecture)

## enums

- **[ADR-0035: Status Taxonomy and Categorical Organization](adrs/ADR-0035-status-taxonomy-and-categorical-organization.md)** (adr)

## error-handling

- **[ADR-0032: Reducer Output Exception Consistency](adrs/ADR-0032-reducer-output-exception-consistency.md)** (adr)
- **[ADR-0037: Validator Error Handling with ModelOnexError](adrs/ADR-0037-validator-error-handling-modelonexerror.md)** (adr)

## event

- **[Event Bus Integration Guide](architecture/event-bus-integration.md)** (architecture)
- **[ONEX Event Streaming Topics - Specification (v1)](architecture/event-streaming-topics.md)** (architecture)

## event-bus

- **[ADR-0005: Dispatch Lifecycle Canonical Source](adrs/ADR-0005-dispatch-lifecycle-canonical.md)** (adr)
- **[OmniIntelligence Contract Package Specification](architecture/omniintelligence-contract-package-spec.md)** (architecture)
- **[ARCH-002: Kafka Abstraction Rule (OmniMemory)](architecture/omnimemory-arch-002-kafka-abstraction.md)** (architecture)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)
- **[ONEX Kafka Topic Naming Standard](reference/onex-topic-taxonomy.md)** (reference)
- **[Kafka/Redpanda Reconnect Tuning and Broker Recovery](runbooks/kafka-reconnect-and-broker-recovery.md)** (runbook)

## event-envelope

- **[Event Envelope Canonical Field Names](reference/event-envelope-field-names.md)** (reference)

## event-streaming

- **[Ingestion Is Not Interpretation](pivots/PIVOT-0001-ingestion-is-not-interpretation.md)** (pivot)
- **[Event Streams Are Not Authoritative State](pivots/PIVOT-0005-event-streams-are-not-authoritative-state.md)** (pivot)

## event-surface

- **[OmniIntelligence Event Surface](reference/omniintelligence-event-surface.md)** (reference)

## events

- **[ADR-0033: Registration Trigger Architecture](adrs/ADR-0033-registration-trigger-architecture.md)** (adr)

## evidence

- **[ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only](adrs/ADR-0019-no-self-authored-evidence.md)** (adr)
- **[ADR-0020: Branch-Preview Verification (proof_class=branch-preview)](adrs/ADR-0020-branch-preview-verification.md)** (adr)
- **[ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)](adrs/ADR-0025-occ-validator-redesign-option-a.md)** (adr)
- **[Completion Requires Durable Evidence](pivots/PIVOT-0003-completion-requires-durable-evidence.md)** (pivot)

## evidence-gates

- **[ADR-0002: Data Verification Node Invocation Policy](adrs/ADR-0002-data-verification-invocation.md)** (adr)

## evidence-only

- **[ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)](adrs/ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md)** (adr)

## evidence-systems

- **[Evidence Is a First-Class Output](doctrine/evidence-is-first-class-output.md)** (doctrine)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## evolutionary-search

- **[ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots](adrs/ADR-0017-no-deterministic-champion-llm-pilots.md)** (adr)

## example

- **[2-Way Registration: A Complete ONEX Example](guides/registration-example.md)** (guide)

## failure-handling

- **[Degrade Safely](doctrine/degrade-safely.md)** (doctrine)
- **[Fail Fast and Loud](doctrine/fail-fast-and-loud.md)** (doctrine)

## fault

- **[Fault-injection fixture — DLQ offset-withholding proof](runbooks/fault-inject-fixture-dlq-offset-withholding.md)** (runbook)

## fixture

- **[Fault-injection fixture — DLQ offset-withholding proof](runbooks/fault-inject-fixture-dlq-offset-withholding.md)** (runbook)

## fleet

- **[Runner fleet listener liveness (<ticket>)](runbooks/runner-fleet-listener-liveness.md)** (runbook)

## format

- **[Dead Letter Queue (DLQ) Message Format](architecture/dlq-message-format.md)** (architecture)

## four-node-architecture

- **[ONEX Core Terminology](reference/onex-terminology.md)** (reference)

## freshness

- **[Repowise Freshness Receipt](runbooks/repowise-freshness-receipt.md)** (runbook)

## fsm

- **[ADR-0005: Dispatch Lifecycle Canonical Source](adrs/ADR-0005-dispatch-lifecycle-canonical.md)** (adr)
- **[ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators](adrs/ADR-0013-deterministic-fsm-control-plane.md)** (adr)

## fsm-snapshots

- **[ADR-0036: Context Mutability Design Decision](adrs/ADR-0036-context-mutability-design-decision.md)** (adr)

## full

- **[Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)](runbooks/cold-lane-full-bringup.md)** (runbook)

## gate

- **[Runner disk-admission gate (<ticket>)](runbooks/runner-disk-admission-gate.md)** (runbook)

## gate-check-contract

- **[CI/CD Standards](reference/ci-cd-standards.md)** (reference)

## gates

- **[ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators](adrs/ADR-0013-deterministic-fsm-control-plane.md)** (adr)

## git

- **[Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2](runbooks/c2-git-mirror-egress-rollout.md)** (runbook)

## github-actions

- **[ADR-0001: Dependabot PR Approval Remains Manual](adrs/ADR-0001-dependabot-approval-manual.md)** (adr)

## golden-chain

- **[Dual-Binding Test Cases — the Harness Convention](reference/dual-binding-cases.md)** (reference)

## golden-fixtures

- **[ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic](adrs/ADR-0015-steel-live-play-non-deterministic.md)** (adr)

## governance

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)
- **[ADR-0035: Status Taxonomy and Categorical Organization](adrs/ADR-0035-status-taxonomy-and-categorical-organization.md)** (adr)

## graded-eval

- **[ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling](adrs/ADR-0018-delegation-graded-benchmark-ladder.md)** (adr)

## handler

- **[Handler Authoring Guide](guides/handler-authoring-guide.md)** (guide)

## handlers

- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)
- **[ONEX Core Terminology](reference/onex-terminology.md)** (reference)

## historical

- **[Event-Driven Agent Routing Architecture Proposal](architecture/event-driven-routing-proposal.md)** (architecture)
- **[Agent Routing Architecture - Visual Comparison](architecture/routing-architecture-comparison.md)** (architecture)

## hooks

- **[Compliance Enforcement Architecture](architecture/compliance-enforcement-architecture.md)** (architecture)
- **[Context Enrichment Pipeline Architecture](architecture/context-enrichment-pipeline.md)** (architecture)
- **[Hook Data Flow Architecture](architecture/hook-data-flow.md)** (architecture)
- **[Adding a Hook Handler](guides/adding-a-hook-handler.md)** (guide)

## how-to

- **[Adding a Hook Handler](guides/adding-a-hook-handler.md)** (guide)
- **[Adding a Skill](guides/adding-a-skill.md)** (guide)
- **[Adding an Agent](guides/adding-an-agent.md)** (guide)
- **[Testing Guide](guides/omniclaude-testing-guide.md)** (guide)

## immutability

- **[ADR-0036: Context Mutability Design Decision](adrs/ADR-0036-context-mutability-design-decision.md)** (adr)

## infrastructure

- **[LLM Infrastructure Architecture](architecture/llm-infrastructure.md)** (architecture)

## ingestion

- **[Ingestion Is Not Interpretation](pivots/PIVOT-0001-ingestion-is-not-interpretation.md)** (pivot)

## ingestion-boundaries

- **[Ingestion and Interpretation Are Separate](doctrine/ingestion-and-interpretation-separate.md)** (doctrine)

## inject

- **[Fault-injection fixture — DLQ offset-withholding proof](runbooks/fault-inject-fixture-dlq-offset-withholding.md)** (runbook)

## install

- **[Node-skill package co-install (omnimarket) — <ticket>](runbooks/node-skill-package-install.md)** (runbook)

## integration

- **[Event Bus Integration Guide](architecture/event-bus-integration.md)** (architecture)
- **[MCP Integration Guide](guides/mcp-integration-guide.md)** (guide)

## integration-testing

- **[Dual-Binding Test Cases — the Harness Convention](reference/dual-binding-cases.md)** (reference)

## judge

- **[Judge Compose Profile](runbooks/judge-compose-profile.md)** (runbook)

## kafka

- **[ADR-0002: Data Verification Node Invocation Policy](adrs/ADR-0002-data-verification-invocation.md)** (adr)
- **[Emit Daemon Architecture](architecture/emit-daemon-architecture.md)** (architecture)
- **[ARCH-002: Kafka Abstraction Rule (OmniMemory)](architecture/omnimemory-arch-002-kafka-abstraction.md)** (architecture)
- **[OmniIntelligence Event Surface](reference/omniintelligence-event-surface.md)** (reference)
- **[OmniMemory Runtime Plugin System](reference/omnimemory-runtime-plugins.md)** (reference)
- **[ONEX Kafka Topic Naming Standard](reference/onex-topic-taxonomy.md)** (reference)
- **[Kafka/Redpanda Reconnect Tuning and Broker Recovery](runbooks/kafka-reconnect-and-broker-recovery.md)** (runbook)

## lane

- **[Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)](runbooks/cold-lane-full-bringup.md)** (runbook)
- **[Stability-Lane Refresh (<ticket> / <ticket>)](runbooks/stability-lane-refresh.md)** (runbook)
- **[Stability-Test Runtime Lane](runbooks/stability-test-runtime-lane.md)** (runbook)

## last-write-wins

- **[Reducers Own State Progression](pivots/PIVOT-0004-reducers-own-state-progression.md)** (pivot)

## layer

- **[Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)](runbooks/worktree-reaper-two-layer-gc.md)** (runbook)

## learned-routing

- **[ADR-0009: Complexity-Aware Delegation Routing](adrs/ADR-0009-complexity-aware-delegation-routing.md)** (adr)

## learning-loop

- **[ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots](adrs/ADR-0017-no-deterministic-champion-llm-pilots.md)** (adr)

## lifecycle

- **[ADR-0005: Dispatch Lifecycle Canonical Source](adrs/ADR-0005-dispatch-lifecycle-canonical.md)** (adr)

## listener

- **[Runner fleet listener liveness (<ticket>)](runbooks/runner-fleet-listener-liveness.md)** (runbook)

## liveness

- **[Runner fleet listener liveness (<ticket>)](runbooks/runner-fleet-listener-liveness.md)** (runbook)

## llm

- **[ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic](adrs/ADR-0015-steel-live-play-non-deterministic.md)** (adr)
- **[LLM Infrastructure Architecture](architecture/llm-infrastructure.md)** (architecture)

## llm-navigation

- **[AGENT.md Template](reference/agent-md-template.md)** (reference)

## llm-pilots

- **[ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots](adrs/ADR-0017-no-deterministic-champion-llm-pilots.md)** (adr)

## llm-routing

- **[Delegation Dispatch Architecture](architecture/delegation-dispatch.md)** (architecture)
- **[Delegation Routing Contract](architecture/delegation-routing-contract.md)** (architecture)
- **[LLM Routing Architecture](architecture/llm-routing-architecture.md)** (architecture)

## local-first

- **[ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)](adrs/ADR-0010-adaptive-recursive-contract-bisection.md)** (adr)
- **[ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic](adrs/ADR-0015-steel-live-play-non-deterministic.md)** (adr)
- **[ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling](adrs/ADR-0018-delegation-graded-benchmark-ladder.md)** (adr)

## local-llm

- **[Delegation Architecture](architecture/delegation-architecture.md)** (architecture)

## markdown-link-check

- **[CI Documentation Validation Setup](reference/ci-validation-setup.md)** (reference)

## market

- **[Market Node Deployment Runbook](runbooks/market-node-deployment.md)** (runbook)

## materialization

- **[Event Streams Are Not Authoritative State](pivots/PIVOT-0005-event-streams-are-not-authoritative-state.md)** (pivot)

## mcp

- **[MCP Service Architecture](architecture/mcp-service-architecture.md)** (architecture)
- **[MCP Integration Guide](guides/mcp-integration-guide.md)** (guide)

## memgraph

- **[OmniIntelligence Deterministic Code Projection v2](architecture/omniintelligence-code-projection-v2.md)** (architecture)
- **[OmniMemory Data Ownership](reference/omnimemory-memory-data-ownership.md)** (reference)

## merge-gates

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)

## merge-ordering

- **[Cross-Repo Merge Dependency Graph](reference/merge-dependency-graph.md)** (reference)

## merge-queue

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)
- **[ADR-0023: Remove the onex_change_control Merge Queue](adrs/ADR-0023-remove-occ-merge-queue.md)** (adr)

## merge-sweep

- **[ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock](adrs/ADR-0024-merge-stall-tooling-not-capacity.md)** (adr)

## message

- **[Dead Letter Queue (DLQ) Message Format](architecture/dlq-message-format.md)** (architecture)
- **[Message Dispatch Engine Architecture](architecture/message-dispatch-engine.md)** (architecture)

## micro-factories

- **[ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)](adrs/ADR-0010-adaptive-recursive-contract-bisection.md)** (adr)

## migration

- **[ADR-0007: Canonical Skills Migration Plan](adrs/ADR-0007-skills-canonical-plan.md)** (adr)
- **[OmniMemory → OmniMarket Node Migration Boundary](guides/omnimemory-market-migration-boundary.md)** (guide)

## migration-safety

- **[Migration Must Be Staged and Recoverable](doctrine/migration-staged-recoverable.md)** (doctrine)

## migrations

- **[Apply Migrations Runbook](runbooks/apply-migrations.md)** (runbook)
- **[Vendored Node Migration Runbook](runbooks/vendored-node-migrations.md)** (runbook)

## mirror

- **[Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2](runbooks/c2-git-mirror-egress-rollout.md)** (runbook)

## model-routing

- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## multi-tenant

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)

## multitenancy

- **[ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops](adrs/ADR-0026-two-databases-tenant-vs-internal.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)

## naming

- **[ADR-0011: Name the Discipline RSD = Recursive System Design](adrs/ADR-0011-rsd-recursive-system-design-naming.md)** (adr)

## node

- **[ONEX Current Node Architecture](architecture/current-node-architecture.md)** (architecture)
- **[Market Node Deployment Runbook](runbooks/market-node-deployment.md)** (runbook)
- **[Node-skill package co-install (omnimarket) — <ticket>](runbooks/node-skill-package-install.md)** (runbook)
- **[Vendored Node Migration Runbook](runbooks/vendored-node-migrations.md)** (runbook)

## node-archetypes

- **[ONEX Four-Node Architecture in OmniIntelligence](architecture/omniintelligence-four-node-architecture.md)** (architecture)
- **[ONEX Four-Node Architecture in OmniMemory](architecture/omnimemory-four-node-architecture.md)** (architecture)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## node-inventory

- **[OmniIntelligence Node Inventory](reference/omniintelligence-node-inventory.md)** (reference)

## node-lifecycle

- **[ADR-0033: Registration Trigger Architecture](adrs/ADR-0033-registration-trigger-architecture.md)** (adr)

## nodes

- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)
- **[OmniMemory → OmniMarket Node Migration Boundary](guides/omnimemory-market-migration-boundary.md)** (guide)
- **[OmniIntelligence Node Inventory](reference/omniintelligence-node-inventory.md)** (reference)
- **[OmniMarket Node Catalog](reference/omnimarket-node-catalog.md)** (reference)

## non-determinism

- **[ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic](adrs/ADR-0015-steel-live-play-non-deterministic.md)** (adr)
- **[ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots](adrs/ADR-0017-no-deterministic-champion-llm-pilots.md)** (adr)

## nondeterminism

- **[Ingestion Is Not Interpretation](pivots/PIVOT-0001-ingestion-is-not-interpretation.md)** (pivot)

## occ

- **[ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only](adrs/ADR-0019-no-self-authored-evidence.md)** (adr)
- **[ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)](adrs/ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md)** (adr)
- **[ADR-0023: Remove the onex_change_control Merge Queue](adrs/ADR-0023-remove-occ-merge-queue.md)** (adr)
- **[ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)](adrs/ADR-0025-occ-validator-redesign-option-a.md)** (adr)
- **[Dual-Binding Test Cases — the Harness Convention](reference/dual-binding-cases.md)** (reference)
- **[DoD Receipt Hashing, Append-Only, and Supersession](reference/receipt-hashing-and-supersession.md)** (reference)

## omnibase-infra

- **[ONEX Current Node Architecture](architecture/current-node-architecture.md)** (architecture)
- **[Dead Letter Queue (DLQ) Message Format](architecture/dlq-message-format.md)** (architecture)
- **[Event Bus Integration Guide](architecture/event-bus-integration.md)** (architecture)
- **[ONEX Event Streaming Topics - Specification (v1)](architecture/event-streaming-topics.md)** (architecture)
- **[LLM Infrastructure Architecture](architecture/llm-infrastructure.md)** (architecture)
- **[MCP Service Architecture](architecture/mcp-service-architecture.md)** (architecture)
- **[Message Dispatch Engine Architecture](architecture/message-dispatch-engine.md)** (architecture)
- **[ONEX Architecture Overview](architecture/onex-runtime-overview.md)** (architecture)
- **[REGISTRATION WORKFLOW](architecture/registration-workflow.md)** (architecture)
- **[Untitled](architecture/shared-enum-ownership.md)** (architecture)
- **[Snapshot Publishing Architecture](architecture/snapshot-publishing.md)** (architecture)
- **[Topic Catalog Architecture](architecture/topic-catalog-architecture.md)** (architecture)
- **[Handler Authoring Guide](guides/handler-authoring-guide.md)** (guide)
- **[MCP Integration Guide](guides/mcp-integration-guide.md)** (guide)
- **[2-Way Registration: A Complete ONEX Example](guides/registration-example.md)** (guide)
- **[Application database cutover receipts](runbooks/application-database-cutover-receipts.md)** (runbook)
- **[Apply Migrations Runbook](runbooks/apply-migrations.md)** (runbook)
- **[Bulk PR operations — mandatory throttled path (<ticket>)](runbooks/bulk-pr-operations.md)** (runbook)
- **[Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2](runbooks/c2-git-mirror-egress-rollout.md)** (runbook)
- **[Cold-lane full bring-up (deps + migration one-shots + full `--profile runtime`)](runbooks/cold-lane-full-bringup.md)** (runbook)
- **[Fault-injection fixture — DLQ offset-withholding proof](runbooks/fault-inject-fixture-dlq-offset-withholding.md)** (runbook)
- **[Judge Compose Profile](runbooks/judge-compose-profile.md)** (runbook)
- **[Market Node Deployment Runbook](runbooks/market-node-deployment.md)** (runbook)
- **[Node-skill package co-install (omnimarket) — <ticket>](runbooks/node-skill-package-install.md)** (runbook)
- **[PyPI pull-through cache (egress) rollout — <ticket> C1](runbooks/pypi-cache-egress-rollout.md)** (runbook)
- **[Repowise Freshness Receipt](runbooks/repowise-freshness-receipt.md)** (runbook)
- **[Runner disk-admission gate (<ticket>)](runbooks/runner-disk-admission-gate.md)** (runbook)
- **[Runner-fleet local DNS cache rollout — <ticket>](runbooks/runner-dns-cache-rollout.md)** (runbook)
- **[Runner fleet listener liveness (<ticket>)](runbooks/runner-fleet-listener-liveness.md)** (runbook)
- **[Stability-Lane Refresh (<ticket> / <ticket>)](runbooks/stability-lane-refresh.md)** (runbook)
- **[Stability-Test Runtime Lane](runbooks/stability-test-runtime-lane.md)** (runbook)
- **[Vendored Node Migration Runbook](runbooks/vendored-node-migrations.md)** (runbook)
- **[Volume Config Drift Gate + Re-seed Procedure](runbooks/volume-config-drift-and-reseed.md)** (runbook)
- **[Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)](runbooks/worktree-reaper-two-layer-gc.md)** (runbook)

## omnibase_core

- **[ADR-0028: Receipt Type Consolidation onto ModelDodReceipt](adrs/ADR-0028-receipt-type-consolidation.md)** (adr)
- **[ADR-0029: Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core)](adrs/ADR-0029-model-b-failing-rollup-validator-enforcement.md)** (adr)
- **[ADR-0030: Protocol-Based Dependency Injection Architecture](adrs/ADR-0030-protocol-based-di-architecture.md)** (adr)
- **[ADR-0031: Centralized Field Limit Constants](adrs/ADR-0031-centralized-field-limit-constants.md)** (adr)
- **[ADR-0032: Reducer Output Exception Consistency](adrs/ADR-0032-reducer-output-exception-consistency.md)** (adr)
- **[ADR-0033: Registration Trigger Architecture](adrs/ADR-0033-registration-trigger-architecture.md)** (adr)
- **[ADR-0034: Core-Infra Dependency Boundary](adrs/ADR-0034-core-infra-dependency-boundary.md)** (adr)
- **[ADR-0035: Status Taxonomy and Categorical Organization](adrs/ADR-0035-status-taxonomy-and-categorical-organization.md)** (adr)
- **[ADR-0036: Context Mutability Design Decision](adrs/ADR-0036-context-mutability-design-decision.md)** (adr)
- **[ADR-0037: Validator Error Handling with ModelOnexError](adrs/ADR-0037-validator-error-handling-modelonexerror.md)** (adr)
- **[ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)](adrs/ADR-0038-ci-workflow-modification-risk.md)** (adr)

## omniclaude

- **[Agent Routing Architecture](architecture/agent-routing-architecture.md)** (architecture)
- **[Compliance Enforcement Architecture](architecture/compliance-enforcement-architecture.md)** (architecture)
- **[Context Enrichment Pipeline Architecture](architecture/context-enrichment-pipeline.md)** (architecture)
- **[Delegation Architecture](architecture/delegation-architecture.md)** (architecture)
- **[Emit Daemon Architecture](architecture/emit-daemon-architecture.md)** (architecture)
- **[Event-Driven Agent Routing Architecture Proposal](architecture/event-driven-routing-proposal.md)** (architecture)
- **[Hook Data Flow Architecture](architecture/hook-data-flow.md)** (architecture)
- **[LLM Routing Architecture](architecture/llm-routing-architecture.md)** (architecture)
- **[omniclaude Repo Charter](architecture/omniclaude-repo-charter.md)** (architecture)
- **[Skill Lifecycle: When a Skill Stays in omniclaude vs. Moves to omnimarket](architecture/omniclaude-skill-lifecycle.md)** (architecture)
- **[Agent Routing Architecture - Visual Comparison](architecture/routing-architecture-comparison.md)** (architecture)
- **[Service Ownership & Boundaries](architecture/service-boundaries.md)** (architecture)
- **[Adding a Hook Handler](guides/adding-a-hook-handler.md)** (guide)
- **[Adding a Skill](guides/adding-a-skill.md)** (guide)
- **[Adding an Agent](guides/adding-an-agent.md)** (guide)
- **[Testing Guide](guides/omniclaude-testing-guide.md)** (guide)
- **[CI/CD Standards](reference/omniclaude-ci-cd-standards.md)** (reference)
- **[Test Discipline](reference/omniclaude-test-discipline.md)** (reference)
- **[Verification Doctrine](reference/omniclaude-verification-doctrine.md)** (reference)

## omniintelligence

- **[OmniIntelligence Deterministic Code Projection v2](architecture/omniintelligence-code-projection-v2.md)** (architecture)
- **[OmniIntelligence Contract Package Specification](architecture/omniintelligence-contract-package-spec.md)** (architecture)
- **[ONEX Four-Node Architecture in OmniIntelligence](architecture/omniintelligence-four-node-architecture.md)** (architecture)
- **[Service Ownership & Boundaries](architecture/service-boundaries.md)** (architecture)
- **[OmniIntelligence Event Surface](reference/omniintelligence-event-surface.md)** (reference)
- **[OmniIntelligence Node Inventory](reference/omniintelligence-node-inventory.md)** (reference)

## omnimarket

- **[Delegation Dispatch Architecture](architecture/delegation-dispatch.md)** (architecture)
- **[Delegation Routing Contract](architecture/delegation-routing-contract.md)** (architecture)
- **[Skill Lifecycle: When a Skill Stays in omniclaude vs. Moves to omnimarket](architecture/omniclaude-skill-lifecycle.md)** (architecture)
- **[OmniMemory → OmniMarket Node Migration Boundary](guides/omnimemory-market-migration-boundary.md)** (guide)
- **[OmniMarket Node Catalog](reference/omnimarket-node-catalog.md)** (reference)

## omnimemory

- **[ARCH-002: Kafka Abstraction Rule (OmniMemory)](architecture/omnimemory-arch-002-kafka-abstraction.md)** (architecture)
- **[ONEX Four-Node Architecture in OmniMemory](architecture/omnimemory-four-node-architecture.md)** (architecture)
- **[OmniMemory → OmniMarket Node Migration Boundary](guides/omnimemory-market-migration-boundary.md)** (guide)
- **[OmniMemory Data Ownership](reference/omnimemory-memory-data-ownership.md)** (reference)
- **[OmniMemory Runtime Plugin System](reference/omnimemory-runtime-plugins.md)** (reference)

## onex

- **[ONEX Architecture Overview](architecture/onex-runtime-overview.md)** (architecture)
- **[Event Envelope Canonical Field Names](reference/event-envelope-field-names.md)** (reference)
- **[ONEX Core Terminology](reference/onex-terminology.md)** (reference)
- **[ONEX Kafka Topic Naming Standard](reference/onex-topic-taxonomy.md)** (reference)

## onex-exclude

- **[DB Boundary Policy](reference/db-boundary-policy.md)** (reference)
- **[Typed-Metadata Policy](reference/typed-metadata-policy.md)** (reference)

## onex-runtime

- **[OmniMarket Node Catalog](reference/omnimarket-node-catalog.md)** (reference)

## operations

- **[Bulk PR operations — mandatory throttled path (<ticket>)](runbooks/bulk-pr-operations.md)** (runbook)
- **[Kafka/Redpanda Reconnect Tuning and Broker Recovery](runbooks/kafka-reconnect-and-broker-recovery.md)** (runbook)

## orchestrator

- **[ADR-0033: Registration Trigger Architecture](adrs/ADR-0033-registration-trigger-architecture.md)** (adr)

## orchestrator-nodes

- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## ordering

- **[Reducers Own State Progression](pivots/PIVOT-0004-reducers-own-state-progression.md)** (pivot)

## org-registry

- **[Repository Registry](reference/repository-registry.md)** (reference)

## overlays

- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## overview

- **[ONEX Architecture Overview](architecture/onex-runtime-overview.md)** (architecture)

## ownership

- **[Untitled](architecture/shared-enum-ownership.md)** (architecture)

## package

- **[Node-skill package co-install (omnimarket) — <ticket>](runbooks/node-skill-package-install.md)** (runbook)

## parity

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)

## per-model-baselines

- **[ADR-0009: Complexity-Aware Delegation Routing](adrs/ADR-0009-complexity-aware-delegation-routing.md)** (adr)

## pilot

- **[ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy](adrs/ADR-0016-one-contract-configured-pilot.md)** (adr)

## pipeline-fill

- **[ADR-0011: Name the Discipline RSD = Recursive System Design](adrs/ADR-0011-rsd-recursive-system-design-naming.md)** (adr)

## planning

- **[ADR-0007: Canonical Skills Migration Plan](adrs/ADR-0007-skills-canonical-plan.md)** (adr)
- **[ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes](adrs/ADR-0021-beta-ships-first-priority-lock.md)** (adr)

## plugin-lifecycle

- **[OmniMemory Runtime Plugin System](reference/omnimemory-runtime-plugins.md)** (reference)

## postgres

- **[ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops](adrs/ADR-0026-two-databases-tenant-vs-internal.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)

## pr

- **[Bulk PR operations — mandatory throttled path (<ticket>)](runbooks/bulk-pr-operations.md)** (runbook)

## pre-commit

- **[ADR-0006: Skill Liveness Validator Home](adrs/ADR-0006-skill-liveness-validator-home.md)** (adr)
- **[ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)](adrs/ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md)** (adr)

## pre-merge

- **[ADR-0020: Branch-Preview Verification (proof_class=branch-preview)](adrs/ADR-0020-branch-preview-verification.md)** (adr)

## prioritization

- **[ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes](adrs/ADR-0021-beta-ships-first-priority-lock.md)** (adr)

## profile

- **[Judge Compose Profile](runbooks/judge-compose-profile.md)** (runbook)

## projection

- **[Ingestion Is Not Interpretation](pivots/PIVOT-0001-ingestion-is-not-interpretation.md)** (pivot)
- **[Reducers Own State Progression](pivots/PIVOT-0004-reducers-own-state-progression.md)** (pivot)

## projection-authority

- **[Authoritative Projections Own Truth](doctrine/authoritative-projections-own-truth.md)** (doctrine)
- **[Cursors Represent Projection Progress](doctrine/cursors-represent-projection-progress.md)** (doctrine)
- **[State Is a Materialized Projection](doctrine/state-is-materialized-projection.md)** (doctrine)

## projections

- **[ADR-0003: Registration Runtime / Registry Boundary](adrs/ADR-0003-registration-runtime-registry-boundary.md)** (adr)
- **[ADR-0004: Registry-Owned Consumer Surface](adrs/ADR-0004-registry-owned-consumer-surface.md)** (adr)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)
- **[Dashboard Authority Collapse](pivots/PIVOT-0002-dashboard-authority-collapse.md)** (pivot)
- **[Event Streams Are Not Authoritative State](pivots/PIVOT-0005-event-streams-are-not-authoritative-state.md)** (pivot)
- **[ONEX Core Terminology](reference/onex-terminology.md)** (reference)

## proof-class

- **[ADR-0020: Branch-Preview Verification (proof_class=branch-preview)](adrs/ADR-0020-branch-preview-verification.md)** (adr)

## protocols

- **[ADR-0030: Protocol-Based Dependency Injection Architecture](adrs/ADR-0030-protocol-based-di-architecture.md)** (adr)

## publishing

- **[Snapshot Publishing Architecture](architecture/snapshot-publishing.md)** (architecture)

## pydantic

- **[ADR-0031: Centralized Field Limit Constants](adrs/ADR-0031-centralized-field-limit-constants.md)** (adr)
- **[ADR-0032: Reducer Output Exception Consistency](adrs/ADR-0032-reducer-output-exception-consistency.md)** (adr)
- **[ADR-0036: Context Mutability Design Decision](adrs/ADR-0036-context-mutability-design-decision.md)** (adr)
- **[ADR-0037: Validator Error Handling with ModelOnexError](adrs/ADR-0037-validator-error-handling-modelonexerror.md)** (adr)
- **[Typed-Metadata Policy](reference/typed-metadata-policy.md)** (reference)

## pypi

- **[PyPI pull-through cache (egress) rollout — <ticket> C1](runbooks/pypi-cache-egress-rollout.md)** (runbook)

## pytest

- **[Async Hang Debugging Guide](guides/async-hang-debugging.md)** (guide)

## python

- **[Async Hang Debugging Guide](guides/async-hang-debugging.md)** (guide)

## qdrant

- **[OmniIntelligence Deterministic Code Projection v2](architecture/omniintelligence-code-projection-v2.md)** (architecture)
- **[OmniMemory Data Ownership](reference/omnimemory-memory-data-ownership.md)** (reference)

## raw-events

- **[Event Streams Are Not Authoritative State](pivots/PIVOT-0005-event-streams-are-not-authoritative-state.md)** (pivot)

## reaper

- **[Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)](runbooks/worktree-reaper-two-layer-gc.md)** (runbook)

## receipt

- **[Repowise Freshness Receipt](runbooks/repowise-freshness-receipt.md)** (runbook)

## receipt-gate

- **[ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only](adrs/ADR-0019-no-self-authored-evidence.md)** (adr)

## receipts

- **[ADR-0002: Data Verification Node Invocation Policy](adrs/ADR-0002-data-verification-invocation.md)** (adr)
- **[ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)](adrs/ADR-0025-occ-validator-redesign-option-a.md)** (adr)
- **[ADR-0028: Receipt Type Consolidation onto ModelDodReceipt](adrs/ADR-0028-receipt-type-consolidation.md)** (adr)
- **[Completion Requires Durable Evidence](pivots/PIVOT-0003-completion-requires-durable-evidence.md)** (pivot)
- **[Application database cutover receipts](runbooks/application-database-cutover-receipts.md)** (runbook)

## reconnect

- **[Kafka/Redpanda Reconnect Tuning and Broker Recovery](runbooks/kafka-reconnect-and-broker-recovery.md)** (runbook)

## recursive-system-design

- **[ADR-0011: Name the Discipline RSD = Recursive System Design](adrs/ADR-0011-rsd-recursive-system-design-naming.md)** (adr)

## reducers

- **[ADR-0032: Reducer Output Exception Consistency](adrs/ADR-0032-reducer-output-exception-consistency.md)** (adr)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)
- **[Reducers Own State Progression](pivots/PIVOT-0004-reducers-own-state-progression.md)** (pivot)

## refresh

- **[Stability-Lane Refresh (<ticket> / <ticket>)](runbooks/stability-lane-refresh.md)** (runbook)

## registration

- **[ADR-0003: Registration Runtime / Registry Boundary](adrs/ADR-0003-registration-runtime-registry-boundary.md)** (adr)
- **[ADR-0033: Registration Trigger Architecture](adrs/ADR-0033-registration-trigger-architecture.md)** (adr)
- **[REGISTRATION WORKFLOW](architecture/registration-workflow.md)** (architecture)
- **[2-Way Registration: A Complete ONEX Example](guides/registration-example.md)** (guide)

## registry

- **[ADR-0003: Registration Runtime / Registry Boundary](adrs/ADR-0003-registration-runtime-registry-boundary.md)** (adr)
- **[ADR-0004: Registry-Owned Consumer Surface](adrs/ADR-0004-registry-owned-consumer-surface.md)** (adr)

## release-coordination

- **[Cross-Repo Merge Dependency Graph](reference/merge-dependency-graph.md)** (reference)

## replay

- **[Ingestion Is Not Interpretation](pivots/PIVOT-0001-ingestion-is-not-interpretation.md)** (pivot)
- **[Reducers Own State Progression](pivots/PIVOT-0004-reducers-own-state-progression.md)** (pivot)

## replay-correctness

- **[Canonical Reducers Win](doctrine/canonical-reducers-win.md)** (doctrine)
- **[Systems Must Be Deterministic Under Replay](doctrine/deterministic-under-replay.md)** (doctrine)
- **[Ordering Must Be Explicit and Contracted](doctrine/ordering-must-be-explicit.md)** (doctrine)
- **[Reducers Define State Progression](doctrine/reducers-define-state-progression.md)** (doctrine)

## repo-boundaries

- **[omniclaude Repo Charter](architecture/omniclaude-repo-charter.md)** (architecture)

## repositories

- **[Repository Registry](reference/repository-registry.md)** (reference)

## repowise

- **[Repowise Freshness Receipt](runbooks/repowise-freshness-receipt.md)** (runbook)

## required-status-checks

- **[ADR-0010: Enforcement and Merge-Policy Parity Ratchet](adrs/ADR-0010-required-context-parity-ratchet.md)** (adr)

## reseed

- **[Volume Config Drift Gate + Re-seed Procedure](runbooks/volume-config-drift-and-reseed.md)** (runbook)

## resilience

- **[Kafka/Redpanda Reconnect Tuning and Broker Recovery](runbooks/kafka-reconnect-and-broker-recovery.md)** (runbook)

## risk-mitigation

- **[ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)](adrs/ADR-0038-ci-workflow-modification-risk.md)** (adr)

## rls

- **[ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops](adrs/ADR-0026-two-databases-tenant-vs-internal.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)

## roadmap

- **[ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes](adrs/ADR-0021-beta-ships-first-priority-lock.md)** (adr)

## rollout

- **[PyPI pull-through cache (egress) rollout — <ticket> C1](runbooks/pypi-cache-egress-rollout.md)** (runbook)
- **[Runner-fleet local DNS cache rollout — <ticket>](runbooks/runner-dns-cache-rollout.md)** (runbook)

## root-cause

- **[ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock](adrs/ADR-0024-merge-stall-tooling-not-capacity.md)** (adr)

## routing

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)
- **[ADR-0009: Complexity-Aware Delegation Routing](adrs/ADR-0009-complexity-aware-delegation-routing.md)** (adr)
- **[Agent Routing Architecture](architecture/agent-routing-architecture.md)** (architecture)
- **[Event-Driven Agent Routing Architecture Proposal](architecture/event-driven-routing-proposal.md)** (architecture)
- **[Agent Routing Architecture - Visual Comparison](architecture/routing-architecture-comparison.md)** (architecture)

## rsd

- **[ADR-0010: Adaptive Recursive Contract Bisection (Bisect-on-Contract-Failure)](adrs/ADR-0010-adaptive-recursive-contract-bisection.md)** (adr)
- **[ADR-0011: Name the Discipline RSD = Recursive System Design](adrs/ADR-0011-rsd-recursive-system-design-naming.md)** (adr)
- **[ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing](adrs/ADR-0012-seams-first-class.md)** (adr)
- **[ADR-0013: No Driver Seat — Deterministic FSM Control Plane, LLMs as Gated Candidate Generators](adrs/ADR-0013-deterministic-fsm-control-plane.md)** (adr)
- **[ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug](adrs/ADR-0014-factory-economics-frontier-fissions-locals-build.md)** (adr)

## rule-7a

- **[ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy](adrs/ADR-0016-one-contract-configured-pilot.md)** (adr)

## runbook

- **[ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock](adrs/ADR-0024-merge-stall-tooling-not-capacity.md)** (adr)

## runner

- **[Runner disk-admission gate (<ticket>)](runbooks/runner-disk-admission-gate.md)** (runbook)
- **[Runner-fleet local DNS cache rollout — <ticket>](runbooks/runner-dns-cache-rollout.md)** (runbook)
- **[Runner fleet listener liveness (<ticket>)](runbooks/runner-fleet-listener-liveness.md)** (runbook)

## runners

- **[ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock](adrs/ADR-0024-merge-stall-tooling-not-capacity.md)** (adr)

## runtime

- **[ADR-0003: Registration Runtime / Registry Boundary](adrs/ADR-0003-registration-runtime-registry-boundary.md)** (adr)
- **[ONEX Architecture Overview](architecture/onex-runtime-overview.md)** (architecture)
- **[OmniMemory Runtime Plugin System](reference/omnimemory-runtime-plugins.md)** (reference)
- **[ONEX Core Terminology](reference/onex-terminology.md)** (reference)
- **[Stability-Test Runtime Lane](runbooks/stability-test-runtime-lane.md)** (runbook)

## runtime-isolation

- **[Runtime Complexity Must Be Isolated](doctrine/runtime-complexity-isolated.md)** (doctrine)

## schema-consolidation

- **[ADR-0028: Receipt Type Consolidation onto ModelDodReceipt](adrs/ADR-0028-receipt-type-consolidation.md)** (adr)

## seam-binding

- **[Dual-Binding Test Cases — the Harness Convention](reference/dual-binding-cases.md)** (reference)

## seams

- **[ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing](adrs/ADR-0012-seams-first-class.md)** (adr)

## secrets

- **[ADR-0008: Delegation Config Authority and Budget-Aware Tier Cost](adrs/ADR-0008-delegation-config-authority-and-budget-aware-tier-cost.md)** (adr)

## selective-testing

- **[ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing](adrs/ADR-0012-seams-first-class.md)** (adr)

## self-extending-agent

- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## sentinel-pattern

- **[ADR-0032: Reducer Output Exception Consistency](adrs/ADR-0032-reducer-output-exception-consistency.md)** (adr)

## service

- **[MCP Service Architecture](architecture/mcp-service-architecture.md)** (architecture)

## service-boundaries

- **[Service Ownership & Boundaries](architecture/service-boundaries.md)** (architecture)

## service-boundary

- **[DB Boundary Policy](reference/db-boundary-policy.md)** (reference)

## service-registry

- **[ADR-0030: Protocol-Based Dependency Injection Architecture](adrs/ADR-0030-protocol-based-di-architecture.md)** (adr)

## shadow-mode

- **[ADR-0009: Complexity-Aware Delegation Routing](adrs/ADR-0009-complexity-aware-delegation-routing.md)** (adr)

## shared

- **[Untitled](architecture/shared-enum-ownership.md)** (architecture)

## shift-left

- **[ADR-0022: Shift Defect-Detection Left + OCC Evidence-Only Fast-Lane (WS-E Build-Efficiency)](adrs/ADR-0022-shift-left-and-occ-evidence-only-fast-lane.md)** (adr)

## skill

- **[Node-skill package co-install (omnimarket) — <ticket>](runbooks/node-skill-package-install.md)** (runbook)

## skills

- **[ADR-0006: Skill Liveness Validator Home](adrs/ADR-0006-skill-liveness-validator-home.md)** (adr)
- **[ADR-0007: Canonical Skills Migration Plan](adrs/ADR-0007-skills-canonical-plan.md)** (adr)
- **[Skill Lifecycle: When a Skill Stays in omniclaude vs. Moves to omnimarket](architecture/omniclaude-skill-lifecycle.md)** (architecture)
- **[Adding a Skill](guides/adding-a-skill.md)** (guide)

## snapshot

- **[Snapshot Publishing Architecture](architecture/snapshot-publishing.md)** (architecture)

## stability

- **[Stability-Lane Refresh (<ticket> / <ticket>)](runbooks/stability-lane-refresh.md)** (runbook)
- **[Stability-Test Runtime Lane](runbooks/stability-test-runtime-lane.md)** (runbook)

## standards

- **[Event Envelope Canonical Field Names](reference/event-envelope-field-names.md)** (reference)
- **[Test Discipline](reference/omniclaude-test-discipline.md)** (reference)
- **[Verification Doctrine](reference/omniclaude-verification-doctrine.md)** (reference)

## state

- **[Reducers Own State Progression](pivots/PIVOT-0004-reducers-own-state-progression.md)** (pivot)

## status-taxonomy

- **[ADR-0035: Status Taxonomy and Categorical Organization](adrs/ADR-0035-status-taxonomy-and-categorical-organization.md)** (adr)

## steel-onslaught

- **[ADR-0015: Steel Onslaught Live Play Is LLM-Driven and Non-Deterministic](adrs/ADR-0015-steel-live-play-non-deterministic.md)** (adr)
- **[ADR-0016: One Contract-Configured Pilot (ModelPilot + EnumPilotKind), No Pilot Class Hierarchy](adrs/ADR-0016-one-contract-configured-pilot.md)** (adr)
- **[ADR-0017: No Deterministic Champion in Live Play; Learning Loop Repointed at LLM Pilots](adrs/ADR-0017-no-deterministic-champion-llm-pilots.md)** (adr)

## streaming

- **[ONEX Event Streaming Topics - Specification (v1)](architecture/event-streaming-topics.md)** (architecture)

## supersession

- **[ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)](adrs/ADR-0025-occ-validator-redesign-option-a.md)** (adr)
- **[DoD Receipt Hashing, Append-Only, and Supersession](reference/receipt-hashing-and-supersession.md)** (reference)

## tdd

- **[ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing](adrs/ADR-0012-seams-first-class.md)** (adr)
- **[Technical Design: OmniNode Platform Architecture](architecture/omninode-architecture-technical-design.md)** (architecture)

## tenant-isolation

- **[ADR-0026: Two Databases — Tenant-Facing vs Internal/Ops](adrs/ADR-0026-two-databases-tenant-vs-internal.md)** (adr)
- **[ADR-0027: One Application Database with Contract-Classified Domains](adrs/ADR-0027-one-application-database-domain-separation.md)** (adr)

## terminology

- **[ONEX Core Terminology](reference/onex-terminology.md)** (reference)

## test

- **[Stability-Test Runtime Lane](runbooks/stability-test-runtime-lane.md)** (runbook)

## testing

- **[Testing Guide](guides/omniclaude-testing-guide.md)** (guide)
- **[Dual-Binding Test Cases — the Harness Convention](reference/dual-binding-cases.md)** (reference)
- **[Test Discipline](reference/omniclaude-test-discipline.md)** (reference)

## throughput

- **[ADR-0023: Remove the onex_change_control Merge Queue](adrs/ADR-0023-remove-occ-merge-queue.md)** (adr)

## tier-separation

- **[ADR-0018: Delegation Ladder Acceptance = Escalating-Complexity Graded Benchmark, Local Floor to Paid-Cloud Ceiling](adrs/ADR-0018-delegation-graded-benchmark-ladder.md)** (adr)

## topic

- **[Topic Catalog Architecture](architecture/topic-catalog-architecture.md)** (architecture)

## topic-naming

- **[ONEX Kafka Topic Naming Standard](reference/onex-topic-taxonomy.md)** (reference)

## topics

- **[ONEX Event Streaming Topics - Specification (v1)](architecture/event-streaming-topics.md)** (architecture)

## transport-imports

- **[ADR-0038: CI Workflow Modification Risk (Transport Import Branch Protection)](adrs/ADR-0038-ci-workflow-modification-risk.md)** (adr)

## tree-pr-composition

- **[ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing](adrs/ADR-0012-seams-first-class.md)** (adr)

## truth

- **[Dashboard Authority Collapse](pivots/PIVOT-0002-dashboard-authority-collapse.md)** (pivot)
- **[Event Streams Are Not Authoritative State](pivots/PIVOT-0005-event-streams-are-not-authoritative-state.md)** (pivot)

## truth-verification

- **[Truth Must Be Proven, Not Claimed](doctrine/truth-must-be-proven.md)** (doctrine)

## two

- **[Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)](runbooks/worktree-reaper-two-layer-gc.md)** (runbook)

## type-system

- **[ADR-0035: Status Taxonomy and Categorical Organization](adrs/ADR-0035-status-taxonomy-and-categorical-organization.md)** (adr)

## typed-metadata

- **[Typed-Metadata Policy](reference/typed-metadata-policy.md)** (reference)

## validation

- **[ADR-0031: Centralized Field Limit Constants](adrs/ADR-0031-centralized-field-limit-constants.md)** (adr)

## validator

- **[ADR-0025: OCC Validator Redesign = Option A (Per-Entry Hashing + Append-Only + Supersession/Tombstones)](adrs/ADR-0025-occ-validator-redesign-option-a.md)** (adr)

## validator-enforcement

- **[ADR-0029: Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core)](adrs/ADR-0029-model-b-failing-rollup-validator-enforcement.md)** (adr)

## validators

- **[ADR-0006: Skill Liveness Validator Home](adrs/ADR-0006-skill-liveness-validator-home.md)** (adr)
- **[ADR-0037: Validator Error Handling with ModelOnexError](adrs/ADR-0037-validator-error-handling-modelonexerror.md)** (adr)

## valkey

- **[OmniMemory Data Ownership](reference/omnimemory-memory-data-ownership.md)** (reference)

## vendored

- **[Vendored Node Migration Runbook](runbooks/vendored-node-migrations.md)** (runbook)

## verification

- **[ADR-0019: No Self-Authored Evidence — OCC Companions From Autogen or Independent Verifier Only](adrs/ADR-0019-no-self-authored-evidence.md)** (adr)
- **[ADR-0020: Branch-Preview Verification (proof_class=branch-preview)](adrs/ADR-0020-branch-preview-verification.md)** (adr)
- **[Completion Requires Durable Evidence](pivots/PIVOT-0003-completion-requires-durable-evidence.md)** (pivot)
- **[Verification Doctrine](reference/omniclaude-verification-doctrine.md)** (reference)

## volume

- **[Volume Config Drift Gate + Re-seed Procedure](runbooks/volume-config-drift-and-reseed.md)** (runbook)

## workflow

- **[REGISTRATION WORKFLOW](architecture/registration-workflow.md)** (architecture)

## workflow-state

- **[ADR-0036: Context Mutability Design Decision](adrs/ADR-0036-context-mutability-design-decision.md)** (adr)

## worktree

- **[Merge-Triggered Worktree GC — Two-Layer Model (Event-First + Timer-Backstop)](runbooks/worktree-reaper-two-layer-gc.md)** (runbook)

## ws-b

- **[ADR-0021: Beta Ships First — Priority-Ladder Lock, WS-B Outranks All In-Flight Lanes](adrs/ADR-0021-beta-ships-first-priority-lock.md)** (adr)

## ws-t

- **[ADR-0012: Seams Are First-Class — Seam-Tests-First, Tree-Shaped PRs, Seam-Scoped Testing](adrs/ADR-0012-seams-first-class.md)** (adr)
