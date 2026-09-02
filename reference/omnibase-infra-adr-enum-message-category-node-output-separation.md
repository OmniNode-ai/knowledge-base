---
type: reference
status: current
date: "2026-09-02"
title: "ADR-002: Separation of EnumMessageCategory and EnumNodeOutputType"
topics: [omnibase-infra, adr, enum, message]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-002-enum-message-category-node-output-separation.md on 2026-09-02. -->

# ADR-002: Separation of EnumMessageCategory and EnumNodeOutputType

## Status

Accepted

## Date

2025-12-20

## Context

The ONEX infrastructure relies on enum types to categorize messages flowing through the event-driven architecture. Two related but semantically distinct concepts were conflated into a single enum:

1. **Message Routing Categories**: How messages are routed through Kafka topics (`*.events`, `*.commands`, `*.intents`). These represent the logical routing destinations for messages in the event bus.

2. **Node Output Types**: What types of outputs ONEX nodes can produce, used for execution shape validation in the 4-node architecture (Effect, Compute, Reducer, Orchestrator).

**The Problem: Drift Between Packages**

The `omnibase_core` package defined `EnumMessageCategory` with three values:
- `EVENT` - Domain events representing facts about what happened
- `COMMAND` - Requests for action to be performed
- `INTENT` - User intentions requiring validation

The `omnibase_infra` package extended `EnumMessageCategory` with a fourth value:
- `PROJECTION` - State projections for read model optimization

This drift caused:
- **Type confusion**: Code couldn't reliably import `EnumMessageCategory` from either package
- **Semantic mismatch**: PROJECTION was added for node output validation, but projections are NOT routed through Kafka topics - they are state outputs produced by REDUCER nodes
- **Coupling concerns**: The core package shouldn't need to know about infrastructure-specific validation concepts

**ONEX 4-Node Architecture Context**

Understanding the problem requires understanding the ONEX 4-node architecture:

| Handler Type | Allowed Outputs | Cannot Output |
|--------------|----------------|---------------|
| EFFECT | EVENT, COMMAND | PROJECTION |
| COMPUTE | EVENT, COMMAND, INTENT, PROJECTION | (none) |
| REDUCER | PROJECTION | EVENT |
| ORCHESTRATOR | COMMAND, EVENT | INTENT, PROJECTION |

REDUCER nodes specifically produce PROJECTION outputs, which represent consolidated state (e.g., `OrderSummaryProjection`, `UserProfileProjection`). These projections are stored or returned directly - they are NOT published to Kafka topics for routing.

## Decision

We separated the concerns into two distinct enums:

### EnumMessageCategory (Routing)

Location: `src/omnibase_infra/enums/enum_message_category.py`

```python
class EnumMessageCategory(str, Enum):
    """Message categories for ONEX event-driven architecture.

    These represent the canonical message types that flow through
    the ONEX Kafka-based event bus. Each category has specific
    topic naming conventions and handler constraints.
    """
    EVENT = "event"    # Read from *.events topics
    COMMAND = "command"  # Read from *.commands topics
    INTENT = "intent"   # Read from *.intents topics
```

**Purpose**: Defines how messages are routed through Kafka topics.

### EnumNodeOutputType (Validation)

Location: `src/omnibase_infra/enums/enum_node_output_type.py`

```python
class EnumNodeOutputType(str, Enum):
    """Valid output types for ONEX 4-node architecture execution shape validation.

    This enum defines what types of outputs a node can produce. The execution
    shape validator uses this to ensure nodes only produce outputs allowed
    for their handler type.
    """
    EVENT = "event"
    COMMAND = "command"
    INTENT = "intent"
    PROJECTION = "projection"  # Only valid here, not in EnumMessageCategory
```

**Purpose**: Defines valid output types for execution shape validation.

### Validation Rules Updated

The `ModelExecutionShapeRule` now uses `EnumNodeOutputType` exclusively:

```python
EXECUTION_SHAPE_RULES: dict[EnumHandlerType, ModelExecutionShapeRule] = {
    EnumHandlerType.REDUCER: ModelExecutionShapeRule(
        handler_type=EnumHandlerType.REDUCER,
        allowed_return_types=[EnumNodeOutputType.PROJECTION],
        forbidden_return_types=[EnumNodeOutputType.EVENT],
        can_publish_directly=False,
        can_access_system_time=False,
    ),
    # ... other handler types
}
```

### Union Types for Flexibility

Validators accept both enum types where needed:

```python
def is_output_allowed(
    self,
    handler_type: EnumHandlerType,
    output_category: EnumMessageCategory | EnumNodeOutputType,
) -> bool:
```

This allows validation of:
- Message categories detected from routing context (`EnumMessageCategory`)
- Output types detected from node return values (`EnumNodeOutputType`)

## Rationale

### 1. Semantic Correctness

PROJECTION is fundamentally different from EVENT, COMMAND, and INTENT:

| Aspect | EVENT/COMMAND/INTENT | PROJECTION |
|--------|---------------------|------------|
| Kafka Routing | Yes - published to topics | No - not routed |
| Producer | All node types | REDUCER only |
| Purpose | Message passing | State consolidation |
| Topic Pattern | `*.events`, `*.commands`, `*.intents` | N/A |

Projections are the output of state reduction operations. They represent materialized views or denormalized state, not messages for routing.

### 2. Separation of Concerns

The two enums serve different architectural layers:

```
Application Layer
       |
       v
+------------------+     +------------------+
| EnumNodeOutputType|     | EnumMessageCategory|
| (Validation)     |     | (Routing)        |
+------------------+     +------------------+
       |                        |
       v                        v
Execution Shape             Kafka Event Bus
Validator                   Topic Selection
```

### 3. Single Package Ownership

Both enums now live in `omnibase_infra`:
- `EnumMessageCategory` - infrastructure routing concern
- `EnumNodeOutputType` - infrastructure validation concern

This eliminates the core/infra drift issue and places both enums where they're used.

### 4. Type System Expressiveness

The union type `EnumMessageCategory | EnumNodeOutputType` explicitly documents when both enum types are valid inputs. This is clearer than a single overloaded enum with ambiguous semantics.

### 5. Forward Compatibility

Each enum can evolve independently:
- New message categories can be added for routing without affecting validation
- New output types can be added for validation without affecting routing
- Teams can extend either enum for domain-specific needs

## Consequences

### Positive

1. **Clear Semantic Distinction**: Code using message categories vs output types is now explicit about which domain it operates in.

2. **Type Safety**: The type system catches incorrect usage - you can't accidentally use `PROJECTION` in message routing code.

3. **Eliminated Drift**: Both packages now use consistent enum definitions from a single source.

4. **Better Documentation**: The enum docstrings clearly explain their purpose and constraints.

5. **ONEX Architecture Alignment**: The separation aligns with the 4-node architecture's distinction between message routing (event bus) and output validation (execution shapes).

6. **Easier Testing**: Validators can be tested against specific enum types rather than a combined enum with mixed semantics.

### Negative

1. **Union Type Complexity**: Validators now use union types (`EnumMessageCategory | EnumNodeOutputType`), adding cognitive load when reading signatures.

2. **Conversion Logic Required**: The `_to_node_output_type()` function maps between enums:
   ```python
   _MESSAGE_CATEGORY_TO_NODE_OUTPUT: dict[EnumMessageCategory, EnumNodeOutputType] = {
       EnumMessageCategory.EVENT: EnumNodeOutputType.EVENT,
       EnumMessageCategory.COMMAND: EnumNodeOutputType.COMMAND,
       EnumMessageCategory.INTENT: EnumNodeOutputType.INTENT,
   }
   ```

3. **Pattern Matching Duplication**: The execution shape validator has separate pattern dictionaries for message categories and projection detection.

4. **Learning Curve**: Developers must understand when to use which enum, though the clear naming (`MessageCategory` vs `NodeOutputType`) helps.

## Alternatives Considered

### 1. Keep Single Enum with PROJECTION in Core

**Approach**: Add PROJECTION to `omnibase_core.EnumMessageCategory`.

**Why Rejected**:
- Semantic mismatch: PROJECTION is not a message routing category
- Core package shouldn't contain infrastructure-specific validation concepts
- Would require core to depend on infrastructure domain knowledge
- Future core updates might remove PROJECTION, causing drift again

### 2. Remove PROJECTION Entirely

**Approach**: Don't validate PROJECTION outputs at all.

**Why Rejected**:
- REDUCER nodes specifically produce projections - this is a critical architectural constraint
- Without PROJECTION validation, reducers could return events (violating determinism requirements)
- The 4-node architecture explicitly defines reducer output constraints
- Removing validation would weaken execution shape enforcement

### 3. Create Separate Validation Module with Custom Types

**Approach**: Create a new validation-specific module with its own type hierarchy.

**Why Rejected**:
- Adds unnecessary complexity
- Would require additional type conversions between domains
- The existing enum pattern is well-understood by the team
- Two enums is simpler than a new module hierarchy

