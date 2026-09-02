---
type: reference
status: current
date: "2026-09-02"
title: "OmniMarket node_ticket_pipeline"
topics:
  - omnimarket
  - nodes
  - onex-runtime
refs: []
---

<!-- Migrated from omnimarket:src/omnimarket/nodes/node_ticket_pipeline/README.md on 2026-09-01 -->

# Ticket Pipeline Node

This node manages the processing pipeline for tickets in the omnimarket system.

## Overview
The Ticket Pipeline Node handles the lifecycle of ticket processing through distinct phases, providing event-driven updates and maintaining state throughout the process.

The current bounded market-owned slice wires:

- `PRE_FLIGHT`: deterministic input validation with no side effects.
- `IMPLEMENT`: compile-only dispatch-worker prompt generation via `node_dispatch_worker`; no agent spawn, TaskCreate call, deploy, or runtime mutation.

Later side-effect phases stop explicitly as `blocked/not_implemented` until they are wired.

## Integration
1. **Initiation**: Send a `ModelPipelineStartCommand` to begin processing
2. **Event Handling**: Subscribe to `ModelPipelinePhaseEvent` for phase-by-phase updates
3. **Completion**: Listen for `ModelPipelineCompletedEvent` to finalize processing
4. **State Management**: Query `ModelPipelineState` for current processing status

## Key Components
- `ModelPipelineStartCommand`: Initiates the ticket processing pipeline.
  Fields: `correlation_id` (required), `ticket_id` (required — must match an
  uppercase Linear key such as `TEAM-1234`), `skip_test_iterate`, `dry_run`,
  `skip_to`, `requested_at` (required). `model_config` sets `extra="forbid"`
  — unknown fields raise a validation error.
- `ModelPipelinePhaseEvent`: Emitted during each processing phase
- `ModelPipelineCompletedEvent`: Signals successful pipeline completion
- `ModelPipelineState`: Maintains current pipeline status

## Usage Example
```python
from datetime import UTC, datetime
from uuid import uuid4

from omnimarket.nodes.node_ticket_pipeline.models import ModelPipelineStartCommand

# correlation_id and requested_at are required; extra="forbid" rejects any
# field not declared on the model (e.g. a free-form `payload`).
command = ModelPipelineStartCommand(
    correlation_id=uuid4(),
    ticket_id="TEAM-1234",
    requested_at=datetime.now(UTC),
)
# Send command to HandlerTicketPipeline.run_executable_pipeline()
```
