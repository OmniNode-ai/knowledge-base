---
type: adr
status: accepted
date: "2026-01-12"
title: "ADR-0035: Status Taxonomy and Categorical Organization"
adr_id: ADR-0035
topics: [omnibase_core, enums, status-taxonomy, type-system, governance]
refs: []
supersedes: []
superseded_by: []
---

# ADR-0035: Status Taxonomy and Categorical Organization

**Status**: Accepted
**Date**: 2026-01-12 (updated 2026-02-14)
**Source**: omnibase_core `docs/decisions/ADR-006-status-taxonomy.md`

> This decision record absorbed and supersedes an earlier "ADR-013" (Status Taxonomy —
> Canonical Enums) inside omnibase_core, per that repo's own decision index. Any reference
> to ADR-013 in other documents should be redirected here.

---

## Executive Summary

Establishes a formal taxonomy for the 57+ status-related enums in omnibase_core, organizing
them into semantic categories with canonical representatives. Gates future consolidation
work and provides clear guidance on when to use each status category.

## Problem Statement

57+ status-related enums evolved organically, creating ambiguity (which enum for a given
use case?), redundancy (overlapping semantics), inconsistency (similar concepts, different
value sets), and cognitive load.

## Decision

### Six Primary Status Categories

| Category | Purpose | Canonical Enum | Location |
|----------|---------|----------------|----------|
| **Execution** | Task/node execution lifecycle | `EnumExecutionStatus` | `src/omnibase_core/enums/enum_execution_status.py` |
| **Operation** | Service operation outcomes | `EnumOperationStatus` | `src/omnibase_core/enums/enum_operation_status.py` |
| **Workflow** | Multi-step workflow progression | `EnumWorkflowStatus` | `src/omnibase_core/enums/enum_workflow_status.py` |
| **Health** | System/service health state | `EnumHealthStatus` | `src/omnibase_core/enums/enum_health_status.py` |
| **Lifecycle** | Entity maturity/availability | `EnumLifecycle` | `src/omnibase_core/enums/enum_metadata.py` |
| **Registration** | Registry entry states | `EnumRegistryEntryStatus` | `src/omnibase_core/enums/enum_registry_entry_status.py` |

### Three Severity Categories

| Category | Canonical Enum | Status | Location |
|----------|----------------|--------|----------|
| Issue Severity | `EnumSeverity` | Canonical | `src/omnibase_core/enums/enum_severity.py` |
| Log Severity | `EnumSeverityLevel` (RFC 5424) | Keep Separate | `src/omnibase_core/enums/enum_severity_level.py` |
| Business Impact | `EnumImpactSeverity` | Keep Separate | `src/omnibase_core/enums/enum_impact_severity.py` |

**Key distinction**: `EnumSeverity` is general-purpose severity classification for issues,
violations, findings, and diagnostic messages (6-level scale: DEBUG, INFO, WARNING, ERROR,
CRITICAL, FATAL). `EnumSeverityLevel` is RFC 5424-compliant logging levels (11 values incl.
TRACE, NOTICE, ALERT, EMERGENCY) for logging infrastructure requiring numeric ordering.
`EnumImpactSeverity` is business-impact classification (CRITICAL, HIGH, MEDIUM, LOW,
MINIMAL). Calling `logger.warning()`/`logger.info()` uses Python's logging module directly —
not any of these enums.

### Category Values (summary)

- **`EnumExecutionStatus`**: PENDING, RUNNING, COMPLETED, SUCCESS, FAILED, SKIPPED,
  CANCELLED, TIMEOUT, PARTIAL.
- **`EnumOperationStatus`**: SUCCESS, FAILED, IN_PROGRESS, CANCELLED, PENDING, TIMEOUT.
  Distinction from Execution: Operation is for discrete atomic operations; Execution is for
  longer-running tasks with richer lifecycle tracking.
- **`EnumWorkflowStatus`**: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, SIMULATED.
- **`EnumHealthStatus`**: HEALTHY, DEGRADED, UNHEALTHY, CRITICAL, UNKNOWN, WARNING,
  UNREACHABLE, AVAILABLE, UNAVAILABLE, ERROR.
- **`EnumLifecycle`**: DRAFT, ACTIVE, DEPRECATED, ARCHIVED.
- **`EnumRegistryEntryStatus`**: EPHEMERAL, ONLINE, VALIDATED.

### Selecting the Right Category

```text
Question                                          -> Category
"Has the task/node finished executing?"           -> Execution
"Did the API call succeed?"                       -> Operation
"Where is the workflow in its process?"           -> Workflow
"Is the service healthy?"                         -> Health
"Is this feature production-ready?"               -> Lifecycle
"Is this node registered in the discovery?"       -> Registration
"How severe is this code violation?"              -> Issue Severity
"What log level should this message have?"        -> Log Severity
"What is the business impact of this change?"     -> Business Impact
```

## Scope Limitations

This decision explicitly does **not** cover: FSM transition rules (valid state transitions
are deferred to a future decision), a cross-category root enum (no unified `StatusBase` is
established — each category stays independent), consolidation implementation (merging
redundant enums is tracked separately), or formal cross-category mapping rules.

## Consequences

**Positive**: clear, authoritative taxonomy; foundation for future consolidation; reduced
"which enum?" ambiguity.

**Negative**: `checker_enum_governance.py` (`src/omnibase_core/validation/checker_enum_governance.py`)
enforces this taxonomy in pre-commit but, as of authoring, ran in **warning mode** (`|| true`)
— reporting violations without blocking builds, pending existing-violation cleanup before it
becomes blocking. This status was not re-verified during the 2026-08-25 migration; treat as
historical unless independently reconfirmed.

---

## References

- All nine enum locations verified live against omnibase_core@dev during the 2026-08-25 migration (no drift found).

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-08-25 | Migrated to knowledge base. All enum file-path claims re-verified live; no corrections needed. |
| 2026-02-14 | Supersession note added: prior "ADR-013" merged into this document |
| 2026-01-14 | Enhanced severity enum documentation |
| 2026-01-12 | Initial taxonomy proposal |
