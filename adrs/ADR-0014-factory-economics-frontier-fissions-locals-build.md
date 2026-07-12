---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug"
adr_id: ADR-0014
topics: [rsd, economics, delegation, disposable-implementations, distillation]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0014: Factory Economics — Frontier Fissions, Locals Build, Regenerate-Don't-Debug

## Context

Adversarial review of recursive bisection (ADR-0010) raised a fatal-if-unmitigated
economics horn: a cold depth-1 bisect pays `C_local(fail) + C_fission + 2·C_local +
C_compose`, and writing two provably-composing sub-contracts can cost roughly as much as
solving the whole problem (the fission call must read+reason over the entire problem).
Naively, "frontier reserved for just the fission step" hides that fission is not cheap on
a cold split. The operator supplied the economic model that makes the tree defensible.

## Decision

Adopt the economic model **"frontier fissions, locals build":**

- The decomposition tax is **O(splits)**; the savings are **O(leaf implementation
  volume)**. A contract + seam tests is a few hundred tokens; an implementation is 10–50×
  that. So even if every split is frontier-priced, economics favor the tree whenever
  local leaf success is decent — exactly what the 2×2 harness measures.
- **Implementations are disposable; contracts are durable.** A contract-bounded leaf that
  fails does so locally against a named invariant, and at leaf granularity you
  **REGENERATE rather than debug** ("nobody debugs compiler output"). The expensive thing
  is *debugging a monolith smeared across the dependency graph*, not generation.
- **Fission traces are the training corpus.** Frontier fission is the bootstrap, not the
  steady state: learned grain + contract templates decay the tax with use, and
  distillation (frontier teacher → local student) drives the fission tax toward zero on
  owned hardware over time.
- Prefer **wide-shallow splits** when fission confidence allows (serial-depth latency is
  ~log2 depth, minor).

## Alternatives Considered

1. Treat "frontier only for fission" as automatically cheap. Rejected as dishonest: cold fission ≈ frontier-solve; the tax must be paid down by seam-aligned splits (cheap mapping) or a warm learned grain, else the tree degenerates to escalate-tier.
2. Debug failing leaves in place. Rejected: contract-bounded leaves are cheaper to regenerate than to debug; debugging is the costliest tier (frontier/human).
3. Assume "nearly free local" leaves. Qualified, not adopted wholesale: the local fleet is fixed and shared, so local calls carry real MLX wall-clock + opportunity cost; price local at marginal fleet-occupancy and do not credit learning savings until the capture→projection→consumer chain demonstrably reduces the fission-call rate.

## Consequences

Positive: reframes the decomposition tax as an *amortizing* cost (bootstrap → distill →
own), and makes the accumulated verified-decomposition event corpus — not the models
(rentable) — the durable moat. Negative / honest caveats: the steady-state cheapness
depends on an *unbuilt* learning chain (no lineage DTO wired, `roi_overlay` unmerged and
tier-level only, `node_recall_compute` has zero backends); fleet congestion is real; and
the one-shot-at-bounded-complexity claim is measured but bounded (D2 adoption 73.3%,
ratchet canary 2/2 first-try, graded-ladder saturated — the benchmark could not find
bounded tasks hard enough to make local fail, which is itself the trigger-discrimination
risk in ADR-0010).

## Derived From

`docs/plans/2026-07-06-recursive-contract-bisection-micro-factories.md` §8 R4 ("Frontier
fissions, locals build") and R5 ("The expensive thing is debugging, not generation"),
with the E1–E6 economics critiques in §4.2 and the R11 distillation refinement in §9.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Measured data points
(D2 73.3%, ratchet 2/2, graded-ladder 0.980 on the thread-safe TTL-LRU task) are quoted
from the source doc R5; the unbuilt-learning-chain caveats are file-grounded in §2/§4.2.
