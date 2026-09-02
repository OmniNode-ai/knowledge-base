> Migrated from omnimarket:src/omnimarket/adapters/cursor/README.md on 2026-09-01 (OMN-16613)

# Cursor Adapter — OmniMarket

## Overview

Cursor adapters are `.mdc` rule files that instruct the Cursor AI to invoke
OmniMarket packages via the ONEX event bus. Each rule publishes a command event
and monitors for the corresponding completion event. **No business logic lives
in the rule.**

## How it works

1. Cursor's AI matches the rule based on file globs or user prompt
2. The rule instructs the AI to publish a command event to the bus
3. The OmniMarket node picks up the command, executes, and publishes a completion event
4. The rule instructs the AI to monitor for the completion event and format the result

## File conventions

| File | Purpose |
|------|---------|
| `aislop-sweep.mdc` | Example rule for the aislop-sweep node |
| `template.mdc` | Generic template with placeholders for new rules |

Rules are installed by copying them to `.cursor/rules/` in the project root.

## Wrapper responsibilities

1. **Argument collection and validation** — Parse user intent from the prompt
   context and map to the event payload schema from `contract.yaml`.
2. **Command options mapping** — Translate natural language or structured arguments
   into the event payload fields.
3. **Correlation ID generation** — Generate a unique `correlation_id` (UUID v4) for
   each invocation to track request/response pairs on the bus.
4. **Event publishing** — Publish the command event to the node's `subscribe_topics`
   topic with the assembled payload and correlation ID.
5. **Completion monitoring** — Listen on the node's `publish_topics` topic, filtering
   by correlation ID, with a configurable timeout.
6. **Output formatting** — Transform the completion event payload into a clear
   markdown response for the user.
7. **Timeout and error handling** — If no completion event arrives within the node's
   `descriptor.timeout_ms`, report a timeout error. Surface any error payloads
   from the completion event clearly.

## Creating a new rule

1. Copy `template.mdc` to `<skill-name>.mdc`
2. Replace all `{{PLACEHOLDER}}` values using the node's `contract.yaml`
3. Copy the resulting file to `.cursor/rules/` in the target project
