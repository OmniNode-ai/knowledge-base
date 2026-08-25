---
type: adr
status: accepted
date: "2025-12-15"
title: "ADR-0036: Context Mutability Design Decision"
adr_id: ADR-0036
topics: [omnibase_core, pydantic, immutability, workflow-state, fsm-snapshots]
refs: [adrs/ADR-0030-protocol-based-di-architecture.md]
supersedes: []
superseded_by: []
---

# ADR-0036: Context Mutability Design Decision

**Status**: Implemented
**Date**: 2025-12-15
**Source**: omnibase_core `docs/decisions/ADR-007-context-mutability-design-decision.md`

> Originally numbered ADR-002 in omnibase_core's pre-consolidation `docs/architecture/decisions/`
> tree; renumbered ADR-007 during consolidation into `docs/decisions/` to avoid a collision
> with the field-limit-constants decision ([ADR-0031](ADR-0031-centralized-field-limit-constants.md)).

---

## Context

Workflow and FSM state snapshots must be serializable and restorable for replay/debugging,
persistence across restarts, testing, and cross-service communication. These snapshots
contain a `context` field storing flexible runtime state as `dict[str, Any]`. Python's
`dict` is fundamentally mutable — even with Pydantic `frozen=True`, field *reassignment* is
blocked but the dict's *contents* remain mutable (`snapshot.context["key"] = "value"` still
works).

Four options were considered: `types.MappingProxyType`, recursive deep-freeze, a
convention-based approach (document the contract, trust developers), and a custom immutable
dict type.

## Decision

**Convention-Based Immutability** with comprehensive documentation for context fields in
state snapshot models — `ModelWorkflowStateSnapshot` and `ModelFSMStateSnapshot`.

### Core Principles

1. **Contractual immutability**: context MUST NOT be mutated after snapshot creation (documented, not enforced).
2. **Defensive programming**: helper methods for safe snapshot updates (e.g. `with_step_completed()`).
3. **Deep-copy guidance**: documented pattern for isolated copies where needed.
4. **PII awareness**: sanitization utilities for safe logging/persistence.

### Implementation Pattern

```python
class ModelWorkflowStateSnapshot(BaseModel):
    """
    Immutability Contract:
        - Guaranteed immutable: workflow_id (UUID), current_step_index (int), etc.
        - Contractually immutable: context (dict) — contents can be modified but MUST NOT be
        - Field reassignment is blocked by frozen=True
        - Workflow executors MUST create new snapshots rather than mutating existing ones
    """
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)
    context: dict[str, Any] = Field(default_factory=dict)

    def with_step_completed(self, step_id: UUID, *, new_context: dict | None = None):
        """Create new snapshot with updated state — preserves immutability contract."""
        updated_context = {**self.context, **(new_context or {})}
        return ModelWorkflowStateSnapshot(
            workflow_id=self.workflow_id,
            current_step_index=self.current_step_index + 1,
            completed_step_ids=(*self.completed_step_ids, step_id),
            context=updated_context,  # New dict, not mutation
        )
```

## Rationale — Why Not the Alternatives

- **`MappingProxyType`**: not JSON-serializable by default, requires custom validators, only protects the top-level dict (nested dicts remain mutable), API friction.
- **Deep Freeze**: performance overhead on every snapshot creation, needs frozen versions of list/dict/set, third-party-code compatibility issues, overkill given most context usage is read-only after creation.
- **Custom Immutable Dict**: maintenance burden covering all dict operations, ecosystem friction with type checkers/tools, still doesn't solve nested mutability.
- **Convention-Based (chosen)**: simple, performant, compatible with JSON serializers/Pydantic/pytest-xdist, relies on developer discipline and code review rather than runtime enforcement.

## Consequences

**Positive**: simplicity, no defensive-copy/proxy overhead, full ecosystem compatibility, testability.

**Negative**: no runtime enforcement of the contract — accidental mutation won't raise;
mutation bugs may be subtle. Mitigated by comprehensive docstrings, the `with_step_completed()` /
`with_step_failed()` helper methods, a `sanitize_context_for_logging()` PII helper, a
`validate_context_size()` size guard, and a documented `copy.deepcopy()` pattern for callers
that need an isolated copy.

### Thread Safety

Safe: passing snapshots between threads for read-only access; serializing via `model_dump()`.
Unsafe: mutating context contents (violates the contract *and* causes race conditions).

---

## References

- [ADR-0030](ADR-0030-protocol-based-di-architecture.md): Protocol-Based Dependency Injection Architecture
- `src/omnibase_core/models/workflow/execution/model_workflow_state_snapshot.py` — primary implementation (verified live: `with_step_completed` present, `frozen=True` on `ModelWorkflowStateSnapshot`)
- `src/omnibase_core/models/fsm/model_fsm_state_snapshot.py`
- [Pydantic Frozen Models](https://docs.pydantic.dev/latest/concepts/models/#model-configuration)
- [Python `MappingProxyType`](https://docs.python.org/3/library/types.html#types.MappingProxyType)

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base. Verified live: both model files exist at their stated paths, `with_step_completed` is defined, and `ModelWorkflowStateSnapshot` is declared with `frozen=True`. No drift found. |
| 2025-12-15 | Initial decision |
