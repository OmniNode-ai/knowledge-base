---
type: plan
status: active
date: "2026-04-01"
title: "Test-driven ticket-pipeline iteration loop"
topics: [pipelines, testing, automation, agents]
---

# Design: Test-Driven Ticket-Pipeline Iteration Loop

> **Priority**: P3
>
> Specifies how to add a test-run-fix iteration loop to ticket-pipeline that
> autonomously resolves test failures before PR creation, with support for both
> Python (pytest) and TypeScript (vitest/jest) test runners.

## 1. Insertion Point in Ticket-Pipeline Flow

### Current Pipeline Flow

From ticket-pipeline SKILL.md (v5.0.0), the phase chain is:

```
pre_flight (Phase 0)
  -> decision_context_load (Phase 0.5)
  -> conflict_gate (Phase 0.6)
  -> implement (Phase 1)
  -> local_review (Phase 2)
  -> create_pr (Phase 3)
  -> ci_watch (Phase 4)
  -> pr_review_loop (Phase 5)
  -> integration_verification_gate (Phase 6)
  -> auto_merge (Phase 7)
```

### Proposed Insertion: Phase 1.5 -- test_iterate

The test-driven iteration loop inserts as **Phase 1.5** between `implement` (Phase 1)
and `local_review` (Phase 2):

```
implement (Phase 1)
  -> TEST_ITERATE (Phase 1.5) <-- NEW
  -> local_review (Phase 2)
  -> create_pr (Phase 3)
  -> ...
```

### Why This Location

| Alternative | Reason Rejected |
|-------------|-----------------|
| Inside Phase 1 (implement) | Implementation agent (`ticket-work`) owns code generation. Mixing test iteration into it conflates responsibilities and bloats the implementation agent's context. |
| Inside Phase 2 (local_review) | local-review focuses on lint, type-check, and code quality -- not functional test failures. Adding test iteration would overload its scope. |
| After Phase 3 (create_pr) | Too late -- PR is already created with failing tests, generating noise for reviewers and CI. |
| Before Phase 1 (pre_flight) | Tests cannot run before code is written. |

Phase 1.5 is the natural seam: code exists on the branch (from Phase 1), but has not
yet been reviewed (Phase 2) or published (Phase 3). The test iteration loop ensures
all tests pass BEFORE local-review even begins, reducing local-review iterations and
preventing CI failures.

### State File Extension

The pipeline state.yaml gains a new phase entry:

```yaml
phases:
  implement:
    status: completed
    completed_at: "2026-03-29T10:05:00Z"
  test_iterate:                          # NEW
    status: in_progress
    started_at: "2026-03-29T10:05:01Z"
    iteration: 2
    max_iterations: 5
    test_runner: "pytest"                # pytest | vitest | jest
    last_failure_summary: "2 failed, 45 passed"
    failures:
      - file: "tests/unit/test_handler.py"
        test: "test_handler_validates_input"
        error_type: "AssertionError"
        message: "Expected 200, got 422"
  local_review:
    status: pending
```

### Auto-Advance Conditions

Phase 1.5 advances to Phase 2 (local_review) when:
- ALL tests pass (exit code 0), OR
- Max iterations reached AND bail-to-blocked triggered (see Section 3)

Phase 1.5 is SKIPPED entirely when:
- `--docs-only` flag is set (documentation changes have no tests)
- No test files exist in the repo (detected by globbing `tests/**/*.py` and `**/*.test.{ts,tsx,js,jsx}`)

---

## 2. Test Failure Parsing and Feedback

### Python: pytest

**Invocation**:
```bash
uv run pytest tests/ -x --timeout=120 --tb=short -q 2>&1
```

Flags:
- `-x`: Stop on first failure (focused iteration -- fix one thing at a time)
- `--timeout=120`: Per-test timeout to prevent hangs
- `--tb=short`: Concise tracebacks (context-efficient)
- `-q`: Quiet mode (reduce noise)

**Output Parsing Strategy**:

pytest output follows a predictable structure:

```
FAILED tests/unit/test_handler.py::test_validates_input - AssertionError: Expected 200, got 422
FAILED tests/unit/test_handler.py::test_missing_field - KeyError: 'name'
============= 2 failed, 45 passed in 3.42s ==============
```

