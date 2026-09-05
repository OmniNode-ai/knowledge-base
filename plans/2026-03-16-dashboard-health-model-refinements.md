---
type: plan
status: active
date: "2026-03-16"
title: "Dashboard health model refinements — not_applicable status and probe semantics"
topics: [dashboard, health-model, probes, observability]
---

# Omnidash Health Model Refinements — not_applicable status, envSync threshold, topicParity semantics

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Close three gaps left from the health-model epic: add `not_applicable` as a distinct health status for intentionally disabled features, relax the envSync staleness threshold from 1h to 24h for local dev, and update the topicParity probe to use subscription-parity semantics instead of contract-completeness semantics.

**Architecture:** All changes are in the omnidash repo. Server-side adds `not_applicable` to the `DataSourceStatus` union and updates two probes (envSync, topicParity). Client-side adds rendering for the new status. Existing `expected_idle_local` semantics are unchanged — `not_applicable` is a separate concept for features that are intentionally off, not merely idle.

**Tech Stack:** TypeScript (Express server + React client), Vitest

---

## Context

That epic delivered a five-state health model (`live`, `mock`, `error`, `offline`, `expected_idle_local`) but the plan originally specified a six-state model that also included `not_applicable`. Three specific gaps remain:

1. **`not_applicable` not implemented** — envSync with the secrets manager disabled currently returns `mock` → reclassified to `expected_idle_local`. It should be `not_applicable` (feature is off, not idle).
2. **envSync staleness threshold unchanged** — still 1 hour. Local dev sessions are long-running; 24 hours is more appropriate.
3. **topicParity probe semantics** — still checks contract-completeness (EXPECTED_TOPICS vs READ_MODEL_TOPICS vs subscribed). Should check subscription parity only: are we subscribed to everything in READ_MODEL_TOPICS? Contract gaps are metadata, not health degradation.

**Existing code verified:**
- `omnidash/server/health-data-sources-routes.ts` (739 lines) — `DataSourceStatus` at line 68, `ENV_SYNC_STALE_SECS` at line 94, `probeEnvSync()` at line 478, `probeTopicParity()` at line 522, `LOCAL_IDLE_EXPECTED` at line 115
- `omnidash/client/src/components/DataSourceHealthPanel.tsx` (319 lines) — `DataSourceStatus` at line 19, `StatusIcon` at line 96, `StatusBadge` at line 113, `SummaryBar` at line 188
- `omnidash/server/__tests__/health-data-sources-routes.test.ts` (505 lines) — 12 tests covering probes, caching, summary counts

---

## Task 1: Add `not_applicable` status to server-side type and summary

**Repo:** omnidash
**Files:**
- Modify: `omnidash/server/health-data-sources-routes.ts` (lines 68, 78-88, 688-700)

**Description:**

Add `not_applicable` to the `DataSourceStatus` type union and to the summary counter initialization.

**Changes:**

1. Line 68 — add to union:
```typescript
export type DataSourceStatus = 'live' | 'mock' | 'error' | 'offline' | 'expected_idle_local' | 'not_applicable';
```

2. Lines 78-88 — add to summary interface:
```typescript
summary: {
  live: number;
  mock: number;
  error: number;
  offline: number;
  expected_idle_local: number;
  not_applicable: number;
};
```

3. Lines 688-700 — add to counter reduce initial value:
```typescript
{ live: 0, mock: 0, error: 0, offline: 0, expected_idle_local: 0, not_applicable: 0 }
```

**Acceptance Criteria:**
- `DataSourceStatus` includes exactly 6 values: `live`, `mock`, `error`, `offline`, `expected_idle_local`, `not_applicable`
- Summary object has a `not_applicable` counter
- TypeScript compiles without errors (`npm run check`)

---

## Task 2: Update envSync probe to return `not_applicable` when the secrets manager is disabled and relax staleness threshold

**Repo:** omnidash
**Files:**
- Modify: `omnidash/server/health-data-sources-routes.ts` (lines 94, 478-510, 115-123)

**Description:**

Two changes to the envSync probe:

**2a. Return `not_applicable` instead of `mock` when the secrets manager is off:**

Replace line 482:
```typescript
// Before:
return { status: 'mock', reason: 'secrets_manager_disabled' };
// After:
return { status: 'not_applicable', reason: 'secrets_manager_disabled' };
```

**2b. Relax staleness threshold from 1h to 24h:**

Replace line 94:
```typescript
// Before:
const ENV_SYNC_STALE_SECS = 3600; // 1 hour (2× the 5-min throttle window)
// After:
const ENV_SYNC_STALE_SECS = 86400; // 24 hours — local dev sessions are long-running
```

