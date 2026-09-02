---
type: guide
status: current
title: "Authoring an ONEX Skill"
topics: ["omniclaude", "skills", "reference"]
refs: ["guides/adding-a-skill.md"]
---

# Authoring an ONEX Skill

> Migrated from omniclaude:docs/reference/SKILL_AUTHORING_GUIDE.md on 2026-09-01 (OMN-16609). Trimmed to the material not already covered by [Adding a Skill](adding-a-skill.md) — see that guide for the directory layout, SKILL.md front matter, and invocation basics. This page holds the deeper reference: dispatch contracts, supporting-script conventions, the output-suppression contract, and the receipt-mode dispatch pattern.

## Dispatch Contract Rules

Skills that orchestrate agents must define explicit dispatch contracts. These are
execution-critical rules that Claude must follow without deviation.

Standard rules for orchestrator skills:

```
Rule: NEVER call Edit(), Write(), or Bash(code-modifying) directly from orchestrator.
Rule: ALL Task() calls MUST use subagent_type="onex:general-purpose". No exceptions.
Rule: NO git operations in spawned agents. Git is coordinator-only, user-approved only.
Rule: Always dispatch all agents in a SINGLE message for true parallelism.
```

## Supporting Scripts

Skills may include executable scripts that agents invoke:

```bash
# Scripts should be executable and take positional arguments
plugins/onex/skills/pr-review/fetch-pr-data <PR-number>
plugins/onex/skills/pr-review/collate-issues <PR-number>
plugins/onex/skills/pr-review/review-pr <PR-number> [--strict] [--json]
```

Reference scripts from `SKILL.md` using `${CLAUDE_PLUGIN_ROOT}/skills/<skill-name>/<script>`.

## Best Practices

1. **Dispatch, do not implement.** Orchestrator skills coordinate agents; they do not
   write code or modify files directly.
2. **Define exit criteria.** Every skill should specify when it is done and what success
   looks like. Ambiguous completion criteria cause agents to over- or under-execute.
3. **Single-message parallelism.** When dispatching multiple agents, always dispatch
   all of them in a single message. Sequential dispatch destroys parallelism.
4. **Explicit contracts between phases.** Use structured JSON for data passed between
   phases. Ambiguous hand-offs cause integration failures.
5. **Keep SKILL.md scannable.** Claude reads SKILL.md during execution. Use headers,
   code blocks, and numbered lists. Avoid dense paragraphs.
6. **Version supporting scripts.** If a script's interface changes, update the version
   in front matter and document the breaking change.
7. **Do not embed secrets.** Scripts that need credentials must read from environment
   variables. Never hardcode tokens or passwords.

## Output Suppression Contract

Every bash block in a skill prompt that calls an external process MUST apply one of
these patterns. Unsuppressed output enters Claude's context window on every skill
invocation — this is a direct token cost.

### Pattern A — Discard (output not needed by Claude)

Use when Claude only needs to know if the command succeeded:

```bash
some-command 2>/dev/null
some-command --quiet
some-command > /dev/null 2>&1
```

### Pattern B — Trim (Claude needs the result, not the verbosity)

Use when Claude needs to read the output but not all of it:

```bash
some-command 2>&1 | tail -50      # errors bubble to top after tail
some-command | head -20           # take the first N matches
docker logs --tail 20 <container> # last N log lines only
pytest -q --tb=short              # compact test output
gh pr list --limit 50             # cap API result sets
```

### Pattern C — Structured contract (subprocess tools)

Use when invoking a standalone Python script or aggregator:

```bash
python script.py --args 2>/dev/null   # stderr silenced; stdout is JSON only
```

### Anti-patterns (NEVER use in skill prompts)

- `pytest -v` — prints every test name; use `-q --tb=short`
- `docker logs <container>` without `--tail` — unbounded stream
- `grep -r` without `| head -N` — could return thousands of lines
- `gh pr list --limit 100` — 100 PRs x ~2KB JSON = 200KB in context
- `pre-commit run --all-files` without `| tail -50` — full hook output
- `find <dir>` without `-maxdepth` or `| head -N` — unbounded filesystem scan

### Reference implementation

`hostile_reviewer/prompt.md` Step 1: aggregator runs all models silently,
outputs compact JSON to stdout only. Claude reads ~500 tokens of structured
findings regardless of how verbose the underlying models are.

### Enforcement

The suppression contract is regression-tested in
`tests/unit/skills/test_output_suppression.py`. Any new skill that introduces
unbounded output patterns will fail CI.

## Receipt-Mode Pattern (Required for R-class dispatch skills)

Skills that dispatch to omnimarket nodes must use the **onex skill receipt
pattern** instead of inline dispatch shims. The CI ratchet gate (`skill-receipt-mode-gate`)
enforces this pattern and will block merges on non-compliant new skills.

### What the receipt-mode flag is

A receipt-mode skill declares `receipt_mode: true` in its `SKILL.md` front
matter and dispatches via the single-command pattern:

```yaml
---
name: my-skill-name
description: Dispatches to the my_feature domain node in omnimarket.
receipt_mode: true
---
```

The `receipt_mode: true` flag signals that the skill's dispatch result is
validated against a structured receipt returned by the omnimarket node, rather
than relying on inline output parsing.

### Correct skill stub shape (post-migration)

```markdown
# my_skill

## Overview

Thin dispatch stub. Execution logic lives in omnimarket `node_my_feature_orchestrator`.

## Quick Start

/my_skill

## Methodology

1. Run: `uv run onex run node_my_feature_orchestrator --args '{"context": "..."}'`
2. Display the structured receipt returned by the node.

## Notes

- This skill uses receipt-mode dispatch. Do not add inline execution steps.
- See omnimarket `node_my_feature_orchestrator` for internals.
```

### Which skill categories are subject to this requirement

R-class skills are those that:
- Dispatch to an omnimarket node via `uv run onex run node_*`
- Previously used inline `claude -p`, `Agent()`, or `Task()` dispatch shims

Skills that are pure UX triggers with no omnimarket dispatch (e.g. `/login`,
`/recall`, `/set_session`) are exempt.

### Diagnosing CI ratchet failures

If the `skill-receipt-mode-gate` check fails in CI:

1. Identify which skill file triggered the gate (check CI output for the
   skill name).
2. Verify the skill's `SKILL.md` front matter includes `receipt_mode: true`.
3. Verify the skill calls `uv run onex run node_*` rather than inline shim
   patterns (`claude -p`, bare `Agent()`, hand-rolled dispatch loops).
4. If this is a new skill that legitimately does not dispatch to omnimarket
   (pure UX trigger), add it to the gate's allowlist in
   `tests/unit/skills/test_receipt_mode_gate.py` with a comment explaining
   why it is exempt.
