---
type: adr
status: accepted
date: "2025-12-19"
title: "ADR-0033: Registration Trigger Architecture"
adr_id: ADR-0033
topics: [omnibase_core, registration, events, commands, orchestrator, node-lifecycle]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0033: Registration Trigger Architecture

**Status**: Accepted — decision documented, implementation pending as of authoring
**Date**: 2025-12-19
**Implementation**: `src/omnibase_core/models/discovery/model_nodeintrospectionevent.py`
**Source**: omnibase_core `docs/decisions/ADR-004-registration-trigger-architecture.md`

---

## Purpose

Defines how node registration is triggered in the ONEX system: event-driven registration (via a `NodeIntrospected` EVENT) is the canonical/default path, while command-driven registration (via a `RegisterNodeRequested` COMMAND) is an optional/gated path for administrative use cases.

## Background

**Event Model** (`src/omnibase_core/models/discovery/model_nodeintrospectionevent.py`):

```python
class ModelNodeIntrospectionEvent(ModelOnexEvent):
    """Event published by nodes to announce their capabilities for discovery.

    Automatically published by MixinEventDrivenNode when a node starts up.
    """
    event_type: str = Field(default=NODE_INTROSPECTION_EVENT)
    node_name: str
    version: ModelSemVer
    node_type: str  # effect, compute, reducer, orchestrator
    capabilities: ModelNodeCapability
```

**Event Type Constant**: 2026-08-25 migration note — the constant now lives at
`src/omnibase_core/constants/constants_event_types.py` (renamed from
`constants/event_types.py` since this decision was written):

```python
NODE_INTROSPECTION_EVENT = "node_introspection_event"
```

**Topic Taxonomy** (see the ONEX topic taxonomy reference, migrated alongside this decision):

```text
onex.registration.commands   # Registration commands (incl. RegisterNodeRequested)
onex.registration.events     # Registration events (incl. NodeIntrospected)
onex.registration.intents    # Registration coordination
onex.registration.snapshots  # Registration state snapshots
```

## Decision

**Event-driven registration is canonical.** Nodes automatically publish `NodeIntrospected`
on startup; the Registration Orchestrator consumes it and registers the node with no
external coordination required. `RegisterNodeRequested` (command-driven) remains available
for administrative, exceptional, or gated scenarios: pre-registration before node startup,
administrative bulk registration, policy-gated registration flows, re-registration after
failures.

### Registration Trigger Mapping

| Trigger | Message Category | Canonical/Gated | Use Case |
|---------|------------------|-----------------|----------|
| `NodeIntrospected` | EVENT | **Canonical** | Automatic node startup |
| `RegisterNodeRequested` | COMMAND | Gated/Optional | Administrative control |

### Orchestrator Behavior

The Registration Orchestrator MUST accept both triggers, apply consistent validation
regardless of trigger source, emit the same `NodeRegistered` event on success from either
path, and support additional authorization gating for commands.

### Rationale

1. **Alignment with ONEX Philosophy**: events represent facts (the node announced itself); this is more natural than requiring an external command for basic startup.
2. **Automatic Startup Flow**: nodes register without external coordination, reducing operational complexity.
3. **Clear Semantic Distinction**: events = facts about what happened; commands = requests to perform actions.
4. **Execution Shape Compliance**: both `Event → Orchestrator` and `Command → Orchestrator` are valid canonical execution shapes.

### Example — Canonical Flow (Event-Driven)

```python
introspection_event = ModelNodeIntrospectionEvent.create_from_node_info(
    node_id=node_id,
    node_name="MyComputeNode",
    version=ModelSemVer(major=1, minor=0, patch=0),
    node_type="compute",
    actions=["transform", "validate"],
)

await event_bus.publish(topic="onex.registration.events", event=introspection_event)
# Registration Orchestrator consumes and processes — Shape 1: Event -> Orchestrator
```

### Example — Gated Flow (Command-Driven, future)

```python
register_command = ModelRegisterNodeRequestedCommand(
    node_id=node_id,
    node_name="MyComputeNode",
    node_type="compute",
    requested_by="admin-user",
    reason="Pre-registration for deployment",
)

await event_bus.publish(topic="onex.registration.commands", command=register_command)
# Registration Orchestrator consumes with additional gate checks — Shape 4: Command -> Orchestrator
```

## Trade-offs

1. **Event Bus Dependency at Startup** — nodes cannot register if the event bus is unavailable; mitigated by retry with exponential backoff in the introspection publisher.
2. **Less Explicit Control for the Default Path** — mitigated by the command-driven path remaining available for gated scenarios.
3. **Two Code Paths in the Orchestrator** — shared validation logic minimizes duplication.

## Implementation Status (as of authoring)

**Implemented**: `NODE_INTROSPECTION_EVENT` constant, `ModelNodeIntrospectionEvent` model,
`MixinIntrospectionPublisher` (`src/omnibase_core/mixins/mixin_introspection_publisher.py`),
registration topic taxonomy.

**Planned/Reserved at authoring time**: `RegisterNodeRequested` COMMAND model, a dedicated
Registration Orchestrator node, gating logic for command-driven registration. This decision
record was not re-verified against current implementation status of those reserved items
during the 2026-08-25 migration — treat as historical intent, not a current-state claim.

---

## References

- Canonical Execution Shapes and ONEX topic taxonomy references (this repository)
- `src/omnibase_core/constants/constants_event_types.py` — `NODE_INTROSPECTION_EVENT`
- `src/omnibase_core/models/discovery/model_nodeintrospectionevent.py` — `ModelNodeIntrospectionEvent`
- `src/omnibase_core/mixins/mixin_introspection_publisher.py` — `MixinIntrospectionPublisher`

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base. Corrected `constants/event_types.py` → `constants/constants_event_types.py` (verified renamed live). Replaced an email-shaped code-example placeholder with a non-email value per KB sanitization policy. Did not re-verify "Planned/Reserved" implementation items against current source. |
| 2025-12-19 | Initial decision |
