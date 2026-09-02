---
type: guide
status: current
date: "2026-09-01"
title: "OmniMarket Skill-Backing Node Handler Pattern"
topics:
  - omnimarket
  - onex-runtime
  - dispatch
refs: []
---

<!-- Migrated from omnimarket:docs/patterns/skill_backing_node_pattern.md on 2026-09-01 -->

# Pattern: Skill-Backing Node Handler

Every skill-backing omnimarket node follows the same shape so the foreground
caller can drive dispatch deterministically. This document is canonical; it
augments the foreground-only Agent() ADR (recorded in the org's internal
decision record as `omnimarket-agent-spawn-foreground-only`, not published
here because its evidence body describes internal agent-harness session
topology) with the per-handler responsibilities those skills depend on.

## Handler contract

A skill-backing node handler is one of two purities:

- `COMPUTE_GENERIC` — synchronous compile-then-return. The handler validates
  the input, compiles the worker prompt, persists the dispatch record, and
  returns the typed result in a single call.
- `ORCHESTRATOR_GENERIC` — Kafka-driven. The handler subscribes to its command
  topic, performs the same compile + persist + emit-result sequence, and
  publishes the typed result on its event topic.

Both purities adhere to the same input/output contracts and the same
dispatch-record write step. The only difference is transport.

## Required input model fields

Reuse `ModelDispatchWorkerCommand` from
`omnimarket.nodes.node_dispatch_worker.models.model_dispatch_worker_command`.
Do NOT duplicate the model under a per-skill name.

Required fields:

- `name` (str) — worker handle.
- `team` (str) — team scoping for TaskList.
- `role` (EnumWorkerRole) — one of seven role enums (watcher, fixer, designer,
  auditor, synthesizer, sweep, ops).
- `scope` (str) — goal description.
- `targets` (list[str]) — tickets, PRs, or paths the worker owns.

Skill-specific extensions belong in a sibling input model that wraps
`ModelDispatchWorkerCommand`, not in a redefinition of the model itself.

## Required output model fields

Reuse `ModelDispatchWorkerResult` from
`omnimarket.nodes.node_dispatch_worker.models.model_dispatch_worker_result`.
Do NOT duplicate the model under a per-skill name.

Required fields:

- `validated_task_description` (str) — TaskList subject line.
- `validated_prompt_template` (str) — compiled worker prompt.
- `proposed_agent_spawn_args` (dict[str, str]) — args foreground passes to
  `Agent(**args)`. Keys: `name`, `team_name`, `model`, `subagent_type`.
- `collision_fence_embeds` (list[str]) — fence strings embedded in the prompt.
- `rejected_reason` (str) — non-empty on rejection (e.g., duplicate worker).

For `deterministic_node` and `review_worker` archetypes, the output model
mirrors this shape but `proposed_agent_spawn_args` stays empty since no spawn
follows.

## Dispatch record persistence

Before returning the typed result, the handler persists a `ModelDispatchRecord`
to `$ONEX_STATE_DIR/dispatches/<agent_id>.yaml`.

Implementation note: import the writer via
`from omnimarket.nodes.node_dispatch_worker.handlers.dispatch_record_writer import write_dispatch_record`
and the model via
`from omnimarket.nodes.node_dispatch_worker.models.model_dispatch_record import ModelDispatchRecord`.
Both live in `omnimarket.nodes.node_dispatch_worker` — the Phase-1 omniclaude
home was a temporary staging location and has been removed.

The handler MUST fail loud (raise `RuntimeError`) if the import chain breaks.
Never silently skip persistence — the dispatch record is the audit trail that
downstream verification depends on.

## Why the handler does NOT call Agent()

The `Agent` tool is foreground-only. Subagents, headless `claude -p`, and
runtime workers do not have it. Handlers that compile worker prompts cannot
call `Agent()` themselves; they return `proposed_agent_spawn_args` and the
foreground caller invokes `Agent(**args)`.

This rule is enforced by the foreground-only Agent() ADR. The handler's role
is "compile + persist + return"; the foreground's role is "read result + call
TeamCreate + TaskCreate + Agent()". Handlers that call Agent directly violate
the ADR and will fail in production whenever the skill is invoked from a
subagent context.
