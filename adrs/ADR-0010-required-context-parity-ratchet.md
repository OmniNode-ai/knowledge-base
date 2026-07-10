---
type: adr
status: proposed
date: "2026-07-10"
title: "ADR-0010: Enforcement and Merge-Policy Parity Ratchet"
adr_id: ADR-0010
topics: [ci, branch-protection, enforcement, parity, governance, merge-gates, required-status-checks, merge-queue, config-as-data]
refs:
  - doctrine/truth-must-be-proven.md
  - doctrine/evidence-is-first-class-output.md
  - doctrine/fail-fast-and-loud.md
  - doctrine/contracts-define-reality.md
supersedes: []
superseded_by: []
---

# ADR-0010: Enforcement and Merge-Policy Parity Ratchet

(Make the full per-repo branch-protection policy — the load-bearing gates we CLAIM
are enforced AND the decided merge-queue/strict policy — deterministic config-as-data,
mechanically asserted against live state by one parity ratchet.)

## Context

Our agent operating doctrine names a set of load-bearing safety gates that MUST
block a merge — most importantly a **deploy-gate** (rejects a pull request that
mutates a runtime contract without deploy/DoD evidence) and a
**reject-skip-token** gate (rejects a pull request body carrying a
`[skip-*]` bypass token). The doctrine asserts these were "wired as required
status checks" across the runtime repositories.

A read-only enforcement-parity audit on 2026-07-10 tested that assertion against
live GitHub branch protection and **falsified it for two of the four runtime
repos.** The finding is airtight (every probe was a read-only `gh api` call):

- On both **omnimarket** and **omniclaude**, the `dev` branch's
  `required_status_checks.contexts` was **exactly `["CI Summary"]`** — nothing
  else. `deploy-gate` and the reject-skip token check were **not** required
  contexts.
- Those two gates each live in their **own separate workflow files**, and a
  GitHub `needs:` dependency is **intra-workflow only** — a `needs:` inside the
  `CI Summary` job (in a different workflow) can never reference a job in another
  workflow file. So the gates were **structurally incapable** of being enforced
  transitively through `CI Summary` either.
- **Net effect:** on those two repos a *red* `deploy-gate`, or a pull request
  carrying a `[skip-deploy-gate: …]` bypass token, left `CI Summary` green and
  the pull request **mergeable**. The doctrine's enforcement claim was false in
  live state.
- The contrast repos (**omnibase_core**, **omnibase_infra**) got it right: they
  require `deploy-gate` and the reject-skip context **directly** in
  `required_status_checks` — the only correct pattern for a cross-workflow gate.

This is not a one-off typo. **The root cause is architectural: the org runs two
mutually incompatible enforcement philosophies simultaneously, with nothing
reconciling them.**

- **Philosophy #1 — "the umbrella job is the single required gate."** Everything
  rolls up into one aggregator job (`CI Summary`) via `needs:`; branch protection
  requires only that aggregator. A prose, per-repo `required-checks.yaml` manifest
  documents this model. omnimarket + omniclaude follow it. **Its fatal flaw:** a
  `needs:` closure is intra-workflow only, so any load-bearing gate that lives in
  its **own** workflow file (deploy-gate, reject-skip, and others) can never be
  rolled into the aggregator and is therefore silently unenforced under this
  model.
- **Philosophy #2 — "each load-bearing gate is its own required context."**
  omnibase_core + omnibase_infra follow it, requiring each cross-workflow gate
  directly. This is the only model that actually enforces a cross-workflow gate.

The doctrine's claims assume Philosophy #2; the two affected repos were
configured under Philosophy #1. **There is no mechanical assertion anywhere that
"the load-bearing gates a repo claims are enforced are actually in its
`required_status_checks` — directly, or via a required aggregator's `needs:`
closure."** The only existing guard is a periodic branch-protection auditor that
checks the *opposite* direction (a required context that no longer reports a
check-run) and is itself advisory-only (scheduled, report-only, not a required
context on any repo). The gap that let this happen is unguarded.

