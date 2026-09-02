---
type: guide
status: current
date: "2026-09-02"
title: "OmniMarket Claude Code Adapter"
topics:
  - omnimarket
  - adapters
  - claude-code
refs: []
---

<!-- Migrated from omnimarket:src/omnimarket/adapters/claude_code/README.md on 2026-09-01 -->

# Claude Code Adapter — OmniMarket

## Overview

Claude Code adapters are thin SKILL.md wrappers that invoke OmniMarket packages
via the ONEX event bus. Each wrapper publishes a command event and monitors for
the corresponding completion event. **No business logic lives in the wrapper.**

## How it works

1. User invokes the skill (e.g. `/aislop-sweep --dry-run`)
2. The SKILL.md instructs the AI to publish a command event to the bus
3. The OmniMarket node picks up the command, executes, and publishes a completion event
4. The SKILL.md monitors for the completion event and formats the result

## File conventions

| File | Purpose |
|------|---------|
| `aislop_sweep_SKILL.md` | Example wrapper for the aislop-sweep node |
| `template_SKILL.md` | Generic template with placeholders for new skills |

## Wrapper responsibilities

1. **Argument collection and validation** — Parse user-provided flags and map them
   to the event payload schema defined in the node's `contract.yaml`.
2. **Command options mapping** — Translate platform-specific argument syntax (e.g.
   `--dry-run`, `--repos omniclaude`) into the structured event payload fields.
3. **Correlation ID generation** — Generate a unique `correlation_id` (UUID v4) for
   each invocation to track request/response pairs on the bus.
4. **Event publishing** — Publish the command event to the node's `subscribe_topics`
   topic with the assembled payload and correlation ID.
5. **Completion monitoring** — Listen on the node's `publish_topics` topic, filtering
   by correlation ID, with a configurable timeout.
6. **Output formatting** — Transform the completion event payload into Claude Code's
   expected output format (markdown tables, status summaries, etc.).
7. **Timeout and error handling** — If no completion event arrives within the node's
   `descriptor.timeout_ms`, report a timeout error. Surface any error payloads
   from the completion event clearly to the user.

## Creating a new wrapper

1. Copy `template_SKILL.md` to `<skill_name>_SKILL.md`
2. Replace all `{{PLACEHOLDER}}` values using the node's `contract.yaml`
3. Place the resulting file in your Claude Code skills directory
   (e.g. `omniclaude/plugins/onex/skills/<skill_name>/SKILL.md`)
