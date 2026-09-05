---
type: plan
status: active
date: "2026-02-28"
title: "Insights-driven workflow improvements"
topics: [workflow, skills, developer-experience, epics]
---

# Insights-Driven Workflow Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Implement the top four workflow improvements surfaced by the /insights report to reduce wrong-approach friction, enable epic checkpoint/resume, add uv lock advisory warnings, and codify epic failure recovery strategies

**Architecture:** Four independent deliverables across two surfaces: (1) documentation edits to `omniclaude/CLAUDE.md` and skill SKILL.md files, and (2) a Python change to `bash_guard.py` with TDD. Each deliverable is self-contained and can be committed independently. All changes target the `omniclaude` repo and belong in a worktree before committing.

**Tech Stack:** Python 3.12, pytest, uv, bash, markdown (SKILL.md)

---

## Context

All changes go to the `omniclaude` repo. Work in a worktree:

```bash
TICKET="insights-workflow"
git -C "$WORKSPACE_ROOT/omniclaude" worktree add \
  "$WORKTREES_ROOT/$TICKET/omniclaude" \
  -b <author>/insights-workflow-improvements
cd "$WORKTREES_ROOT/$TICKET/omniclaude"
uv sync --group dev
```

### Why each task

| Task | Root cause from insights | Pain instances |
|------|--------------------------|----------------|
| 1. Anti-patterns in CLAUDE.md | `wrong_approach` friction | 75 instances |
| 2. `resume-epic` skill | Rate limit / context limit mid-epic | 6+ sessions wasted |
| 3. uv lock advisory in bash_guard.py | CI version mismatch (uv 0.5.14 vs 0.8.3) | Multiple cascading CI failures |
| 4. Epic-team failure taxonomy | Sub-agents stall without recovery | Recurring stale tasks |

---

## Task 1: Add Common Anti-Patterns section to omniclaude/CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (insert after `## Workflow Principles`)

**Step 1: Add the anti-patterns section**

Open `CLAUDE.md` and insert this new section immediately after the `## Workflow Principles` heading block (after the `### Headless Mode` subsection ends, before `### Fail-Fast Design`):

```markdown
### Common Anti-Patterns (DO NOT DO THESE)

These are recurring wrong-approach mistakes surfaced from session analysis. Before implementing, check this list.

| Anti-Pattern | Correct Approach |
|--------------|-----------------|
| Treating skills and nodes as orthogonal concepts | Skills ARE thin markdown files that trigger event emission in the node architecture. They are NOT separate from nodes. |
| Reimplementing CI merge branches | Use GitHub Merge Queue (`gh pr merge --auto`). Never re-implement CI merge coordination. |
| plan-to-tickets: analyzing format compatibility first | Execute ticket creation immediately from the plan file. Never analyze format mismatches first. |
| Making `consumer.run()` block the Kafka event loop | Kafka consumers must not block the event loop. Use async patterns or background threads. |
| Removing branch protection rules after adding them | Never remove branch protection rules. If temporary rules were added, flag them to the user. |
| Routing a ticket to a repo based on title alone | Always verify the target repo from the Linear ticket metadata (`repo` field in TicketContract) before starting work. |
| Iterating plans more than 2 self-review passes | After 2 review cycles, present the plan to the user. Do not continue internally iterating. |
```

**Step 2: Verify the section was inserted correctly**

Read the modified `CLAUDE.md` and confirm the section appears between `### Headless Mode` and `### Fail-Fast Design` with correct markdown table formatting.

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add common anti-patterns section to CLAUDE.md [insights]"
```

---

## Task 2: Create `resume-epic` skill

**Files:**
- Create: `plugins/onex/skills/resume-epic/SKILL.md`

This skill checks Linear ticket status for an epic and re-dispatches only the incomplete tickets sequentially (not in parallel) to avoid rate limits.

**Step 1: Write the skill file**

Create `plugins/onex/skills/resume-epic/SKILL.md`:

```markdown
---
name: resume-epic
description: Resume an interrupted epic-team run — checks Linear ticket status per epic and re-dispatches only incomplete (non-Done, non-In Review) tickets sequentially to avoid rate limits
version: 1.0.0
category: workflow
tags: [epic, resume, checkpoint, linear, rate-limit-recovery]
args:
  - epic_id (required): tracker epic ID (e.g., `ABC-2000`)
  - --dry-run: Show which tickets would be re-dispatched without dispatching
