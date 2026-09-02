# Architecture

Architecture artifacts are public Technical Design Documents (TDDs). Each one describes the standing technical design of a subsystem or cross-cutting concern of the platform: its primitives, the boundaries between them, how work flows through the runtime, and the proof a correct implementation must produce.

A TDD is not a decision log or a story. It is the structured reference design that an implementer, reviewer, or auditor reads to understand what a part of the platform is *supposed* to be — and the criteria by which a real implementation is judged against that intent.

## What Makes a Good Architecture TDD

A TDD describes a target shape precisely enough that drift from it is detectable. A good TDD captures:

- **Primitives** — the small set of building blocks the design is allowed to use, and nothing else
- **Boundaries** — what each component owns, what it must not own, and where the seams are
- **Runtime flow** — how a request, event, or unit of work moves through the design end to end
- **Proof requirements** — the evidence a conforming implementation must emit to be considered correct

## How Architecture TDDs Relate to Other Artifacts

The knowledge base uses several artifact types that work together. Architecture TDDs sit alongside them but answer a different question:

- **ADRs** record a *single decision* — the context that forced it, the alternatives, and the consequences. A TDD may embody many ADRs, but it is not itself a decision; it is the standing design those decisions add up to.
- **Plans** are *intended implementation paths* — proposed sequences of work with expected evidence. A plan says how to build toward a target; a TDD defines the target itself.
- **Doctrine** are the principles and invariants every artifact must respect. A TDD must not contradict doctrine; when it appears to, the doctrine is reconciled first.

The typical flow: operational pressure and ADRs surface and ratify the pieces → a TDD consolidates them into the standing technical design of a subsystem → plans describe the path to implement it → a cited outcome (a PR, a CI run) proves the implementation matches the design.

## Lifecycle

```
draft → accepted → superseded
                 → deprecated
```

| Status | Meaning |
|--------|---------|
| **draft** | Design is being written or reviewed; not yet the agreed reference. |
| **accepted** | Design is the agreed reference shape for the subsystem and actively governs implementation. |
| **superseded** | A newer TDD replaces this design; the document is kept for provenance and points to its successor. |
| **deprecated** | The design no longer applies and is not replaced by a newer TDD (the subsystem was removed or folded elsewhere). |

A TDD moves from `draft` to `accepted` via PR review. When a later TDD renders an earlier one obsolete, the earlier one is updated to `superseded`; when a design simply stops applying, it is `deprecated`.

## How to Propose a New Architecture TDD

