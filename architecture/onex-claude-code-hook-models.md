---
type: architecture
status: accepted
date: "2026-09-02"
title: "Claude Code Hooks Architecture"
topics:
  - omnibase-core
  - claude
  - code
  - hook
  - models
refs: []
---

<!-- Migrated from omnibase_core:docs/architecture/CLAUDE_CODE_HOOKS.md on 2026-09-02 -->

# Claude Code Hooks Architecture

**Why in core?** These hook models are part of the shared contract surface used by multiple repos (omnimemory, omniintelligence, etc.). They define the canonical event types for Claude Code integration.

---

## Hook Event Types

| Event | Purpose | Category |
|-------|---------|----------|
| `SESSION_START` | Session initialization | Lifecycle |
| `USER_PROMPT_SUBMIT` | Prompt submission | Lifecycle |
| `PRE_TOOL_USE` | Before tool execution | Agentic Loop |
| `POST_TOOL_USE` | After tool execution | Agentic Loop |
| `SUBAGENT_START/STOP` | Subagent lifecycle | Agentic Loop |
| `STOP` | Session stopping | Lifecycle |

---

## Hook Event Model

```python
class ModelClaudeCodeHookEvent(BaseModel):
    event_type: EnumClaudeCodeHookEventType
    session_id: str
    correlation_id: UUID | None
    timestamp_utc: datetime  # Must be timezone-aware
    payload: ModelClaudeCodeHookEventPayload
```

---

## Lifecycle Flow

```
SessionStart → UserPromptSubmit → [PreToolUse → PostToolUse]* → Stop → SessionEnd
```

---

## Key Files

| Purpose | Location |
|---------|----------|
| Hook event type enum | `src/omnibase_core/enums/hooks/enum_claude_code_hook_event_type.py` |
| Hook event model | `src/omnibase_core/models/hooks/model_claude_code_hook_event.py` |
| Hook payload model | `src/omnibase_core/models/hooks/model_claude_code_hook_event_payload.py` |

---

## Related Documentation

- ONEX Four-Node Architecture
- Canonical Execution Shapes