---

# Resume Epic

**Announce at start:** "I'm using the resume-epic skill."

## Purpose

When `epic-team` is interrupted by a rate limit, context limit, or session disconnect, this
skill picks up exactly where it left off by:

1. Fetching all child tickets from Linear
2. Checking their current status (Done / In Review = skip)
3. Re-dispatching only the remaining tickets — sequentially to avoid rate limits
4. Reporting a final summary

This is the canonical recovery path for interrupted epic runs. Do not re-run
`epic-team` from scratch — that re-dispatches completed tickets unnecessarily.

## Usage

```
/resume-epic <epic-id>          # Resume all incomplete tickets
/resume-epic <epic-id> --dry-run  # Show what would be dispatched without dispatching
```

## Execution Algorithm

```
1. Fetch all child tickets for {epic_id} via mcp__linear-server__list_issues parentId={epic_id}

2. Classify each ticket:
   - SKIP: state is "Done" OR state is "In Review" OR state is "Merged"
   - DISPATCH: all other states (Backlog, In Progress, Todo, Blocked, etc.)

3. If --dry-run:
   Print two tables: SKIP list and DISPATCH list with states. Exit.

4. If DISPATCH list is empty:
   Report "All tickets complete — epic {epic_id} is done." Exit.

5. SEQUENTIAL dispatch (one at a time — no parallel, to avoid rate limits):
   For each ticket in DISPATCH list:
     Update Linear ticket state to "In Progress" (skip if already In Progress)
     Invoke: Skill(skill="onex:ticket-pipeline", args="{ticket_id}")
     Wait for completion
     Report result (merged / failed / blocked)
     If failed/blocked: log clearly but continue with remaining tickets

6. SUMMARY: List all tickets with final state:
   ✓ merged: OMN-XXXX — title
   ✗ blocked: OMN-YYYY — title (reason)
   ⊘ skipped: OMN-ZZZZ — title (was already Done)
```

## State Classification

