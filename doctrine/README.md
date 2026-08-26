# OmniNode Doctrine

Doctrine documents capture the stable platform principles that govern OmniNode's architecture. These are not guidelines or best practices — they define whether the system is functioning correctly.

## How Doctrine Evolves

Doctrine evolves slowly, informed by:
- **Pivots** — fundamental changes in architectural understanding
- **ADRs** — specific decisions that test or extend doctrine
- **Replay failures** — operational evidence that existing doctrine is incomplete
- **Runtime evidence** — production behavior that reveals gaps

A doctrine update is significant. It means the platform's understanding of correctness has changed.

## Principles

| # | Principle | File | Core Topic |
|---|-----------|------|------------|
| 1 | Truth Must Be Proven | [truth-must-be-proven.md](truth-must-be-proven.md) | Truth verification |
| 2 | Authoritative Projections Own Truth | [authoritative-projections-own-truth.md](authoritative-projections-own-truth.md) | Projection authority |
| 3 | Deterministic Under Replay | [deterministic-under-replay.md](deterministic-under-replay.md) | Replay correctness |
| 4 | Ordering Must Be Explicit | [ordering-must-be-explicit.md](ordering-must-be-explicit.md) | Replay correctness |
| 5 | Reducers Define State Progression | [reducers-define-state-progression.md](reducers-define-state-progression.md) | Replay correctness |
| 6 | State Is a Materialized Projection | [state-is-materialized-projection.md](state-is-materialized-projection.md) | Projection authority |
| 7 | Contracts Define Reality | [contracts-define-reality.md](contracts-define-reality.md) | Contract governance |
| 8 | Cursors Represent Projection Progress | [cursors-represent-projection-progress.md](cursors-represent-projection-progress.md) | Projection authority |
| 9 | Fail Fast and Loud | [fail-fast-and-loud.md](fail-fast-and-loud.md) | Failure handling |
| 10 | Degrade Safely | [degrade-safely.md](degrade-safely.md) | Failure handling |
| 11 | Ingestion and Interpretation Are Separate | [ingestion-and-interpretation-separate.md](ingestion-and-interpretation-separate.md) | Ingestion boundaries |
| 12 | Runtime Complexity Must Be Isolated | [runtime-complexity-isolated.md](runtime-complexity-isolated.md) | Runtime isolation |
| 13 | Migration Must Be Staged and Recoverable | [migration-staged-recoverable.md](migration-staged-recoverable.md) | Migration safety |
| 14 | Canonical Reducers Win | [canonical-reducers-win.md](canonical-reducers-win.md) | Replay correctness |
| 15 | Evidence Is a First-Class Output | [evidence-is-first-class-output.md](evidence-is-first-class-output.md) | Evidence systems |

## Topic Clusters

### Replay Correctness
Principles 3, 4, 5, 14 — ensuring the system produces identical state given the same inputs.

- [deterministic-under-replay.md](deterministic-under-replay.md) — the base guarantee
- [ordering-must-be-explicit.md](ordering-must-be-explicit.md) — ordering contracts enable determinism
- [reducers-define-state-progression.md](reducers-define-state-progression.md) — reducers are the mechanism
- [canonical-reducers-win.md](canonical-reducers-win.md) — conflict resolution under reducer semantics

### Projection Authority
Principles 2, 6, 8 — projections own truth, clients render it.

- [authoritative-projections-own-truth.md](authoritative-projections-own-truth.md) — projections are the source of truth
- [state-is-materialized-projection.md](state-is-materialized-projection.md) — state is always an explicit construction
- [cursors-represent-projection-progress.md](cursors-represent-projection-progress.md) — progress tracking for projections

### Contract Governance
Principle 7 — every boundary is governed by explicit contracts.

- [contracts-define-reality.md](contracts-define-reality.md) — no implicit assumptions at boundaries

### Failure Handling
Principles 9, 10 — correctness over availability, explicit degradation.

- [fail-fast-and-loud.md](fail-fast-and-loud.md) — detect and surface violations immediately
- [degrade-safely.md](degrade-safely.md) — when failure occurs, degrade explicitly

### Evidence Systems
Principle 15 — every completion claim requires durable, inspectable evidence.

- [evidence-is-first-class-output.md](evidence-is-first-class-output.md) — evidence is an output, not a side effect

### Ingestion Boundaries
Principle 11 — transport and state logic are separate concerns.

- [ingestion-and-interpretation-separate.md](ingestion-and-interpretation-separate.md) — consumers deliver, projections interpret

### Runtime Isolation
Principle 12 — complexity stays in controlled layers.

- [runtime-complexity-isolated.md](runtime-complexity-isolated.md) — mocks do not prove system truth

### Migration Safety
Principle 13 — no system is replaced without proof.

- [migration-staged-recoverable.md](migration-staged-recoverable.md) — parallel validation before deletion

### Truth Verification
Principle 1 — truth requires durable, observable evidence.

- [truth-must-be-proven.md](truth-must-be-proven.md) — status is not truth

## Relationship to Other Artifacts

- Doctrine constrains **ADRs** — decisions must be compatible with active doctrine
- Doctrine emerges from **Pivots** — fundamental understanding shifts produce new principles
- Doctrine is validated by outcomes — runtime behavior proves principles hold, cited (a PR, a CI run, an OCC receipt) rather than hosted here; OCC (`onex_change_control`) is the sole evidence authority
- Doctrine is tested by operational pressure — recurring incidents and friction are what surface a candidate Pivot or ADR in the first place
