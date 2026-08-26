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

1. Copy `_template.md` to `architecture/YYYY-MM-DD-short-title.md` (date the design was authored).
2. Fill in the frontmatter: `status: draft`, the `title` (prefixed `Technical Design:`), `date`, and the `topics` / `refs` lists.
3. Write the body sections: Purpose, Scope, Non-Goals, Design Principles, the subsystem-specific design sections, Current Versus Target State, and Acceptance Criteria.
4. Open a PR for review.
5. On approval, change `status` to `accepted` and update any TDD this one supersedes.

Keep a TDD focused on one subsystem or one cross-cutting concern. If background explanation grows long, trim it rather than folding it in — a TDD is the stable reference, not the narrative of how the team got there.

## Current Architecture Designs

| Date | Title | Status |
|------|-------|--------|
| [2026-05-31](2026-05-31-omninode-architecture-technical-design.md) | Technical Design: OmniNode Platform Architecture | accepted |
