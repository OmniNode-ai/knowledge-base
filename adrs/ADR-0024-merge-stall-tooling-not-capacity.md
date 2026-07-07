---
type: adr
status: proposed
date: "2026-07-06"
title: "ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock"
adr_id: ADR-0024
topics: [merge-sweep, runners, ci-capacity, root-cause, runbook]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0024: Merge Stall Root Cause = Merge-Sweep Tooling Miss, Not a Capacity Deadlock

## Context

Merges stalled across queue repos for days (core ~2.5 days, infra/OCC ~24.6h, omniclaude
~44.6h). The initial ledger framing called it a ~14h merge-queue deadlock and proposed
options like dequeuing core suites; a probe pass then reframed it as a runner-capacity
starvation backlog (required `merge_group` jobs raw-`queued` 45+ min, never starting). The
operator then supplied the actual root cause.

## Decision

**The merge stall was a merge-sweep TOOLING miss, not a capacity deadlock.** The autonomous
merge-sweep driver (Codex) was running the not-yet-working **skill-based** merge sweep
instead of the **runbook + manual** sweep, so merges were **not being driven at all**.
Resolution: **(1)** drive merges via the runbook/manual sweep until the skill-based path is
fixed (WS-M merge-skill fix, High); **(2)** runner saturation is a real *slowness*
contributor — increase runner count per the runner-capacity plan (48→56→64 phased,
operator-endorsed, home-infra). The prior "dequeue core suites" options and the
"#2219 is the unblocker" read are **withdrawn** — the `uv sync` timeout fix is companion resilience,
not the merge cause.

## Alternatives Considered

1. "~14h merge-queue deadlock; dequeue core suites" (initial ledger). Withdrawn: throughput was measurably nonzero, not a frozen circular deadlock.
2. "Runner-capacity starvation is the dominant cause" (probe reframing). Superseded by the operator correction: capacity is a *slowness* contributor, not the reason merges weren't happening — the sweep simply wasn't driving them.
3. "The `uv sync` timeout (#2219) is the unblocker." Withdrawn: no failed `merge_group` run was observed from it; #2219 is companion resilience (necessary-not-sufficient), not the merge cause.

## Consequences

Positive: the correct fix is applied — the manual/runbook sweep drives merges now, and the
skill-based sweep is fixed separately (unbounded `subprocess.run` on `gh` calls
caused an infinite silent hang; 90s bounds + fail-soft; parity byte-identical vs manual
census) before it is trusted to drive again ("manual/runbook sweep stays the driver until the
released skill proves one supervised merge-drive"). Runner count is increased for genuine
slowness. Negative: a real tooling gap (silent-hang merge sweep) had masqueraded as an
infrastructure deadlock, costing days of merge latency and a wrong first diagnosis — motivating
fail-loud guards (swept-but-zero-merges guard, parallelism).

## Derived From

`docs/plans/ROLLING_SEVEN_DAY_PLAN.md` §3 item 24 ("Break the CI runner-capacity backlog —
DECIDED 2026-07-06: the merge stall was a merge-sweep TOOLING miss, not a capacity deadlock")
and the §6 2026-07-06 ~16:0xZ POST-RE-CUT OPERATOR CORRECTION; runner plan
`docs/plans/2026-07-06-runner-capacity-memory-and-gc-plan.md`.

## Evidence

Hand-driven ADR canary batch (2026-07-06). Source is a dated operator
correction that explicitly withdraws two prior diagnoses; the root cause (unbounded
`subprocess.run` hang) is recorded in the §6 2026-07-06 ~20:15Z entry.

## Related Pivots

- Two prior conclusions overturned this session: the "queue deadlock" framing and the "runner-starvation is the cause" framing were both superseded by the tooling-miss root cause.
