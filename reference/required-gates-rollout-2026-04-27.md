---
type: reference
status: stale
date: "2026-04-28"
title: "Required-Gates Rollout — April 2026 Snapshot"
topics: [ci-gates, branch-protection, receipt-gate, coderabbit, historical]
refs: []
---

# Required-Gates Rollout — April 2026 Snapshot

> **Source**: onex_change_control `docs/governance/2026-04-27-required-gates-rollout.md`.
> Migrated to the knowledge base 2026-08-25 as a dated point-in-time record, marked
> `status: stale` rather than corrected — this document is a snapshot of a specific rollout
> action, not a living policy page, and "updating" it would destroy its record value.
>
> **This snapshot is superseded.** Verified live against `onex_change_control`'s branch
> protection on its default branch (2026-08-25): required status checks have grown from the 3
> listed below for this repo to 23 contexts, spanning contract validation, corpus ratchets, a
> merge-hold gate, an append-only gate, and several AI-slop/pattern checks that did not exist
> at rollout time. Do not treat the per-repo table below as current policy for any repo — it
> documents one historical enrollment action.

**Goal:** Stop "Receipt-Gate + CodeRabbit Thread Check are advisory" by enrolling them as required status checks on the default branch across the OmniNode-ai organization's repos.

## Canonical context names (probe-verified, as of the original rollout)

The investigation source and the prompt that triggered this rollout both used slightly
aspirational context names. Live probes against each repo's check-runs API showed the actual
emitted contexts were:

| Gate | Actual context | Notes |
|---|---|---|
| Receipt Gate | `verify / verify` | Caller workflow `Receipt Gate` has job `verify:` that uses a reusable workflow whose job is also `verify`. That reusable workflow's own docstring claimed a more specific context name — that was wrong; the truly emitted context was `verify / verify`. |
| CodeRabbit Thread Check | `gate / CodeRabbit Thread Check` | Caller workflow has job `gate:` that uses a reusable workflow whose job is named `CodeRabbit Thread Check`. |

## Final state per repo (at rollout time)

| Repo | Receipt-Gate required? | CR-Thread required? | Why partial? |
|---|---|---|---|
| omniclaude | NO | YES | No Receipt-Gate workflow installed |
| omnibase_core | YES | YES | full coverage |
| omnibase_infra | YES | YES | full coverage |
| omnibase_spi | NO | YES | No Receipt-Gate workflow installed |
| omnidash | NO | NO | CR-thread workflow registered but never fired (zero runs); Receipt-Gate not installed |
| omniintelligence | NO | NO | same as omnidash |
| omnimemory | NO | YES | No Receipt-Gate workflow installed |
| omninode_infra | NO | NO | same as omnidash |
| omniweb | NO | NO | same as omnidash |
| onex_change_control | NO | YES (already) | No Receipt-Gate workflow installed; CR-thread already required pre-rollout |
| omnibase_compat | NO | YES | No Receipt-Gate workflow installed |

**Coverage at the time:** 7 of 11 repos required CR-Thread; 2 of 11 required Receipt-Gate. This
was framed as "as much enforcement as is currently safe" — requiring a context a repo's
workflow set never emits deadlocks every PR (GitHub waits for the check forever).

## Apply mechanism

Used the additive REST endpoint for `required_status_checks.contexts`, which appends without
mutating any other branch-protection field (`enforce_admins`, `required_linear_history`,
`required_pull_request_reviews`, `required_conversation_resolution`, `allow_force_pushes`,
`allow_deletions` all preserved). Verified on one repo first as a single-repo dry run, then
rolled out to the rest.

One transient API error on the first POST against `omnibase_core` (CodeRabbit-thread context).
Retried once; succeeded. All other PATCH operations succeeded on the first try.

## Follow-ups noted at the time (not resolved in this snapshot)

1. Land a Receipt-Gate workflow in the repos that lacked one, using `omnibase_infra`'s working
   template, then require `verify / verify` once each has it.
2. Diagnose the silently-broken CodeRabbit-thread gate on the repos where the workflow was
   registered but never fired — likely a `workflow_call` `secrets:` schema mismatch between
   caller and reusable workflow.
3. Add a recurring drift check — a CI gate that diffs the live `required_status_checks.contexts`
   against an expected canonical list per repo and fails if drift is detected.
4. Rename the generic `verify / verify` context to something less collision-prone with unrelated
   workflows, coordinating the branch-protection update in the same change to avoid a deadlock
   window.

## Hostile-review acknowledgements (retained for traceability)

Three medium-confidence observations from an adversarial review of the original rollout, and
how they were resolved at the time:

1. *"The generic context name is collision-prone"* — accepted as a follow-up (see #4 above). Not
   treated as a blocker for the rollout itself because branch protection requires the *exact*
   string, and the receipt-gate caller was the only workflow emitting that exact
   `<workflow-name> / <job-id>` pair in either repo at the time — verified via each repo's
   check-runs listing on a live PR.
2. *"Required-context coupling deadlocks PRs on a CI refactor"* — accepted, intentional. The
   point of this rollout was to make a CI refactor that silently drops a governance gate fail
   loudly. The drift-check follow-up (#3 above) was proposed as the durable mitigation: any
   future rename of the receipt-gate context should ship with a synchronous branch-protection
   update, not an out-of-band breakage.
3. *"Rolling out enforcement on some repos while others have silently broken workflows"* —
   partial agreement. The working repos benefited from enforcement immediately; the broken ones
   were tracked as a follow-up rather than blocking the whole rollout — waiting for every repo to
   have a working workflow before requiring any of them was judged the worse anti-pattern
   ("opt-in verification never gets adopted").
