---
type: adr
status: accepted
date: "2026-06-24"
title: "ADR-0029: Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core)"
adr_id: ADR-0029
topics: [omnibase_core, ci, branch-protection, validator-enforcement]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0029: Model B — Failing-Rollup Validator Enforcement (pilot: omnibase_core)

**Source:** omnibase_core `docs/decisions/adr-2026-06-24-model-b-failing-rollup-enforcement.md`
**Status:** Implemented (pilot) · **Created:** 2026-06-24

## Context

`architecture-handshakes/validator-requirements.yaml` is the single source of
truth for which validators every repo must wire. Its consumer
(`validator_requirements_consumer.py`) proves each spec-required validator is
**present** — a matching pre-commit hook id, and a matching keyword somewhere in
`.github/workflows/*.yml`. Each repo also carries
`required_check_on_main` strings naming a granular branch-protection context per
validator (e.g. `"Quality Gate / ruff"`, `"AI Slop / check"`).

The 2026-06-24 enforcement-deficiency audit found two structural gaps:

1. **The granular `required_check_on_main` contexts do not exist in live branch
   protection.** omnibase_core's `dev` branch requires four aggregate rollup
   contexts: `CI Summary`, `verify / verify`, `gate / CodeRabbit Thread Check`,
   `call-reject-skip-token / scan / reject-skip-gate-token`. The per-validator
   contexts the spec named were never registered. The consumer never reads
   `required_check_on_main` at all, so this drift was invisible.

2. **"Present" is not "gating".** A repo can be handshake-clean while the single
   required rollup never actually depends on the job that runs a validator:
   - `naming-conventions` and `aislop-patterns` ran only in
     `omni-standards-compliance.yml`, which has no aggregator job and is not in
     branch protection — a real violation could not turn `CI Summary` red.
   - `pydantic-patterns` had no real CI job at all; the consumer's `pydantic`
     keyword matched incidental `pip install pydantic` lines in unrelated
     workflows.
   - `version-pin-check` was listed in `quality-gate.needs` but carried
     `continue-on-error: true`, so its failure could never propagate.

## Decision

Adopt **Model B**: keep **one** required aggregate rollup context per repo
(`CI Summary` for omnibase_core), but make that rollup **airtight** so it goes
red if any spec-required validator sub-job fails. Explicitly reject Model A
(registering granular per-validator contexts in branch protection): it inflates
the branch-protection surface that must be mutated through the gated path, and
the aggregate rollup is already a required check.

Three mechanisms enforce airtightness:

1. **The rollup transitively covers every spec-required validator.** Every
   spec-required validator that applies to omnibase_core runs as a job in
   `ci.yml` (the workflow that emits `CI Summary`) and feeds
   `quality-gate → ci-summary`. New jobs added: `naming-conventions`,
   `pydantic-patterns`, `aislop-patterns`. `version-pin-check` was removed from
   `quality-gate.needs` because `continue-on-error: true` means it can never
   gate.
2. **A meta-check prevents silent drop.** `validator_rollup_coverage.py` parses
   the rollup workflow's `needs` graph and asserts the rollup job transitively
   depends on a real, non-`continue-on-error` job for every opted-in
   spec-required validator. Wired as a pre-commit hook
   (`validate-rollup-coverage`) and a `check-handshake.yml` CI step.
   `tests/validation/test_validator_rollup_coverage.py` exercises the logic,
   including planted-failure cases.
3. **Per-repo opt-in keeps the fleet safe.** A new additive top-level spec block
   `model_b_rollup_enforcement.repos` lists only the pilot (omnibase_core). The
   legacy consumer reads only `required_validators` + `known_repos` and ignores
   the new block, so the other repos' `validate-validator-requirements`
   handshake is byte-for-byte unchanged.

## Why Model B over Model A

- **Lower branch-protection surface.** One required rollup is far less to manage and audit than ~18 granular contexts per repo.
- **The rollup is already required.** `CI Summary` already gates merge; the only defect was that it did not depend on every validator. Fixing the `needs` graph is strictly additive.
- **The meta-check closes the silent-drop hole** that made Model A's per-context registration attractive: a validator cannot be quietly removed from the rollup without a deterministic test going red.

## Consequences

- A real `naming-conventions`, `pydantic-patterns`, or `aislop-patterns` violation now turns `CI Summary` red on omnibase_core.
- `validator_rollup_coverage.py` must stay in sync with the spec's `validator_jobs` map.
- Grandfathered baseline gaps (e.g. `spdx-headers`, `stub-implementations`) are intentionally not asserted by the rollup verifier yet — they remain `MISSING_CI_WORKFLOW` and graduate into `validator_jobs` as their wiring lands.
- Fleet rollout to the other repos is a separate, later effort, each with its own rollup mapping.

## Verification (2026-08-20, at migration)

`src/omnibase_core/validation/validator_rollup_coverage.py` exists on
`omnibase_core@dev`, consistent with the mechanism this ADR describes. This
migration does not re-run the fleet-rollout status claim (pilot-scoped as of
authoring); treat "fleet rollout" language above as historical intent, not a
live-verified current state.