Parse rules:
1. Capture lines matching `^FAILED (.+?)::(.+?) - (.+)$`
2. Extract: file path, test name, error type + message
3. Capture the summary line matching `(\d+) failed, (\d+) passed`

**Structured Failure Model**:

```yaml
test_result:
  runner: "pytest"
  exit_code: 1
  total: 47
  passed: 45
  failed: 2
  duration_seconds: 3.42
  failures:
    - file: "tests/unit/test_handler.py"
      test: "test_validates_input"
      error_type: "AssertionError"
      message: "Expected 200, got 422"
      traceback_snippet: "handler.py:42: assert response.status_code == 200"
    - file: "tests/unit/test_handler.py"
      test: "test_missing_field"
      error_type: "KeyError"
      message: "'name'"
      traceback_snippet: "handler.py:38: payload['name']"
```

### TypeScript: vitest

**Invocation**:
```bash
npx vitest run --reporter=json 2>/dev/null
```

The `--reporter=json` flag produces structured output directly:

```json
{
  "numTotalTests": 30,
  "numPassedTests": 28,
  "numFailedTests": 2,
  "testResults": [
    {
      "name": "src/components/Dashboard.test.tsx",
      "status": "failed",
      "assertionResults": [
        {
          "fullName": "Dashboard > renders metrics correctly",
          "status": "failed",
          "failureMessages": ["Expected: 42, Received: 0"]
        }
      ]
    }
  ]
}
```

Parse rules:
1. Read JSON output directly (no regex needed)
2. Filter `testResults` where `status == "failed"`
3. Extract `assertionResults` with `status == "failed"`

### TypeScript: jest

**Invocation**:
```bash
npx jest --json --outputFile=/tmp/jest-results.json 2>/dev/null
```