### 4. Use String Literals Instead of Enums

**Approach**: Replace enums with string literal types for flexibility.

**Why Rejected**:
- Loses IDE autocomplete and type checking benefits
- No runtime validation of values
- Harder to discover valid values
- ONEX explicitly prefers strong typing over string literals

## Implementation Notes

### Key Files Modified

- `src/omnibase_infra/enums/enum_message_category.py` - Reduced to 3 values (EVENT, COMMAND, INTENT)
- `src/omnibase_infra/enums/enum_node_output_type.py` - New file with 4 values (EVENT, COMMAND, INTENT, PROJECTION)
- `src/omnibase_infra/validation/validator_execution_shape.py` - Updated to use union types
- `src/omnibase_infra/validation/validator_runtime_shape.py` - Updated to use union types
- `src/omnibase_infra/models/validation/model_execution_shape_rule.py` - Uses EnumNodeOutputType for allowed/forbidden types

### Migration Pattern

For existing code using the old combined enum:

```python
# Before: Single enum with PROJECTION
from omnibase_infra.enums import EnumMessageCategory
category = EnumMessageCategory.PROJECTION  # ERROR - no longer exists

# After: Use appropriate enum based on context
from omnibase_infra.enums import EnumMessageCategory, EnumNodeOutputType

# For routing/Kafka topics
message_category = EnumMessageCategory.EVENT  # or COMMAND, INTENT

# For execution shape validation
output_type = EnumNodeOutputType.PROJECTION  # or EVENT, COMMAND, INTENT
```

### Detection Logic

The execution shape validator uses multi-phase detection in `_detect_message_category()`:

```python
# Phase 1: Suffix patterns (most reliable)
suffix_patterns = [
    ("EventMessage", EnumMessageCategory.EVENT),
    ("Event", EnumMessageCategory.EVENT),
    ("CommandMessage", EnumMessageCategory.COMMAND),
    ("Command", EnumMessageCategory.COMMAND),
    ("IntentMessage", EnumMessageCategory.INTENT),
    ("Intent", EnumMessageCategory.INTENT),
    # Projections use EnumNodeOutputType (not a message category)
    ("ProjectionMessage", EnumNodeOutputType.PROJECTION),
    ("Projection", EnumNodeOutputType.PROJECTION),
]

# Phase 2: Prefix patterns (Model* naming convention)
prefix_patterns = [
    ("ModelEvent", EnumMessageCategory.EVENT),
    ("ModelCommand", EnumMessageCategory.COMMAND),
    ("ModelIntent", EnumMessageCategory.INTENT),
    ("ModelProjection", EnumNodeOutputType.PROJECTION),
]

# Phase 3: Uppercase enum-style names
uppercase_patterns = {
    "EVENT": EnumMessageCategory.EVENT,
    "COMMAND": EnumMessageCategory.COMMAND,
    "INTENT": EnumMessageCategory.INTENT,
    "PROJECTION": EnumNodeOutputType.PROJECTION,
}

# Phase 4: Lenient substring matching (fallback)
```

### Runtime Validator Usage

```python
from omnibase_infra.validation import RuntimeShapeValidator
from omnibase_infra.enums import EnumNodeArchetype, EnumNodeOutputType
from omnibase_infra.models.validation import ModelOutputValidationParams

validator = RuntimeShapeValidator()

# Validate reducer output using ModelOutputValidationParams
params = ModelOutputValidationParams(
    node_archetype=EnumNodeArchetype.REDUCER,
    output=my_projection,
    output_category=EnumNodeOutputType.PROJECTION,  # Correct - projections use EnumNodeOutputType
)
violation = validator.validate_handler_output(params)
```

## References

- **Ticket**:  - Resolve EnumMessageCategory drift between core and infra
- **PR**: #64 - fix(enums): resolve EnumMessageCategory drift between core and infra
- **Related ADR**: See companion ADR at `docs/decisions/adr-enum-message-category-vs-node-output-type.md` (legacy `docs/decisions/` location) focusing on routing vs validation distinction
- **Related Files**:
  - `src/omnibase_infra/enums/enum_node_output_type.py`
  - `src/omnibase_infra/enums/enum_message_category.py`
  - `src/omnibase_infra/validation/validator_execution_shape.py`
  - `src/omnibase_infra/validation/validator_runtime_shape.py`
  - `src/omnibase_infra/models/validation/model_execution_shape_rule.py`
  - `src/omnibase_infra/runtime/service_message_dispatch_engine.py`
