---
type: reference
status: current
date: "2026-09-02"
title: "OmniMarket node_build_loop_orchestrator"
topics:
  - omnimarket
  - nodes
  - onex-runtime
refs: []
---

<!-- Migrated from omnimarket:src/omnimarket/nodes/node_build_loop_orchestrator/README.md on 2026-09-01 -->

# Build Loop Orchestrator Node

This node orchestrates the build loop process, coordinating build phases and managing execution lifecycle.

## Overview
The Build Loop Orchestrator manages the execution flow of build processes, handling command intents, dispatching tasks, and aggregating results.

## Integration
1. **Initiation**: Send `ModelOrchestratorStartCommand` to begin the build loop
2. **Phase Handling**: React to `ModelPhaseCommandIntent` for build phase instructions
3. **Completion**: Process `ModelOrchestratorCompletedEvent` for final results
4. **Monitoring**: Use `ModelDispatchMetrics` and `ModelDispatchTrace` for observability

The live runner's own environment configuration (LLM endpoints, Linear team
id, worktree paths) is `ModelLiveRunnerConfig` — a separate object assembled
by the live runner (`assemble_live.py`), not a field on the start command.

## Key Components
- `ModelOrchestratorStartCommand`: Initiates the build loop process. Fields:
  `correlation_id` (required), `mode` (`build`/`close_out`/`full`/`observe`,
  default `full`), `max_cycles`, `skip_closeout`, `max_tickets`, `dry_run`,
  `requested_at` (required). `model_config` sets `extra="forbid"` — unknown
  fields raise a validation error.
- `ModelPhaseCommandIntent`: Manages individual build phase instructions
- `ModelLiveRunnerConfig`: Live runner environment configuration (LLM
  endpoints, Linear team targeting, filesystem paths) — not part of the
  start command
- `ModelOrchestratorCompletedEvent`: Signals build loop completion
- `ModelDispatchMetrics`: Performance metrics and KPIs
- `ModelDispatchTrace`: Detailed execution tracing
- `ModelOrchestratorState`: Current orchestrator status
- `ModelLoopCycleSummary`: Summary of build loop iteration

## Usage Example
```python
from datetime import UTC, datetime
from uuid import uuid4

from omnimarket.nodes.node_build_loop_orchestrator.models import (
    ModelOrchestratorStartCommand,
)

# correlation_id and requested_at are required; extra="forbid" rejects any
# field not declared on the model.
command = ModelOrchestratorStartCommand(
    correlation_id=uuid4(),
    mode="build",
    max_cycles=1,
    max_tickets=5,
    dry_run=False,
    requested_at=datetime.now(UTC),
)
# Send command to HandlerBuildLoopOrchestrator.handle()
```