**2c. Remove `envSync` from `LOCAL_IDLE_EXPECTED`:**

Since envSync now returns `not_applicable` directly (not `mock`), the reclassification in `LOCAL_IDLE_EXPECTED` is no longer needed for the secrets-manager-disabled case. Remove `'envSync'` from the set at line 115-123. When the secrets manager IS active but sync is stale, the probe already returns `offline` which is the correct status (it's a real problem, not an expected idle).

**Acceptance Criteria:**
- `probeEnvSync()` returns `{ status: 'not_applicable', reason: 'secrets_manager_disabled' }` when `SECRETS_MANAGER_ADDR` is empty
- `probeEnvSync()` returns `offline` with `sync_stale` reason only after 24 hours (not 1 hour)
- `envSync` is NOT in `LOCAL_IDLE_EXPECTED` set
- When the secrets manager IS active and sync ran within 24h, returns `live`

---

## Task 3: Update topicParity probe to use subscription-parity semantics

**Repo:** omnidash
**Files:**
- Modify: `omnidash/server/health-data-sources-routes.ts` (lines 512-565)

**Description:**

Change the topicParity probe to answer the question "are we subscribed to everything in READ_MODEL_TOPICS?" instead of "does every topic list agree perfectly?"

The current probe checks three-way parity between READ_MODEL_TOPICS, EXPECTED_TOPICS, and actual subscriptions. Contract completeness (EXPECTED_TOPICS matching READ_MODEL_TOPICS) is a deployment metric, not a health signal.

**New logic:**

```typescript
function probeTopicParity(): DataSourceInfo & { metadata?: { unsubscribed?: string[]; contractGaps?: string[] } } {
  try {
    const readModelSet = new Set(READ_MODEL_TOPICS as readonly string[]);
    const stats = readModelConsumer.getStats();

    // Primary check: subscription parity — are we subscribed to everything in READ_MODEL_TOPICS?
    if (!stats.isRunning) {
      return { status: 'offline', reason: 'consumer_not_running' };
    }

    const subscribedSet = new Set(Object.keys(stats.topicStats));
    const unsubscribed: string[] = [];
    for (const topic of READ_MODEL_TOPICS) {
      if (!subscribedSet.has(topic)) {
        unsubscribed.push(topic);
      }
    }

    // Informational: contract gaps (EXPECTED_TOPICS not in READ_MODEL_TOPICS)
    // Reported as metadata, NOT as health degradation
    const expectedSet = new Set(EXPECTED_TOPICS as readonly string[]);
    const contractGaps = [...expectedSet].filter((t) => !readModelSet.has(t));

    if (unsubscribed.length > 0) {
      return {
        status: 'offline',
        reason: `subscription_gap: ${unsubscribed.length} topics in READ_MODEL_TOPICS not subscribed`,
        metadata: { unsubscribed, contractGaps: contractGaps.length > 0 ? contractGaps : undefined },
      };
    }

    return {
      status: 'live',
      lastEvent: new Date().toISOString(),
      ...(contractGaps.length > 0 ? { metadata: { contractGaps } } : {}),
    };
  } catch {
    return { status: 'error', reason: 'probe_threw' };
  }
}
```

**Key semantic change:** When subscription parity is satisfied (all READ_MODEL_TOPICS are subscribed), return `live` regardless of contract gaps. Contract gaps are informational metadata, not health degradation.

**Also remove `topicParity` from `LOCAL_IDLE_EXPECTED`** at lines 115-123. The probe now has proper semantics — `live` when subscriptions match, `offline` when they don't. The idle reclassification was masking real subscription failures.

**Acceptance Criteria:**
- topicParity returns `live` when all READ_MODEL_TOPICS are subscribed, even if EXPECTED_TOPICS has extras
- topicParity returns `offline` with `subscription_gap` reason when READ_MODEL_TOPICS has unsubscribed topics
- topicParity returns `offline` with `consumer_not_running` when consumer is not running
- Contract gaps reported as `metadata` field, not as health degradation
- `topicParity` is NOT in `LOCAL_IDLE_EXPECTED` set

---

## Task 4: Add `not_applicable` rendering to client-side health panel

**Repo:** omnidash
**Files:**
- Modify: `omnidash/client/src/components/DataSourceHealthPanel.tsx` (lines 19, 29-36, 96-111, 113-150, 188-235)

**Description:**

Add `not_applicable` to the client-side type and render it distinctly (gray, hidden from casual view — not an error, not counted as unhealthy).

**4a. Update type (line 19):**
```typescript
export type DataSourceStatus = 'live' | 'mock' | 'error' | 'offline' | 'expected_idle_local' | 'not_applicable';
```

**4b. Update summary interface (lines 29-36):**
```typescript
summary: {
  live: number;
  mock: number;
  error: number;
  offline: number;
  expected_idle_local: number;
  not_applicable: number;
};
```

**4c. Add StatusIcon case (after line 107):**
```typescript
case 'not_applicable':
  return <MinusCircle className="w-4 h-4 text-gray-500/50" />;
```

**4d. Add StatusBadge case (after line 148):**
```typescript
case 'not_applicable':
  return (
    <Badge className="bg-gray-500/10 text-gray-500 border-gray-500/20 text-[10px]">
      N/A
    </Badge>
  );
```

**4e. Add SummaryBar counter (after line 231):**
```typescript
{summary.not_applicable > 0 && (
  <span className="flex items-center gap-1.5 text-gray-500">
    <MinusCircle className="w-3.5 h-3.5" />
    {summary.not_applicable} n/a
  </span>
)}
```

**4f. Add reason label:**
Add to REASON_LABELS:
```typescript
secrets_manager_disabled: 'Secrets manager not configured (opt-out)',
```
Update the existing `secrets_manager_disabled` entry if it already exists with a clearer label.

**Acceptance Criteria:**
- `not_applicable` renders as a dim gray "N/A" badge (visually distinct from error/offline/idle)
- Summary bar shows "N n/a" count when `not_applicable > 0`
- `not_applicable` sources are not counted in offline, error, or mock totals
- TypeScript compiles without errors

---

## Task 5: Update tests for new health model semantics

**Repo:** omnidash
**Files:**
- Modify: `omnidash/server/__tests__/health-data-sources-routes.test.ts`

**Description:**

Update existing tests and add new ones for the changed semantics.

**5a. Update summary count test (line 350-384):**
The total should still be 15, but `not_applicable` should be included in the count.

**5b. Add test: envSync returns `not_applicable` when SECRETS_MANAGER_ADDR is empty:**
```typescript
it('reports envSync as not_applicable when SECRETS_MANAGER_ADDR is empty', async () => {
  // Clear SECRETS_MANAGER_ADDR to simulate opt-out
  const original = process.env.SECRETS_MANAGER_ADDR;
  delete process.env.SECRETS_MANAGER_ADDR;

  vi.mocked(projectionService.getView).mockReturnValue(null);
  setupEmptyDb();

  const app = makeApp();
  const res = await request(app).get('/api/health/data-sources');

  expect(res.body.dataSources.envSync.status).toBe('not_applicable');
  expect(res.body.dataSources.envSync.reason).toBe('secrets_manager_disabled');

  // Restore
  if (original !== undefined) process.env.SECRETS_MANAGER_ADDR = original;
});
```

**5c. Add test: topicParity returns `live` when subscription parity satisfied:**
Verify that when all READ_MODEL_TOPICS are subscribed, topicParity is `live` even if EXPECTED_TOPICS has additional topics.

**5d. Add test: topicParity returns `offline` when consumer not running:**
Mock `readModelConsumer.getStats()` to return `isRunning: false`.

**5e. Verify total summary includes `not_applicable`:**
Update the summary total assertion to include `summary.not_applicable`.

**Acceptance Criteria:**
- All existing tests pass
- New envSync `not_applicable` test passes
- New topicParity subscription-parity test passes
- New topicParity consumer-not-running test passes
- Summary count test accounts for `not_applicable`
- `npm run test` exits 0

---

## Dependency Order

```
Task 1 (add not_applicable to types)
  → Task 2 (envSync probe changes) — needs Task 1 for the type
  → Task 3 (topicParity probe changes) — needs Task 1 for the type
  → Task 4 (client rendering) — needs Task 1 for the type
    → Task 5 (tests) — needs Tasks 1-4 to be in place
```

**Critical path:** 1 → 2 + 3 + 4 (parallel) → 5

---

## Exit Criteria

1. `DataSourceStatus` has exactly 6 values including `not_applicable`
2. envSync returns `not_applicable` when `SECRETS_MANAGER_ADDR` is empty (not `mock` or `expected_idle_local`)
3. envSync staleness threshold is 24 hours (not 1 hour)
4. topicParity returns `live` when all READ_MODEL_TOPICS are subscribed
5. topicParity reports contract gaps as metadata, not health degradation
6. Client renders `not_applicable` as dim gray "N/A" badge
7. `npm run check` and `npm run test` both pass
8. `envSync` and `topicParity` are NOT in `LOCAL_IDLE_EXPECTED` set

routing: ticket-pipeline (single repo: omnidash, sequential, no external deps)