| Linear State | Action |
|-------------|--------|
| Done | SKIP |
| In Review | SKIP (PR is open, don't re-dispatch) |
| Merged | SKIP |
| In Progress | DISPATCH (may have been interrupted) |
| Backlog | DISPATCH |
| Todo | DISPATCH |
| Blocked | DISPATCH (let ticket-pipeline surface the blocker) |
| Cancelled | SKIP |

## Why Sequential, Not Parallel

Parallel dispatch is what caused the original rate limit. Resume always runs sequentially.
If you need parallel execution, use `epic-team` from scratch on a fresh epic.

## Recovery from resume-epic Itself Being Interrupted

If `resume-epic` itself is interrupted, simply invoke it again with the same `epic_id`.
It re-checks Linear state each time, so already-merged tickets are automatically skipped.
This makes `resume-epic` idempotent — safe to call multiple times.

## See Also

- `epic-team` skill — full orchestration (use for new epics, not recovery)
- `ticket-pipeline` skill — per-ticket pipeline invoked by resume-epic
- `~/.claude/epics/{epic_id}/state.yaml` — epic-team state file (for reference)
```

**Step 2: Verify the file was created correctly**

Read the file back and confirm:
- YAML frontmatter is valid (name, description, version, category, tags, args)
- The algorithm section covers the sequential dispatch requirement
- The state classification table is complete

**Step 3: Test the skill description with a subagent**

Using `testing-skills-with-subagents` skill approach: launch a quick subagent that reads the skill and explains back what it would do for `resume-epic <epic-id> --dry-run` with a hypothetical epic that has 3 Done tickets and 2 Backlog tickets. Verify the subagent:
- Identifies the 3 Done tickets as SKIP
- Identifies the 2 Backlog tickets as DISPATCH
- Confirms it would NOT actually call `mcp__linear-server__*` in dry-run mode

**Step 4: Commit**

```bash
git add plugins/onex/skills/resume-epic/SKILL.md
git commit -m "feat: add resume-epic skill for rate-limit recovery [insights]"
```

---

## Task 3: Add CONTEXT_ADVISORY tier to bash_guard.py for uv lock operations

**Files:**
- Modify: `plugins/onex/hooks/lib/bash_guard.py:87-184` (pattern lists section)
- Test: `tests/unit/hooks/test_bash_guard.py` (find this file first)

### 3a: Locate and read the test file

```bash
find tests/ -name "test_bash_guard.py" -type f
```

Read that file to understand the existing test structure before writing new tests.

**Step 1: Write the failing test**

Add these test cases to `tests/unit/hooks/test_bash_guard.py`:

```python
@pytest.mark.unit
class TestContextAdvisoryPatterns:
    """Tests for the CONTEXT_ADVISORY tier (uv lock/sync operations)."""

    def test_uv_lock_triggers_advisory(self) -> None:
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "uv lock"},
            "sessionId": "test-session",
        }
        result = json.loads(
            subprocess.check_output(
                ["python", "plugins/onex/hooks/lib/bash_guard.py"],
                input=json.dumps(hook_input),
                text=True,
            )
        )
        assert result.get("decision") != "block"
        assert "reason" in result or "advisory" in result
        assert "uv" in (result.get("reason", "") + result.get("advisory", "")).lower()

    def test_uv_lock_no_verify_triggers_advisory(self) -> None:
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "uv lock --no-cache"},
            "sessionId": "test-session",
        }
        result = json.loads(
            subprocess.check_output(
                ["python", "plugins/onex/hooks/lib/bash_guard.py"],
                input=json.dumps(hook_input),
                text=True,
            )
        )
        # Must allow (exit 0) but include advisory
        assert result.get("decision") != "block"
        assert "reason" in result or "advisory" in result

    def test_uv_sync_does_not_trigger_advisory(self) -> None:
        """uv sync doesn't modify lock file — no advisory needed."""
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "uv sync"},
            "sessionId": "test-session",
        }
        result = json.loads(
            subprocess.check_output(
                ["python", "plugins/onex/hooks/lib/bash_guard.py"],
                input=json.dumps(hook_input),
                text=True,
            )
        )
        # Should allow without advisory (uv sync just installs from existing lock)
        assert result == {}

    def test_non_uv_command_unaffected(self) -> None:
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/ -v"},
            "sessionId": "test-session",
        }
        result = json.loads(
            subprocess.check_output(
                ["python", "plugins/onex/hooks/lib/bash_guard.py"],
                input=json.dumps(hook_input),
                text=True,
            )
        )
        assert result == {}
```

**Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/unit/hooks/test_bash_guard.py::TestContextAdvisoryPatterns -v
```

Expected: FAIL — `bash_guard.py` doesn't yet emit advisory for `uv lock`.

**Step 3: Implement the CONTEXT_ADVISORY tier in bash_guard.py**

Add to `bash_guard.py` after line 82 (after `__all__`):

```python
# =============================================================================
# CONTEXT_ADVISORY patterns
# =============================================================================
# Commands that should be allowed but warrant an advisory reminder.
# These exit 0 (allow) but return JSON with a "reason" advisory field
# so Claude Code can surface the warning to the agent.

CONTEXT_ADVISORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\buv\s+lock\b",
            re.IGNORECASE | re.MULTILINE,
        ),
        (
            "ADVISORY: uv lock detected. Before modifying uv.lock, verify the "
            "CI-pinned uv version in .github/workflows/ci.yml. Local and CI uv "
            "versions must match or lock file regeneration will fail in CI."
        ),
    ),
]
```