## Decision

**1. Reconcile toward Philosophy #2 as the canonical model for cross-workflow
gates.** A gate that lives in its own workflow file MUST be a **direct** required
context. A gate that genuinely rolls up into an aggregator may be covered
**transitively**, but only when its emitting job is provably inside that
aggregator's intra-workflow `needs:` closure. "It runs in CI" is never
sufficient; "it is required, directly or by proven closure" is the bar.

**2. Make that reconciliation mechanically self-enforcing via a required-context
parity ratchet**, so the doctrine's enforcement claims can never again silently
diverge from live branch protection. The parity ratchet is built
**report-then-enforce**: it ships REPORT-ONLY first (compute + print findings,
never mutate branch protection, never fail a build), and is flipped to a
fail-closed required gate in a separate, deliberate step once the reported
findings are remediated.

**3. Express the FULL per-repo branch-protection policy as deterministic
config-as-data — one manifest, two dimensions.** The same principle that governs
the rest of the architecture (deterministic behavior is declared as data, not
scattered across prose and human ritual) applies to branch protection. The single
machine-asserted manifest is `{repo → branch → {load_bearing_gates[], merge_policy}}`:

- **`load_bearing_gates[]`** — the safety gates (each `coverage: direct | needs_child`),
  as in decision 1.
- **`merge_policy: {queue: enabled|disabled, strict: bool}`** — the *decided* merge
  policy. This records what the policy IS and lets the ratchet flag live drift from
  it, exactly as it does for gates.

This replaces the scattered, honor-system, per-repo prose manifests **and** the
recurring human "re-verify branch protection after merges" ritual (with its
perpetual staleness).

**3a. The decided merge policy: dev merge queues OFF, `strict` as the lighter
guard.** A merge queue's *only* unique value is the `merge_group` event's
re-test-against-latest-base — and that is precisely what wedges a saturated
self-hosted runner fleet (queue entries sit `AWAITING_CHECKS` while the fleet is
busy, stalling all downstream merges). Crucially, the load-bearing required
contexts fire on the `pull_request` event, **not** only on `merge_group`, so
disabling the dev merge queue loses **no** enforcement — a precedent already
established when a governance repo's dev queue was disabled with zero enforcement
lost. The lighter, non-wedging replacement for combine-breakage protection is
`strict` (require-branches-up-to-date), decided ON for the two dashboard repos.
The manifest therefore declares `queue: disabled` on all dev branches and `strict`
per the decision; the ratchet flags any live divergence (**QUEUE_DRIFT** /
**STRICT_DRIFT**).

**4. Host the enforcement on the correct architectural surface, not the
nearest-named one.** The live probe reads external, mutable, network-fetched
branch-protection state. It therefore belongs on an EFFECT surface (a
GitHub-hosted job doing `gh api` probes), extending the **existing** periodic
branch-protection auditor rather than creating a new surface. The static
architectural-invariant catalogue (a `purity: pure`, source-file-only scanner)
**cannot** host the probe without violating its purity contract — so the
catalogue holds only the *declaration* of the principle and points to the
enforcement surface.

## Alternatives Considered

1. **Manually add the two missing contexts and move on.** Necessary but
   insufficient: it fixes today's two instances but leaves the *class* of drift
   unguarded. Branch protection can be re-edited out-of-band (web UI, API) with
   no pull request, and a future workflow rename can re-orphan a required
   context. The immediate remediation is real but is a separate, operator-gated
   branch-protection mutation; this ADR is about the durable guard.
2. **Bolt the live probe onto the static architectural-invariant node.** Rejected
   on purity grounds: that node is a deterministic, network-free source-file
   scanner. Fetching live branch-protection state is external non-deterministic
   I/O and would break its purity contract. The principle is registered there as
   governance-of-record only; the probe lives on the EFFECT auditor.
