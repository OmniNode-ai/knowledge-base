---
type: plan
status: active
date: "2026-04-07"
title: "Platform readiness gap closure plan"
topics: [verification, platform-readiness, observability]
---

# SOW Gap Closure Plan

**SOW**: ONEX Platform Readiness (2026-04-03)
**Current state**: 0/8 success criteria fully MET (5 PARTIAL, 3 NOT MET)
**Target**: All 8 criteria MET

---

## Diagnosis: Why Are 0/8 Criteria Met?

The SOW identified verification as the gap. Three months later, the verification
*infrastructure* exists but the *data flowing through it* does not. The structural
deficiency is a broken feedback loop:

1. **Cost events emit but never arrive.** The session-end hook emits
   `llm.cost.completed` to `onex.evt.omniintelligence.llm-call-completed.v1`. The
   omnidash consumer subscribes and projects to `llm_cost_aggregates`. But the table
   is empty -- meaning either: (a) the emit daemon is not connected to Kafka during
   sessions, (b) the omnidash consumer is not running, or (c) the topic does not
   exist on the bus. This is a wiring verification problem, not a code problem.

2. **Routing events emit but the dashboard shows zero.** Same pattern -- code exists
   end-to-end but no data flows. The `/llm-routing` page shows 0 decisions.

3. **Mock code was never removed.** `polymorphic-agent-integration.ts` has
   `simulateRoutingDecision()` with hardcoded confidence values. `chat-routes.ts`
   has fabricated stats ("94.2% routing accuracy", "$450/month"). These are demo
   artifacts from early development that were never cleaned up.

4. **golden_path does not exist as a contract field.** The SOW requires it in all
   382 contracts. But the field is not defined in the contract schema
   (`omnibase_core`). It cannot be populated until the schema supports it.

5. **Plugin is not auto-redeployed.** The plugin installs via `claude plugin install
   onex@omninode-tools` which reads from the git repo. After PRs merge to main,
   the plugin cache is stale until someone manually reinstalls. Every build cycle
   should include a plugin refresh.

6. **Golden chain sweep fails at runtime.** The 2026-04-05 run shows UUID format
   errors and missing columns. The sweep exists and is invocable but does not pass.

**Root cause**: We build infrastructure but never verify data flows end-to-end before
marking things done. The golden chain sweep is supposed to catch this, but it
itself is broken. The fix is to work from the bottom up: fix the data flow first,
then fix the sweep that verifies it, then run the sweep automatically.

---

## Task 1: Diagnose and fix cost event pipeline (omnidash)

**Repo**: omnidash, omniclaude
**SOW criteria**: 4 (cost trend serves real data)
**Effort**: Small

Verify why `llm_cost_aggregates` is empty despite session-end emitting cost events:

1. Check the topic exists on the bus: `rpk topic list | grep llm-call-completed`
2. Check omnidash consumer is running and subscribed to the topic
3. Check emit daemon health: read `plugins/onex/hooks/logs/emit-health/status-llmcostcompleted`
4. Produce a test event manually via `rpk topic produce` and verify it projects
5. If the topic does not exist, create it
6. If the consumer is not subscribed, fix the topic manifest
7. Run a Claude Code session, end it, verify a row appears in `llm_cost_aggregates`

**Done when**: `/api/costs/summary` returns non-zero token counts after a real session.

---

## Task 2: Diagnose and fix routing decision pipeline (omnidash)

**Repo**: omnidash, omnibase_infra
**SOW criteria**: 5 (routing decisions visible)
**Effort**: Small

Same diagnostic pattern as Task 1 but for routing events:

1. Verify `onex.evt.omniclaude.llm-routing-decision.v1` topic exists
2. Verify omnidash consumer processes it into `llm_routing_decisions` table
3. Trace the emit path from omniclaude's UserPromptSubmit hook
4. Produce a test event and verify projection
5. Run a real session with routing enabled and verify a row appears

**Done when**: `/llm-routing` dashboard shows at least 1 real routing decision.

---

## Task 3: Remove mock code from omnidash server (omnidash)

**Repo**: omnidash
**SOW criteria**: 3 (zero hardcoded/mock values)
**Effort**: Medium

Remove or guard all mock/hardcoded data in production server code:

1. **`polymorphic-agent-integration.ts`**: Delete `simulateRoutingDecision()` and
   all hardcoded confidence values (0.87, 0.92, etc.). If the file has no real
   callers, delete the entire file.
2. **`chat-routes.ts`**: Remove the hardcoded demo conversation with fabricated
   stats. Replace with empty chat history or a message indicating no data.
3. **`registry-mock-data.ts`**: Remove or gate behind `DEMO_MODE=true` only.
   Verify no production code path imports it without the gate.
4. **`registry-routes.ts`**: Remove `mockDataStore` fallback paths. Return empty
   arrays when no real data exists.

