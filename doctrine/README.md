# Doctrine

Stable platform principles that govern OmniNode's architecture. Doctrine evolves slowly, informed by pivots, ADRs, and operational learning.

Doctrine files describe invariants: things that must be true for the platform to remain coherent. When a pivot changes the underlying model, the relevant doctrine is updated to reflect the new understanding — and the pivot record captures what changed and why.

## Files

| File | Title | Topics |
|------|-------|--------|
| [truth-must-be-proven.md](truth-must-be-proven.md) | Truth Must Be Proven, Not Claimed | truth-verification |
| [authoritative-projections-own-truth.md](authoritative-projections-own-truth.md) | Authoritative Projections Own Truth | projection-authority |
| [deterministic-under-replay.md](deterministic-under-replay.md) | Systems Must Be Deterministic Under Replay | replay-correctness |
| [ordering-must-be-explicit.md](ordering-must-be-explicit.md) | Ordering Must Be Explicit and Contracted | replay-correctness |
| [reducers-define-state-progression.md](reducers-define-state-progression.md) | Reducers Define State Progression | replay-correctness |
| [state-is-materialized-projection.md](state-is-materialized-projection.md) | State Is a Materialized Projection | projection-authority |
| [contracts-define-reality.md](contracts-define-reality.md) | Contracts Define Reality | contract-governance |
| [cursors-represent-projection-progress.md](cursors-represent-projection-progress.md) | Cursors Represent Projection Progress | projection-authority |
| [fail-fast-and-loud.md](fail-fast-and-loud.md) | Fail Fast and Loud | failure-handling |
| [degrade-safely.md](degrade-safely.md) | Degrade Safely | failure-handling |
| [ingestion-and-interpretation-separate.md](ingestion-and-interpretation-separate.md) | Ingestion and Interpretation Are Separate | ingestion-boundaries |
| [runtime-complexity-isolated.md](runtime-complexity-isolated.md) | Runtime Complexity Must Be Isolated | runtime-isolation |
| [migration-staged-recoverable.md](migration-staged-recoverable.md) | Migration Must Be Staged and Recoverable | migration-safety |
| [canonical-reducers-win.md](canonical-reducers-win.md) | Canonical Reducers Win | replay-correctness |
| [evidence-is-first-class-output.md](evidence-is-first-class-output.md) | Evidence Is a First-Class Output | evidence-systems |