Jest's `--json` output is structurally identical to vitest's JSON reporter (vitest
adopted jest's format). Same parsing logic applies.

### Fallback: Unstructured Output

If JSON reporters are unavailable (old project, custom config), fall back to parsing
stdout:

```
vitest/jest stdout:
  FAIL src/components/Dashboard.test.tsx
    Dashboard
      x renders metrics correctly (5 ms)
        Expected: 42
        Received: 0

  Tests:  2 failed, 28 passed, 30 total
```

Parse rules:
1. Lines matching `^\s+FAIL (.+)$` for file paths
2. Lines matching `^\s+x (.+) \(\d+ ms\)$` for test names
3. Lines matching `^\s+(Expected|Received): (.+)$` for assertion details
4. Summary line matching `Tests:\s+(\d+) failed, (\d+) passed`

### Test Runner Auto-Detection

The pipeline detects the test runner from project configuration:

| Signal | Runner |
|--------|--------|
| `pyproject.toml` contains `[tool.pytest]` | pytest |
| `vitest.config.ts` or `vitest.config.js` exists | vitest |
| `jest.config.ts` or `jest.config.js` exists | jest |
| `package.json` contains `"test": "vitest"` | vitest |
| `package.json` contains `"test": "jest"` | jest |
| None of the above | Skip Phase 1.5 |

### Feedback Prompt to Implementation Agent

After parsing failures, the iteration loop constructs a focused fix prompt:

```
TEST ITERATION {n} of 5 -- {failed_count} test(s) failing

Fix the following test failures. Do NOT modify test files unless the test
expectations are provably wrong (i.e., the test asserts old behavior that your
implementation intentionally changed).

FAILURE 1:
  File: {file}
  Test: {test_name}
  Error: {error_type}: {message}
  Relevant code: {traceback_snippet}

FAILURE 2:
  ...

After fixing, run the test suite again to verify.
```

The key constraint: **do NOT modify tests unless the test expectations are wrong**.
This prevents the agent from "passing tests" by weakening assertions.

---

## 3. Max Iterations + Bail-to-Blocked Logic

### Iteration Budget

- **Max iterations**: 5
- **Per-iteration timeout**: 3 minutes (for the fix attempt, not the test run)
- **Total Phase 1.5 budget**: ~20 minutes (5 iterations x ~4 minutes each)

### Iteration State Machine

```
START
  |
  v
Run tests
  |
  +-- All pass --> ADVANCE to Phase 2
  |
  +-- Failures detected
        |
        v
      iteration < 5?
        |
        +-- Yes --> Feed failures to agent, agent fixes, re-run tests
        |
        +-- No --> BAIL (see below)
```

### Bail-to-Blocked Protocol

When max iterations are exhausted:

1. **Mark ticket as BLOCKED** in Linear via MCP:
   ```
   mcp__linear-server__save_issue(
     id=ticket_id,
     state="Blocked"
   )
   ```

2. **Post Linear comment** with failure summary:
   ```
   mcp__linear-server__save_comment(
     issueId=ticket_id,
     body="""
     ## Autonomous Test Fix Failed (5/5 iterations exhausted)

     **Test runner**: {runner}
     **Remaining failures**: {failed_count}

     ### Persistent Failures:
     {for each failure:}
     - `{file}::{test_name}` -- {error_type}: {message}

     ### Iteration History:
     - Iter 1: {failed_count} failures
     - Iter 2: {failed_count} failures (fixed: {fixed_names})
     - ...
     - Iter 5: {failed_count} failures

     ### Agent Notes:
     {agent's description of what it tried and why it could not resolve}

     **Action required**: Human review of persistent test failures.
     """
   )
   ```

3. **Write pipeline state** with `status: blocked_test_failures`:
   ```yaml
   test_iterate:
     status: blocked
     blocked_reason: "max_iterations_exhausted"
     iterations_used: 5
     persistent_failures:
       - file: "tests/unit/test_handler.py"
         test: "test_validates_input"
         error_type: "AssertionError"
   ```

4. **Pipeline behavior**: The pipeline STOPS at Phase 1.5. It does NOT advance to
   local_review or create_pr. The ticket remains on the branch with the partial
   implementation for human pickup.

### Regression Detection

If a previously-passing test starts failing during iteration (regression), the loop
immediately bails regardless of iteration count:

```
Iter 1: tests A, B fail (3 pass)
Iter 2: test A fixed, but test C now fails (was passing)
  --> BAIL: regression detected on test C
  --> Revert to pre-iteration-2 commit: git reset --hard HEAD~1
  --> Mark blocked with regression note
```

This prevents the agent from creating cascading breakage.

---

## 4. Parallel Flag: One Agent Per Ticket

### The `--parallel` Flag

When epic-team dispatches multiple tickets in a wave, each ticket gets its own
ticket-pipeline agent (this is already the case -- see epic-team SKILL.md "Direct
Dispatch Pattern"). The `--parallel` flag is an EPIC-LEVEL flag, not a ticket-pipeline
flag:

```bash
/epic-team <epic-id> --parallel
```

What `--parallel` changes at the test-iterate level:

| Behavior | Without `--parallel` | With `--parallel` |
|----------|---------------------|-------------------|
| Test execution | `pytest -x` (stop on first failure) | `pytest` (run all, report all) |
| Fix strategy | One failure at a time, sequential | All failures at once, batch fix |
| Iteration budget | 5 iterations, focused | 3 iterations, broad |
| Context usage | Lower (focused prompts) | Higher (all failures in one prompt) |

The rationale: in parallel mode, multiple agents run simultaneously and context is the
bottleneck. Broader but fewer iterations keep context usage manageable while allowing
the agent to fix correlated failures in one pass.

### Wave-Level Test Coordination

When multiple agents in a wave are running test-iterate on the same repo (e.g., two
tickets both modifying `omnibase_infra`), they operate on separate branches and cannot
interfere. However, both may discover the same pre-existing test failure. The pipeline
handles this by:

1. Recording pre-existing failures during `pre_flight` (Phase 0)
2. Excluding pre-existing failures from the iteration loop
3. Only iterating on failures introduced by the agent's changes

```
Pre-existing failures (from Phase 0): {test_X, test_Y}
Current failures: {test_X, test_Y, test_Z}
Iteration targets: {test_Z}  # Only new failures
```

---

## 5. Integration with Watchdog Stall Detection

### How Test-Iterate Interacts with the Dispatch Watchdog

The dispatch-watchdog skill and health monitor monitor agent
activity from the orchestrator level. Phase 1.5 (test_iterate) is a long-running phase
that may APPEAR stalled because:

- The agent is waiting for a long test suite to complete (2+ minutes of no tool calls)
- The agent is analyzing a complex failure before attempting a fix

To prevent false stall detection during test-iterate:

1. **Phase-aware stall thresholds**: The health monitor uses a longer stall threshold
   for `test_iterate` phase (15 minutes instead of 10 minutes), because test runs
   themselves take time.

2. **Activity heartbeat via state file**: The test-iterate loop updates the state file
   at each iteration boundary (before running tests, after parsing results), providing
   the health monitor with observable activity even during long test runs.

   ```yaml
   # Updated at each iteration boundary
   test_iterate:
     status: in_progress
     iteration: 3
     last_heartbeat: "2026-03-29T10:12:00Z"  # Updated before each test run
   ```

3. **Stall during test run vs. stall during fix**: If the health monitor detects a
   stall during test-iterate, it checks whether a test process is still running:
   ```bash
   pgrep -f "pytest|vitest|jest" > /dev/null
   ```
   If a test process is running, the stall is a false positive (test is just slow).
   If no test process is running, the agent has genuinely stalled.

### Watchdog Post-Hoc Verification for Test-Iterate

After test-iterate completes (either all-pass or bail-to-blocked), the dispatch-watchdog
verifies:

1. At least one commit exists on the branch (code was generated in Phase 1)
2. The state file reflects either `test_iterate.status: completed` or `test_iterate.status: blocked`
3. If `blocked`: a Linear comment exists on the ticket (bail protocol ran correctly)

If verification fails, the watchdog logs a friction event and retries the entire
Phase 1 + 1.5 sequence with a fresh agent.

---

## Flow Diagram: Complete Test-Iterate Phase

```
Phase 1 (implement) completes
  |
  v
Phase 1.5: test_iterate
  |
  v
Detect test runner (pyproject.toml / vitest.config / jest.config / package.json)
  |
  +-- No test runner found --> SKIP Phase 1.5, advance to Phase 2
  |
  +-- Runner detected
        |
        v
      Identify pre-existing failures (from Phase 0 pre_flight)
        |
        v
      Run test suite (iteration 1 of 5)
        |
        +-- All pass (excluding pre-existing) --> ADVANCE to Phase 2
        |
        +-- New failures detected
              |
              v
            Parse failures into structured model
              |
              v
            Feed failure summary to agent with fix prompt
              |
              v
            Agent attempts fix, commits changes
              |
              v
            Update state file heartbeat
              |
              v
            Run test suite (iteration N+1)
              |
              +-- All pass --> ADVANCE to Phase 2
              +-- Regression detected --> REVERT + BAIL
              +-- Failures remain, N < 5 --> Loop
              +-- Failures remain, N == 5 --> BAIL-TO-BLOCKED
```

---

## Prerequisites for Implementation

| Prerequisite | Status | Why Needed |
|-------------|--------|------------|
| ticket-pipeline v5.0.0 | EXISTS | Phase insertion point |
| dispatch-watchdog skill | PLANNED | Stall detection integration |
| Health monitor | DESIGN | Phase-aware thresholds |
| epic-team wave dispatch | EXISTS | `--parallel` flag context |
| pre_flight phase | EXISTS | Pre-existing failure baseline |
| Linear MCP tools | EXISTS | Bail-to-blocked Linear comment |

### Estimated Implementation Effort

| Component | Effort | Depends On |
|-----------|--------|------------|
| Test runner detection | 0.5 day | None |
| pytest output parser | 1 day | None |
| vitest/jest JSON parser | 0.5 day | None |
| Iteration loop + state management | 2 days | Parsers |
| Bail-to-blocked protocol | 1 day | Linear MCP |
| Regression detection + revert | 1 day | Iteration loop |
| Health monitor integration | 1 day | Health monitor |
| Integration testing | 2 days | All above |
| **Total** | **~9 days** | |