3. **Keep the per-repo prose `required-checks.yaml` honor system.** Rejected: it
   is prose ("if you rename a job you MUST update both this file and branch
   protection"), was already stale, existed in only some repos, and documented
   the very philosophy (#1) that produced the gap. A footnote is not a gate.
4. **Enforce as a required gate immediately (no report-only phase).** Rejected:
   flipping a fail-closed required context across repos while findings are still
   open would wedge merges. Report-then-enforce surfaces the true findings, lets
   remediation land first, then flips the gate deliberately.

## Ratchet Design

**Declarative manifest (single source of truth).** One machine-asserted file:

```yaml
repos:
  <repo>:
    <branch>:
      merge_policy:
        queue: disabled           # enabled | disabled — decided policy
        strict: false             # require-branches-up-to-date
      load_bearing_gates:
        - context: "deploy-gate / deploy-gate"   # or the repo's inline job name
          coverage: direct          # MUST appear literally in required_status_checks
          rule: "<doctrine reference>"
        - context: "occ-preflight"
          coverage: needs_child     # enforced transitively via an aggregator
          aggregator: "CI Summary"
          aggregator_workflow: "ci.yml"
          aggregator_job_id: "ci-summary"
          gate_job_id: "occ-preflight"
```

**Assertion logic (pure, unit-tested), extending the existing auditor library.**
For each `repo → branch`, the enforcement dimension checks each gate:

- **`coverage: direct`** → assert the gate context is in the live
  `required_status_checks.contexts`, with **reusable-context normalization** — a
  required context of the form `"caller / reusable / leaf"` is treated as
  equivalent to its trailing `leaf` segment, mirroring GitHub's own fuzzy
  matching, so the check does not itself false-positive on the repos that wired
  the gate correctly. A miss is a **MISSING** finding.
- **`coverage: needs_child`** → parse the aggregator's workflow, compute the
  **transitive `needs:` closure** of the aggregator job, and assert both that
  the aggregator context is itself required and that the gate's emitting job is
  in that closure. A miss is a **NEEDS-CLOSURE** finding. (This is exactly the
  check that proves a cross-workflow gate is *impossible* to cover via an
  aggregator — its job is never in the closure.)
- A declared branch with **no protection object at all** yields an
  **UNPROTECTED** finding.

And the **merge-policy dimension** checks the declared `merge_policy` against live
branch protection (`strict`) and the live merge-queue state (a GraphQL
`mergeQueue(branch:)` probe): a live queue where the policy says `disabled`
(or vice versa) is a **QUEUE_DRIFT** finding; a live `strict` that differs from the
declared value is a **STRICT_DRIFT** finding. Either key may be omitted to leave
that dimension unasserted; an unresolvable live value is reported INDETERMINATE,
never a false drift.

**Two complementary run surfaces (neither alone is sufficient).**

- A **per-pull-request required status check** (the enforcing follow-up) catches
  drift introduced *through* a pull request — a workflow rename that orphans a
  required context, or a manifest edit that drops a gate — before merge, fail-
  closed at the merge boundary.
- A **scheduled backstop** re-asserts across all repos, because branch protection
  can be changed **out-of-band** with no pull request at all; on drift it fails
  the run and auto-files a tracking ticket.

**Dogfood placement (declaration vs. enforcement split).**

- **Declaration:** a governance-of-record entry, `ARCH-006 required_context_parity`,
  is added to the architectural-invariant catalogue. It is loaded and counted but
  has **no checker** — the pure node emits no violation for it; it exists to keep
  the catalogue the single index of "what must be true" and to point at the
  enforcement surface.
- **Enforcement:** the parity assertion + manifest + report-only CLI extend the
  existing periodic branch-protection auditor (an EFFECT surface), wired as a
  non-blocking report step first.

## Consequences

**What improves.**

- The doctrine's enforcement claims become **mechanically checkable** against live
  state instead of asserted in prose. The confirmed two-repo gap is now reported
  automatically and reproducibly.
- Divergence between "gates we claim are enforced" and "gates branch protection
  actually requires" becomes a red check, not a documentation footnote discovered
  by a manual audit months later.
- The single declarative manifest replaces the scattered, stale, per-repo prose
  manifests and retires the recurring human "re-verify branch protection after
  merges" ritual and its perpetual-staleness tax.
- The declaration/enforcement split keeps each surface honest: the pure invariant
  catalogue stays pure; the external-state probe lives where external I/O belongs.

**What becomes harder / the costs.**

- The manifest is now a maintained artifact: adding a new load-bearing gate means
  adding a manifest entry (which is the point — it makes the claim explicit and
  checked).
- The `needs_child` check must fetch and parse workflow files; a fetch/parse
  failure is reported INDETERMINATE (never a false MISSING), so the check
  degrades safely rather than blocking spuriously.
- Flipping the ratchet from report-only to enforcing is a deliberate, separate
  step that must follow remediation of the reported findings; shipping the gate
  enforcing-first would wedge merges.

**Explicitly out of scope for the ratchet itself.**

- The immediate remediation (adding the missing required contexts to the two
  affected repos) mutates branch protection and is operator/admin-gated; it is
  tracked and landed separately from the report-only ratchet.

## Related Pivots

- The audit overturned the standing assumption that the deploy-gate and
  reject-skip token gate were "required across all four runtime repos." They are
  required on two; the claim was false for the other two. Any future doctrine
  edit that re-asserts blanket enforcement must cite the parity report, not prose.

## Related Doctrine

- `doctrine/truth-must-be-proven.md` — an enforcement claim is a truth claim; it
  must be proven against live state (a `gh api` probe), not asserted in a rule
  file. The ratchet is that proof.
- `doctrine/evidence-is-first-class-output.md` — the declarative manifest plus the
  machine-checked report are durable, first-class evidence of what is (and is not)
  enforced, replacing an honor-system footnote.
- `doctrine/fail-fast-and-loud.md` — the enforcing follow-up fails closed at the
  merge boundary; the scheduled backstop fails loudly and files a ticket on
  out-of-band drift.
- `doctrine/contracts-define-reality.md` — the load-bearing gate set is expressed
  as one declarative contract (the manifest), and reality (branch protection) is
  asserted against it.

## Derived From

This ADR is anchored to a read-only enforcement-parity audit (2026-07-10) whose
findings are reproduced by the shipped report-only ratchet, and to the periodic
branch-protection auditor it extends. The tracking work items are cited in the
accompanying pull requests.

## Evidence

Verified 2026-07-10 via read-only `gh api` probes and confirmed by the shipped
report-only tool:

- `omnimarket` `dev` `required_status_checks.contexts` == `["CI Summary"]`
  (deploy-gate + reject-skip absent).
- `omniclaude` `dev` `required_status_checks.contexts` == `["CI Summary"]`
  (deploy-gate + reject-skip absent).
- `omnibase_core` and `omnibase_infra` `dev` require `deploy-gate` and the
  reject-skip context **directly** (the correct cross-workflow pattern).
- The report-only parity CLI reproduces exactly these findings: four MISSING
  gates (omnimarket + omniclaude deploy-gate and reject-skip), with
  omnibase_core / omnibase_infra clean and the omnimarket occ-preflight gate
  correctly reported COVERED via its aggregator's `needs:` closure.
- **Merge-policy dimension:** a live `mergeQueue(branch:"dev")` probe found the
  decided "dev merge queues disabled everywhere" policy already true for seven of
  eight dev branches, but **surfaced one live QUEUE_DRIFT** — a repo whose `dev`
  branch still had a live merge queue against the decided `queue: disabled` policy.
  The `strict` decision (on for the two dashboards, recorded as-is elsewhere)
  matched live on every branch. This is the merge-policy dimension proving its
  value on first run: the config-as-data assertion caught a real divergence that
  the informal "we disabled them all" belief had missed. (Remediating it is a
  separate operator/admin branch-protection action; the ratchet does not mutate.)

## Supersedes

None.

## Superseded By

None.