Then in `main()`, add a new tier check between the SOFT_ALERT check and the default ALLOW (before line 356 `print("{}")` at the end):

```python
    # ------------------------------------------------------------------
    # Tier 3 — CONTEXT_ADVISORY
    # ------------------------------------------------------------------
    for pattern, advisory_message in CONTEXT_ADVISORY_PATTERNS:
        if pattern.search(command):
            advisory_response: dict[str, str] = {"reason": advisory_message}
            print(json.dumps(advisory_response))
            return 0

    # ------------------------------------------------------------------
    # Default — ALLOW
    # ------------------------------------------------------------------
```

Also update `__all__` to include `CONTEXT_ADVISORY_PATTERNS`:

```python
__all__ = [
    "HARD_BLOCK_PATTERNS",
    "SOFT_ALERT_PATTERNS",
    "CONTEXT_ADVISORY_PATTERNS",
    "matches_any",
    "main",
]
```

**Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/unit/hooks/test_bash_guard.py::TestContextAdvisoryPatterns -v
```

Expected: PASS for all 4 new tests.

**Step 5: Run the full bash_guard test suite to ensure no regressions**

```bash
uv run pytest tests/unit/hooks/test_bash_guard.py -v
```

Expected: All tests PASS.

**Step 6: Run linting**

```bash
uv run ruff check plugins/onex/hooks/lib/bash_guard.py tests/unit/hooks/test_bash_guard.py
uv run ruff format --check plugins/onex/hooks/lib/bash_guard.py tests/unit/hooks/test_bash_guard.py
uv run mypy plugins/onex/hooks/lib/bash_guard.py
```

Fix any issues before committing.

**Step 7: Commit**

```bash
git add plugins/onex/hooks/lib/bash_guard.py tests/unit/hooks/test_bash_guard.py
git commit -m "feat: add CONTEXT_ADVISORY tier to bash_guard for uv lock operations [insights]"
```

---

## Task 4: Update epic-team SKILL.md with failure taxonomy and self-healing recovery

**Files:**
- Modify: `plugins/onex/skills/epic-team/SKILL.md` (add new section)

**Step 1: Add failure taxonomy section**

Append this section to `plugins/onex/skills/epic-team/SKILL.md` before the `## See Also` block:

```markdown
## Failure Taxonomy and Recovery Strategies

When a sub-agent fails or stalls, classify the failure before deciding what to do.
Never leave failed tasks unaccounted — always report them with enough context for resume.

### Failure Classes

| Failure Class | Symptoms | Recovery Strategy |
|---------------|----------|-------------------|
| `rate_limit` | Sub-agent exits with rate limit error | Wait 60s, retry the ticket via `ticket-pipeline` sequentially |
| `context_limit` | Sub-agent hits max context length mid-ticket | Spawn fresh sub-agent for that ticket; the previous work is in the branch |
| `ci_failure_uv` | CI fails with lock file or uv version error | Verify CI uv version in `.github/workflows/ci.yml`; regenerate lock with matching version |
| `ci_failure_ruff` | CI fails with ruff lint/format error | Run `uv run ruff check --fix` + `uv run ruff format`, recommit |
| `stale_branch` | PR fails to merge — "main has moved" | `git rebase origin/main`, re-push, re-enable auto-merge |
| `wrong_repo` | Ticket worked in wrong repo | Look up target repo in Linear ticket metadata (`repo` field); re-dispatch in correct repo |
| `blocker_unresolved` | Ticket is blocked by another in-progress ticket | Move to end of queue; complete blocking ticket first; retry |
| `unknown` | Failure doesn't match above patterns | Escalate to user with full diagnostic: ticket ID, last command output, branch state |

### Reporting Failed Tasks

When all other tasks complete and some failed, report:

```
## Epic {epic_id} Summary

✓ Completed: N tickets
✗ Failed: M tickets (see below)

### Failed Tickets (needs intervention)