1. Copy `_template.md` to `architecture/short-title.md` — no date in the filename; a TDD is a living reference revised in place, so the authoring date lives in the `date:` frontmatter field only (see [CONTRIBUTING.md](../CONTRIBUTING.md#file-naming-convention)).
2. Fill in the frontmatter: `status: draft`, the `title` (prefixed `Technical Design:`), `date`, and the `topics` / `refs` lists.
3. Write the body sections: Purpose, Scope, Non-Goals, Design Principles, the subsystem-specific design sections, Current Versus Target State, and Acceptance Criteria.
4. Open a PR for review.
5. On approval, change `status` to `accepted` and update any TDD this one supersedes.

Keep a TDD focused on one subsystem or one cross-cutting concern. If background explanation grows long, trim it rather than folding it in — a TDD is the stable reference, not the narrative of how the team got there.

## Current Architecture Designs

| Date | Title | Status |
|------|-------|--------|
| [2026-05-31](omninode-architecture-technical-design.md) | Technical Design: OmniNode Platform Architecture | accepted |

## ONEX kernel architecture (omnibase_core)

The ONEX execution kernel's architecture records, migrated out of the `omnibase_core`
repository so the platform's architecture is documented in one place rather than inside the
package that happens to implement it. They describe the four node archetypes, the contract and
subcontract system, handler and envelope flow, the typed payload and model-action surfaces, and
the platform pattern catalog.

- [`onex-canonical-execution-shapes.md`](onex-canonical-execution-shapes.md) — ONEX Canonical Execution Shapes
- [`onex-claude-code-hook-models.md`](onex-claude-code-hook-models.md) — Claude Code Hooks Architecture
- [`onex-container-types.md`](onex-container-types.md) — Container Types in omnibase_core
- [`onex-contract-stability-spec.md`](onex-contract-stability-spec.md) — Contract Stability Specification
- [`onex-contract-system.md`](onex-contract-system.md) — Contract System
- [`onex-dependency-injection.md`](onex-dependency-injection.md) — Dependency Injection
- [`onex-dependency-inversion.md`](onex-dependency-inversion.md) — Dependency Inversion in ONEX Architecture
- [`onex-dict-str-any-prevention.md`](onex-dict-str-any-prevention.md) — Dict[str, Any] Prevention Guide
- [`onex-ecosystem-directory-structure.md`](onex-ecosystem-directory-structure.md) — ONEX Ecosystem Directory Structure
- [`onex-effect-timeout-behavior.md`](onex-effect-timeout-behavior.md) — Effect Timeout Behavior
- [`onex-envelope-flow-architecture.md`](onex-envelope-flow-architecture.md) — Envelope Flow Architecture
- [`onex-execution-shape-examples.md`](onex-execution-shape-examples.md) — Execution Shape Examples
- [`onex-handler-architecture.md`](onex-handler-architecture.md) — Handler Architecture
- [`onex-handler-classification-file-io-services.md`](onex-handler-classification-file-io-services.md) — Handler Classification: omnibase_core File I/O Services (Epic 3 — Ticket 3.4)
- [`onex-import-compatibility-matrix.md`](onex-import-compatibility-matrix.md) — Import Compatibility Matrix
- [`onex-message-topic-mapping.md`](onex-message-topic-mapping.md) — Message Category to Topic Mapping
- [`onex-mixin-architecture.md`](onex-mixin-architecture.md) — ONEX Mixin Architecture
- [`onex-mixin-classification.md`](onex-mixin-classification.md) — Mixin Classification Reference
- [`onex-modelaction-typed-payloads.md`](onex-modelaction-typed-payloads.md) — ModelAction Typed Payloads
- [`onex-model-action-architecture.md`](onex-model-action-architecture.md) — ModelAction Architecture
- [`onex-model-intent-architecture.md`](onex-model-intent-architecture.md) — ModelIntent Architecture
- [`onex-node-class-hierarchy.md`](onex-node-class-hierarchy.md) — Node Class Hierarchy Guide
- [`onex-node-purity-guarantees.md`](onex-node-purity-guarantees.md) — Node Purity Guarantees
- [`onex-four-node-architecture.md`](onex-four-node-architecture.md) — ONEX Four-Node Architecture Documentation
- [`onex-payload-type-architecture.md`](onex-payload-type-architecture.md) — Payload Type Architecture
- [`onex-protocol-architecture.md`](onex-protocol-architecture.md) — Protocol Architecture
- [`onex-subcontract-architecture.md`](onex-subcontract-architecture.md) — ONEX Subcontract Package Architecture
- [`onex-type-system.md`](onex-type-system.md) — Type System
- [`onex-url-contract-authority.md`](onex-url-contract-authority.md) — URL Contract Authority
- [`onex-validation-protocol-compliance.md`](onex-validation-protocol-compliance.md) — Validation Protocol Compliance
- [`omnibase-core-overview.md`](omnibase-core-overview.md) — Architecture Overview - omnibase_core
- [`onex-operation-bindings-dsl.md`](onex-operation-bindings-dsl.md) — Operation Bindings DSL
- [`onex-anti-patterns.md`](onex-anti-patterns.md) — ONEX Anti-Patterns Documentation
- [`onex-approved-union-patterns.md`](onex-approved-union-patterns.md) — Approved Union Patterns for ONEX Development
- [`onex-circuit-breaker-pattern.md`](onex-circuit-breaker-pattern.md) — Circuit Breaker Pattern for External Dependencies
- [`onex-configuration-management.md`](onex-configuration-management.md) — Environment-Based Configuration Management
- [`onex-custom-bool-pattern.md`](onex-custom-bool-pattern.md) — Custom `__bool__` Pattern for Result Models
- [`onex-event-driven-architecture.md`](onex-event-driven-architecture.md) — Event-Driven Architecture -- omnibase_core
- [`onex-lease-management-pattern.md`](onex-lease-management-pattern.md) — Lease Management Pattern
- [`onex-pure-fsm-reducer-pattern.md`](onex-pure-fsm-reducer-pattern.md) — Pure FSM Reducer Pattern