**Done when**: `grep -r "simulateRouting\|94\.2%\|0\.87\|mockDataStore" omnidash/server/`
returns zero hits (excluding test files and DEMO_MODE-gated paths).

---

## Task 4: Add golden_path field to contract schema (omnibase_core)

**Repo**: omnibase_core
**SOW criteria**: 1 (contracts have golden_path + dod_evidence)
**Effort**: Medium

The `golden_path` field is referenced by the SOW but does not exist in the contract
schema. Add it:

1. Add `golden_path: list[str] | None = None` to the contract model in omnibase_core
   (find the base contract Pydantic model, add the optional field)
2. Add `dod_evidence: list[dict] | None = None` if not already present
3. Update the contract skeleton generator to include these fields in new contracts
4. Update the contract linter to warn when `golden_path` is empty on seam contracts
5. Backfill the 7 seam contracts referenced in the SOW with their golden_path values

**Done when**: `grep -rl golden_path omnibase_core/src/` returns the model file, and
at least 7 seam contracts have the field populated.

---

## Task 5: Backfill golden_path on seam contracts (multi-repo)

**Repo**: omniclaude, omnibase_infra, omnidash, omniintelligence
**SOW criteria**: 1 (contracts have golden_path)
**Effort**: Medium
**Depends on**: Task 4

After the schema supports `golden_path`, populate it on the critical seam contracts
that verification skills check. Focus on the 5 golden chain topics:

1. `registration` chain: find the contract for routing-decision emission, add
   golden_path pointing to `llm_routing_decisions` table
2. `pattern_learning` chain: contract for pattern-stored emission
3. `delegation` chain: contract for task-delegated emission
4. `routing` chain: contract for llm-routing-decision emission
5. `evaluation` chain: contract for run-evaluated emission
6. `llm_cost` chain: contract for llm-call-completed emission

Each golden_path entry should specify: source topic, projection table, key fields,
and the golden chain test file in omnidash.

**Done when**: At least 7 seam contracts have `golden_path` populated with real values.

---

## Task 6: Fix golden chain sweep runtime errors (omnidash)

**Repo**: omnidash
**SOW criteria**: 2 (verification skills produce structured results), 7 (nightly sweep)
**Effort**: Small

The 2026-04-05 golden chain sweep run failed with UUID format issues and missing
columns. Fix the test infrastructure:

1. Read the sweep results at `.onex_state/golden-chain-sweep/2026-04-05/`
2. Identify the specific UUID format and missing column errors
3. Fix the golden chain test payloads to match current schema
4. Run the golden chain tests: `npx vitest run server/__tests__/golden-chain/`
5. Fix any schema drift between test expectations and actual table definitions
6. Add the `llm_cost` chain (already has a golden test file) to the sweep if missing

**Done when**: `npx vitest run server/__tests__/golden-chain/` passes all chains,
and `/golden_chain_sweep` skill produces `overall_status: "pass"`.

---

## Task 7: Add plugin refresh to build loop cycle (omniclaude)

**Repo**: omniclaude
**SOW criteria**: 7 (nightly sweep without manual intervention)
**Effort**: Small

The plugin cache becomes stale after PRs merge. The build loop and cron cycle
should refresh the plugin automatically:

1. Add a plugin refresh step to the build loop's VERIFYING phase or the
   cron-closeout script: `claude plugin install onex@omninode-tools`
2. Add a post-release hook in the redeploy skill that refreshes the plugin
3. Verify the refresh is idempotent (no-op if already current)

**Done when**: After a PR merges to omniclaude main, the next build loop cycle
picks up the new plugin code without manual intervention.

---

## Task 8: Wire savings pipeline end-to-end (omnibase_infra, omnidash)

**Repo**: omnibase_infra, omnidash
**SOW criteria**: 4 (cost trend serves real data from savings_estimates)
**Effort**: Medium

The SOW specifically calls out `savings_estimates` table. The `SavingsProjection`
in omnidash queries it but the table is empty:

1. Identify where savings events should be produced (omnibase_infra baselines
   computation or delegation cost tracking)
2. Verify the Kafka topic for savings events exists
3. Verify the omnidash consumer projects savings events to `savings_estimates`
4. If the producer does not exist, build it -- emit a savings event when the
   delegation router selects a cheaper model
5. Verify `/api/costs/savings/summary` returns non-zero data

**Done when**: The savings pipeline has at least one event flowing end-to-end.

---

## Task 9: Wire routing visibility with enriched schema (omnibase_infra, omnidash)

**Repo**: omnibase_infra, omnidash
**SOW criteria**: 5 (routing decisions captured with provider, model, reason)
**Effort**: Medium

The SOW requires routing decision events with enriched schema fields:
`provider, model, reason, selection_mode, fallback_indicator`. Current routing
events may lack these fields:

1. Check the routing decision event schema in omnibase_infra
2. Add missing fields (provider, model, selection_mode, fallback_indicator) if absent
3. Verify the omnidash projection maps all enriched fields to `llm_routing_decisions`
4. Verify the `/api/infra-routing/decisions` endpoint returns the enriched fields

**Done when**: A routing decision event with all enriched fields projects correctly
and is visible on the dashboard.

---

## Task 10: Run and fix platform readiness gate (omniclaude)

**Repo**: omniclaude
**SOW criteria**: 6 (readiness gate produces 7D report), 8 (all dimensions PASS/WARN)
**Effort**: Small
**Depends on**: Tasks 1-9

Run `/platform_readiness` and fix any issues that prevent it from producing a
complete 7-dimension report:

1. Invoke `/onex:platform_readiness`
2. Capture the output to `.onex_state/platform-readiness/2026-04-07/`
3. For each FAIL dimension, verify whether the underlying fix (from Tasks 1-9)
   has resolved it
4. If the skill itself has bugs preventing report generation, fix them
5. Re-run until all 7 dimensions produce PASS or WARN

**Done when**: Platform readiness report exists with 7 dimensions, none showing FAIL.

---

## Task 11: Schedule nightly verification cycle (omniclaude)

**Repo**: omniclaude
**SOW criteria**: 7 (nightly sweep without manual intervention)
**Effort**: Small
**Depends on**: Tasks 6, 7, 10

Wire the nightly cron to run the full verification cycle:

1. Verify `cron-closeout.sh` or the autopilot skill includes:
   - `/onex:golden_chain_sweep`
   - `/onex:data_flow_sweep`
   - `/onex:platform_readiness`
2. If any are missing, add them to the nightly cycle
3. Add plugin refresh (Task 7) as the first step
4. Run one full cycle unattended and verify all skills produce structured output
5. Verify results are persisted to `.onex_state/`

**Done when**: A full nightly cycle runs autonomously and produces passing results
for golden_chain_sweep, data_flow_sweep, and platform_readiness.

---

## Task 12: SOW verification evidence collection

**Repo**: omni_home
**SOW criteria**: All 8
**Effort**: Small
**Depends on**: All previous tasks

Re-run the SOW verification against all 8 criteria with evidence:

1. For each criterion, collect the specific evidence proving it is MET
2. Write the verification report to `.onex_state/sow-verification-final.md`
3. Include: command output, screenshots, DB query results, sweep reports
4. For criterion 3 (no mock code): run the grep and show zero results
5. For criterion 4 (cost data): query `/api/costs/summary` and show real data
6. For criterion 7 (nightly sweep): point to the autonomous run artifacts

**Done when**: All 8 criteria show MET with evidence artifacts.

---

## Execution Order

```
Phase A (parallel, no dependencies):
  Task 1: Fix cost event pipeline
  Task 2: Fix routing decision pipeline
  Task 3: Remove mock code
  Task 4: Add golden_path to contract schema

Phase B (after Phase A):
  Task 5: Backfill golden_path on seam contracts (needs Task 4)
  Task 6: Fix golden chain sweep (needs Tasks 1, 2 for data)
  Task 7: Add plugin refresh to build loop
  Task 8: Wire savings pipeline
  Task 9: Wire routing enriched schema

Phase C (after Phase B):
  Task 10: Run platform readiness gate
  Task 11: Schedule nightly verification cycle
  Task 12: Final SOW verification
```

## Process Deficiency Analysis

The user asked: "What is the deficiency in our process?"

**The core deficiency is: we ship infrastructure without verifying data flows.**

Every SOW gap follows the same pattern:
- Code exists and is correct
- Tests pass (unit tests mock the dependencies)
- PR merges
- But zero real events flow through the pipeline
- Dashboard shows empty/zero instead of real data
- Nobody notices because there is no automated end-to-end check

**What needs to change:**

1. **Golden event tests on every merge touching pipelines** -- the golden chain
   tests exist in omnidash but are not in CI. They should run on every PR that
   touches projection code, consumer code, or event schemas.

2. **Plugin auto-refresh every cycle** -- the plugin cache goes stale after merges.
   The build loop should refresh it automatically. This is a 1-line addition to
   the cron script.

3. **Data flow sweep in the build loop's VERIFYING phase** -- the build loop has
   a VERIFYING phase but it currently checks dashboard health (pages render) not
   data flow (events arrive). Add `/data_flow_sweep` to the VERIFYING phase.

4. **"Empty is not passing"** -- the current health checks pass when endpoints
   return `[]` or `{count: 0}`. The readiness gate needs to distinguish between
   "honestly empty because nothing has happened" vs "empty because the pipeline
   is broken." The platform_readiness skill should flag `llm_cost_aggregates`
   having zero rows after 24+ hours of sessions as a FAIL, not a PASS.