**OMN-XXXX** — {title}
Failure class: {rate_limit | context_limit | ci_failure_uv | ...}
Branch: {branch_name}
Last known state: {what the sub-agent last did}
Resume with: /resume-epic {epic_id}
```

### Self-Healing Rules for Workers

When a worker encounters a failure:

1. **First**: Log the failure class clearly to the team lead
2. **If `rate_limit` or `context_limit`**: Mark the ticket as not-started in state.yaml, continue with next ticket. The team lead will see the gap and can invoke `/resume-epic` to re-dispatch.
3. **If `stale_branch`**: Attempt one rebase automatically. If rebase fails (conflicts), classify as `unknown` and escalate.
4. **If `ci_failure_uv`**: Check `.github/workflows/ci.yml` for pinned uv version. If different from local, regenerate lock file with correct version and recommit. One attempt only.
5. **After 2 failed recovery attempts**: Stop trying. Log diagnostic and move to the next ticket. Do not retry in a loop.
```

**Step 2: Verify the section was added correctly**

Read `plugins/onex/skills/epic-team/SKILL.md` and confirm:
- The failure taxonomy table has all 8 failure classes
- The reporting template section appears before `## See Also`
- The self-healing rules list has the "2 attempts max" rule
- No existing content was overwritten

**Step 3: Commit**

```bash
git add plugins/onex/skills/epic-team/SKILL.md
git commit -m "docs: add failure taxonomy and recovery strategies to epic-team [insights]"
```

---

## Task 5: Verify all changes and open PR

**Step 1: Run the full test suite**

```bash
uv run pytest tests/ -m unit -v --tb=short 2>&1 | tail -30
```

Expected: All unit tests pass. If failures, investigate before proceeding.

**Step 2: Run linting on all changed files**

```bash
uv run ruff check CLAUDE.md plugins/onex/hooks/lib/bash_guard.py \
  plugins/onex/skills/resume-epic/SKILL.md \
  plugins/onex/skills/epic-team/SKILL.md
uv run mypy plugins/onex/hooks/lib/bash_guard.py
```

Fix any issues and amend or commit as needed.

**Step 3: Open the PR**

```bash
gh pr create \
  --title "feat: insights-driven workflow improvements (anti-patterns, resume-epic, uv guard, failure taxonomy)" \
  --body "$(cat <<'EOF'
## Summary

Four workflow improvements surfaced by the /insights usage report (875 sessions analyzed):

- **Task 1**: Added Common Anti-Patterns section to CLAUDE.md addressing 75 wrong-approach friction instances
- **Task 2**: New `resume-epic` skill for rate-limit recovery — checks Linear state and re-dispatches only incomplete tickets sequentially
- **Task 3**: Added CONTEXT_ADVISORY tier to `bash_guard.py` — warns when `uv lock` is run, prompting version check against CI pinned version
- **Task 4**: Added failure taxonomy table and self-healing rules to `epic-team` SKILL.md

## Test plan

- [ ] `pytest tests/unit/hooks/test_bash_guard.py -v` — all tests pass including new `TestContextAdvisoryPatterns`
- [ ] `pytest tests/ -m unit -v` — no regressions
- [ ] Manual: run `/resume-epic OMN-XXXX --dry-run` in a session to verify skill loads
- [ ] Manual: run `uv lock` in a session and confirm advisory appears in hook output
EOF
)"
```

**Step 4: Confirm PR URL and add it to this plan for tracking**

Copy the PR URL from the `gh pr create` output. If CI fails, use `/ci-watch` to monitor and fix.

---

## Rollback Notes

All changes are additive (new section in CLAUDE.md, new skill file, new patterns in bash_guard.py). To rollback any task independently:

- Task 1: `git revert <commit>` for the CLAUDE.md commit
- Task 2: `git rm plugins/onex/skills/resume-epic/SKILL.md && git commit`
- Task 3: `git revert <commit>` for bash_guard — removes the CONTEXT_ADVISORY patterns and tests
- Task 4: `git revert <commit>` for epic-team SKILL.md — removes the failure taxonomy section

No database migrations, no schema changes, no Kafka topic changes.
