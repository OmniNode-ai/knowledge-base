---
type: reference
status: current
date: "2026-09-02"
title: "ADR: EnumMessageCategory vs EnumNodeOutputType Distinction"
topics: [omnibase-infra, adr, enum, message]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-enum-message-category-vs-node-output-type.md on 2026-09-02. -->

# ADR: EnumMessageCategory vs EnumNodeOutputType Distinction

**Status**: Accepted
**Date**: 2025-12-21

## Context

ONEX uses two distinct enums that appear similar but serve fundamentally different purposes:

1. **EnumMessageCategory** (`omnibase_infra.enums`)
   - Values: `EVENT`, `COMMAND`, `INTENT`
   - Purpose: Message routing via Kafka topics

2. **EnumNodeOutputType** (`omnibase_infra.enums`)
   - Values: `EVENT`, `COMMAND`, `INTENT`, `PROJECTION`
   - Purpose: Node execution shape validation

The presence of `PROJECTION` in `EnumNodeOutputType` but not in `EnumMessageCategory` caused confusion, leading to incorrect documentation claiming the `MessageDispatchEngine` supports "four ONEX message categories."

## Decision

**PROJECTION is NOT a message category for routing.**

Projections are:
- **Node output types** produced by REDUCER nodes
- **Local state outputs** applied by the runtime to a projection sink
- **NOT routed** via Kafka topics or `MessageDispatchEngine`
- **NOT part of** `EnumMessageCategory`

The two enums serve distinct architectural layers:

| Enum | Layer | Purpose | Used By |
|------|-------|---------|---------|
| `EnumMessageCategory` | Transport | Topic routing, dispatcher selection | `MessageDispatchEngine`, Kafka adapters |
| `EnumNodeOutputType` | Execution | Handler return type validation | Execution shape validator, node contracts |

## Rationale

### Why PROJECTION is not routable

1. **Semantic difference**: Projections are derived state, not protocol messages
2. **No external consumers**: Projections are internal to the runtime
3. **No topic convention**: Unlike `*.events`, `*.commands`, `*.intents`, there is no `*.projections` topic pattern
4. **Single responsibility**: REDUCER nodes produce projections; the runtime applies them locally

### Why two separate enums

1. **Separation of concerns**: Routing vs validation are distinct responsibilities
2. **Different lifetimes**: Message categories are transport-level; output types are execution-level
3. **Extensibility**: Output types may expand (e.g., `QUERY`, `METRIC`) without affecting routing
4. **Type safety**: Prevents accidental use of `PROJECTION` in routing contexts

## Consequences

### Positive

- Clear architectural boundaries between transport and execution layers
- `MessageDispatchEngine` remains focused on routable message categories
- `EnumNodeOutputType` can validate REDUCER outputs without routing implications
- Prevents accidental PROJECTION topic routing

### Negative

- Requires documentation to explain the distinction
- Developers must understand which enum to use in each context
- Mapping between enums requires explicit conversion methods

## Implementation

### EnumNodeOutputType conversion methods

```python
class EnumNodeOutputType(str, Enum):
    EVENT = "event"
    COMMAND = "command"
    INTENT = "intent"
    PROJECTION = "projection"

    def is_routable(self) -> bool:
        """Check if this output type can be routed via Kafka."""
        return self != EnumNodeOutputType.PROJECTION

    def to_message_category(self) -> EnumMessageCategory:
        """Convert to message category for routing.

        Raises:
            ValueError: If this is PROJECTION (not routable)
        """
        if self == EnumNodeOutputType.PROJECTION:
            raise ValueError("PROJECTION has no message category")
        return EnumMessageCategory(self.value)
```

### Dispatch engine topic parsing

```python
# EnumMessageCategory.from_topic() only recognizes:
# - "events" -> EVENT
# - "commands" -> COMMAND
# - "intents" -> INTENT
# Topics with "projections" segment return None (invalid category)
```

### Negative test case

A test exists to document and verify this behavior:

```python
async def test_dispatch_projection_topic_returns_invalid_message():
    """Test that PROJECTION topics are NOT routable via MessageDispatchEngine."""
    result = await engine.dispatch("dev.order.projections.v1", envelope)
    assert result.status == EnumDispatchStatus.INVALID_MESSAGE
```

## References

- `src/omnibase_infra/enums/enum_message_category.py`
- `src/omnibase_infra/enums/enum_node_output_type.py`
- `src/omnibase_infra/runtime/message_dispatch_engine.py`
- `tests/unit/runtime/test_message_dispatch_engine.py`
- CLAUDE.md "Enum Usage" section
