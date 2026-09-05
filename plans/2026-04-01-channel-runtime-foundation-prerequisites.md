---
type: plan
status: active
date: "2026-04-01"
title: "Channel runtime foundation — core contracts and routing backbone"
topics: [contracts, runtime, channels, routing]
---

# OmniClaw MVP Part 1: Core Channel Runtime Foundation

**Goal**: This slice establishes the canonical runtime contracts and routing backbone required for production-quality channel adapters.
**Architecture**: Event-driven, contract-first. Normalized channel messages flow through Kafka. The orchestrator is channel-agnostic; adapters are thin bridges.
**Tech stack**: Python 3.12+, Pydantic v2, omnibase_core models, omniclaude hooks/topics, omniintelligence contract auto-wiring pattern.

---

## Out of Scope for This Part

- Real Discord or Slack adapters (Part 2)
- Attachment ingestion/extraction (MVP behavior is metadata-only)
- Rich outbound formatting (plain text only for MVP)
- Platform auth flows (Part 2)
- Retry and DLQ semantics for real external delivery (post-MVP)

---

## Already Completed (DO NOT re-implement)

- **Contract packages with auto-wiring** — topic auto-discovery in omniintelligence
- **Tiered responder chain**
- **Trust boundary enforcement**
- **Multi-bus topic resolution**
- **Resolution event ledger**

## In Progress (reference but don't block on)

- **Delegation pipeline**
- **Pattern intelligence role detection**

---

## Known Types Inventory

Existing types that OmniClaw must align with or extend:

| Type | Location | Relevance |
|------|----------|-----------|
| `EnumSupportChannel` | `omnibase_core/src/omnibase_core/enums/enum_support_channel.py` | Has EMAIL, CHAT, WEB. Must be extended or a new `EnumChannelType` created for the broader set (DISCORD, SLACK, TELEGRAM, etc.) |
| `ModelMessageEnvelope[T]` | `omnibase_core/src/omnibase_core/models/envelope/model_message_envelope.py` | Signed runtime envelope. Channel envelope payload will be wrapped in this for Kafka transport. |
| `ModelEventChannels` | `omnibase_core/src/omnibase_core/models/core/model_event_channels.py` | `subscribes_to` / `publishes_to` lists for node introspection. |
| `ModelStateEnvelope` | `omnibase_core/src/omnibase_core/models/state/model_state_envelope.py` | Frozen state persistence wrapper — pattern to follow for channel envelope. |
| `TopicBase` (StrEnum) | `omniclaude/src/omniclaude/hooks/topics.py` | 100+ canonical topic definitions. Channel topics must be added here. |
| `build_topic()` | Same file | Validates and returns canonical topic name. |
| Contract auto-wiring | `omniintelligence/src/omniintelligence/runtime/contract_topics.py` | `_discover_effect_node_packages()` scans `contract.yaml` for `event_bus_enabled: true` + `subscribe_topics`. Channel orchestrator will follow this pattern. |
| Contract package layout | `omniintelligence/docs/architecture/contract-package-spec.md` | Required structure: `contract.yaml` with `event_bus` section, node.py, handlers/, models/. |

---

## Task 1: Define EnumChannelType in omnibase_core

Create a new enum for OmniClaw channel types. `EnumSupportChannel` (EMAIL, CHAT, WEB) is a support-ticket classification — OmniClaw needs a messaging-platform enum.

> **Note**: This is the MVP subset of supported channels. WEB, API, CLI, WHATSAPP, TEAMS are intentionally deferred. The enum is extensible — new members can be added without breaking existing adapters.

### Files

- **New**: `omnibase_core/src/omnibase_core/enums/enum_channel_type.py`
- **Edit**: `omnibase_core/src/omnibase_core/enums/__init__.py` (add export)

### Steps (TDD)

1. **Test first**: Write `tests/unit/enums/test_enum_channel_type.py`
   - Assert all members exist: DISCORD, SLACK, TELEGRAM, EMAIL, SMS, MATRIX
   - Assert `str(EnumChannelType.DISCORD) == "discord"`
   - Assert enum is `StrEnum`-based (or `StrValueHelper, str, Enum` per codebase convention)
2. **Implement**: Create `EnumChannelType` following the `EnumSupportChannel` pattern:
   ```python
   @unique
   class EnumChannelType(StrValueHelper, str, Enum):
       DISCORD = "discord"
       SLACK = "slack"
       TELEGRAM = "telegram"
       EMAIL = "email"
       SMS = "sms"
       MATRIX = "matrix"
   ```
3. **Export**: Add to `enums/__init__.py`
4. **Verify**: `uv run pytest tests/unit/enums/test_enum_channel_type.py -v`

### Commit

```
feat(enums): add EnumChannelType for OmniClaw channel platforms [OMN-XXXX]
```

---

## Task 2: Define ModelChannelEnvelope in omnibase_core

Create a frozen Pydantic model that normalizes messages from any channel into a single schema. This is the core data contract that all channel adapters produce and the orchestrator consumes.

> **Metadata policy**: `metadata` is `dict[str, str]` as an intentional MVP simplification. Platform-specific nested data should be JSON-serialized into string values. This will be revisited if adapter implementations consistently need richer typing.

> **Correlation ID policy**: Adapters SHOULD pass through existing correlation/trace context when available. If the inbound message has no correlation context, the adapter generates a new UUID. The model's `default_factory` is a convenience, not the canonical source.

### Files

- **New**: `omnibase_core/src/omnibase_core/models/channel/__init__.py`
- **New**: `omnibase_core/src/omnibase_core/models/channel/model_channel_envelope.py`
- **New**: `omnibase_core/src/omnibase_core/models/channel/model_channel_attachment.py`

### Steps (TDD)

1. **Test first**: Write `tests/unit/models/channel/test_model_channel_envelope.py`
   - Assert frozen (assignment raises)
   - Assert required fields: `channel_id`, `channel_type`, `sender_id`, `message_text`, `message_id`, `timestamp`, `correlation_id`
   - Assert optional fields default correctly: `thread_id=None`, `attachments=[]`, `reply_to=None`, `metadata={}`
   - Assert `channel_type` accepts `EnumChannelType` values
   - Assert `extra="forbid"` rejects unknown fields
   - Assert round-trip serialization (`model_dump` / `model_validate`)
   - Assert `sender_display_name` defaults to `None` (not empty string)
   - Assert rejection or normalization of naive (timezone-unaware) datetimes in `timestamp`
2. **Implement `ModelChannelAttachment`**:
   ```python
   class ModelChannelAttachment(BaseModel):
       model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)
       filename: str
       content_type: str  # MIME type
       url: str | None = None
       size_bytes: int | None = None
   ```
3. **Implement `ModelChannelEnvelope`**:
   ```python
   class ModelChannelEnvelope(BaseModel):
       model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

       # Channel identification
       channel_id: str = Field(..., min_length=1, description="Platform-specific channel/room ID")
       channel_type: EnumChannelType

       # Sender
       sender_id: str = Field(..., min_length=1, description="Platform-specific user ID")
       sender_display_name: str | None = Field(default=None, description="Human-readable sender name")

       # Message content
       message_text: str = Field(..., description="Normalized plain-text message body")
       message_id: str = Field(..., min_length=1, description="Platform-specific message ID")
       thread_id: str | None = Field(default=None, description="Conversation/thread container ID (e.g., Discord thread, Slack thread)")
       attachments: list[ModelChannelAttachment] = Field(default_factory=list)

       # Routing
       timestamp: datetime = Field(..., description="Message timestamp (UTC, timezone-aware)")
       correlation_id: UUID = Field(default_factory=uuid4)
       metadata: dict[str, str] = Field(default_factory=dict, description="Platform-specific metadata (JSON-serialize nested values)")

       # Response routing
       reply_to: str | None = Field(default=None, description="Specific message ID to reply to (for quote-reply semantics)")
   ```

   **Field semantics**:
   - `thread_id` = conversation/thread container ID (e.g., Discord thread, Slack thread)
   - `reply_to` = specific message ID to reply to (for quote-reply semantics)

4. **Export**: Add `__init__.py` with `__all__`
5. **Verify**: `uv run pytest tests/unit/models/channel/ -v && uv run mypy src/omnibase_core/models/channel/`

### Commit

```
feat(models): add ModelChannelEnvelope for normalized channel messages [OMN-XXXX]
```

---

## Task 2b: Define ModelChannelReply in omnibase_core

Create a frozen Pydantic model for normalized outbound replies. This is the contract that the orchestrator produces and channel adapters consume for delivery.

### Files

- **New**: `omnibase_core/src/omnibase_core/models/channel/model_channel_reply.py`
- **Edit**: `omnibase_core/src/omnibase_core/models/channel/__init__.py` (add export)

### Steps (TDD)

1. **Test first**: Write `tests/unit/models/channel/test_model_channel_reply.py`
   - Assert frozen (assignment raises)
   - Assert required fields: `channel_id`, `channel_type`, `reply_text`, `correlation_id`
   - Assert optional fields default correctly: `reply_to=None`, `thread_id=None`, `attachments=[]`, `metadata={}`
   - Assert `extra="forbid"` rejects unknown fields
   - Assert round-trip serialization
2. **Implement `ModelChannelReply`**:
   ```python
   class ModelChannelReply(BaseModel):
       model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

       channel_id: str = Field(..., min_length=1, description="Target channel/room ID")
       channel_type: EnumChannelType
       reply_text: str = Field(..., description="Plain-text reply body")
       reply_to: str | None = Field(default=None, description="Specific message ID to reply to (quote-reply)")
       thread_id: str | None = Field(default=None, description="Conversation/thread container ID")
       correlation_id: UUID = Field(..., description="Correlation ID from the original envelope")
       attachments: list = Field(default_factory=list, description="Empty for MVP")
       metadata: dict[str, str] = Field(default_factory=dict)
   ```
3. **Export**: Add to `channel/__init__.py`
4. **Verify**: `uv run pytest tests/unit/models/channel/test_model_channel_reply.py -v`

### Commit

```
feat(models): add ModelChannelReply for normalized outbound replies [OMN-XXXX]
```

---

## Task 3: Define channel topics in omniclaude TopicBase enum

Add three new topics to the `TopicBase` StrEnum for OmniClaw channel message flow.

> **Topic repo ownership**: These topics are defined in omniclaude's TopicBase for MVP. If OmniClaw becomes a standalone product, channel topics should migrate to a platform-level topic registry (omnibase_core or omnibase_compat). This is acknowledged as temporary placement.

### Files

- **Edit**: `omniclaude/src/omniclaude/hooks/topics.py`

### Steps (TDD)

1. **Test first**: Write `tests/unit/hooks/test_channel_topics.py`
   - Assert `TopicBase.CHANNEL_MESSAGE_RECEIVED == "onex.cmd.omniclaw.channel-message-received.v1"`
   - Assert `TopicBase.CHANNEL_REPLY_REQUESTED == "onex.evt.omniclaw.channel-reply-requested.v1"`
   - Assert `TopicBase.CHANNEL_MESSAGE_PROCESSED == "onex.evt.omniclaw.channel-message-processed.v1"`
   - Assert `build_topic(TopicBase.CHANNEL_MESSAGE_RECEIVED)` returns the canonical name
2. **Implement**: Add a new section to `topics.py`:
   ```python
   # ==========================================================================
   # OmniClaw channel messaging topics (OMN-XXXX)
   # Inbound normalized messages from any channel adapter, outbound replies,
   # and processing observability.
   # ==========================================================================
   CHANNEL_MESSAGE_RECEIVED = "onex.cmd.omniclaw.channel-message-received.v1"
   """Inbound normalized message from any channel adapter. Payload: ModelChannelEnvelope."""

   CHANNEL_REPLY_REQUESTED = "onex.evt.omniclaw.channel-reply-requested.v1"
   """Outbound response to be dispatched to the originating channel adapter."""

   CHANNEL_MESSAGE_PROCESSED = "onex.evt.omniclaw.channel-message-processed.v1"
   """Observability event emitted after orchestrator processes a channel message,
   regardless of outcome. Indicates the message was handled (successfully, with error,
   or as no-op). Does NOT indicate the reply was delivered."""
   ```
3. **Verify**: `uv run pytest tests/unit/hooks/test_channel_topics.py -v`

### Commit

```
feat(topics): add OmniClaw channel messaging topics [OMN-XXXX]
```

---

## Task 4: Create channel orchestrator handler in omniclaude

This is the "assistant brain" — a handler that receives `channel-message-received` events, runs the message through the assistant pipeline (routing, delegation, context injection, response generation), and emits `channel-reply-requested`.

### Required routing inputs (from envelope)

The orchestrator extracts these fields for delegation pipeline routing:
- `message_text` — the user's message (delegation input)
- `sender_id` — identity context for trust boundary
- `channel_type` — channel-aware routing decisions
- `channel_id` — target for reply routing
- `thread_id` — conversation continuity context
- `correlation_id` — end-to-end tracing
- `metadata` — platform-specific context passed to delegation

### Expected handler output

`ModelChannelReply` with populated fields:
- `channel_id` — from envelope
- `channel_type` — from envelope
- `reply_text` — generated response from delegation pipeline
- `reply_to` — from envelope `message_id` (quote-reply to the original)
- `thread_id` — preserved from envelope (if present)
- `correlation_id` — preserved from envelope
- `attachments` — empty list (MVP)
- `metadata` — empty dict (MVP)

### Failure behavior

- **Delegation timeout**: emit error event on `CHANNEL_MESSAGE_PROCESSED` + empty `ModelChannelReply` with `reply_text=""` (adapter interprets as no-op)
- **Delegation failure** (exception): emit error event on `CHANNEL_MESSAGE_PROCESSED` + `ModelChannelReply` with `reply_text="I couldn't process that request."`
- **Empty response** (delegation returns blank): emit warning on `CHANNEL_MESSAGE_PROCESSED` + `ModelChannelReply` with `reply_text="I couldn't help with that."`

### Thread/reply semantics

- If the envelope has `thread_id`, the reply preserves it (response stays in the same thread)
- If the envelope has `reply_to`, the response references it (quote-reply to a specific message)

### Observability payload shape for CHANNEL_MESSAGE_PROCESSED

```python
{
    "correlation_id": str(envelope.correlation_id),
    "channel_type": envelope.channel_type.value,
    "channel_id": envelope.channel_id,
    "sender_id": envelope.sender_id,
    "outcome": "success" | "error" | "empty" | "timeout",
    "duration_ms": int,
    "error_detail": str | None,
}
```

### Files

- **New**: `omniclaude/src/omniclaude/nodes/node_channel_orchestrator/`
  - `__init__.py`
  - `contract.yaml`
  - `node.py`
  - `handlers/__init__.py`
  - `handlers/handler_channel_orchestrate.py`
  - `models/__init__.py`
  - `models/model_channel_orchestrator_input.py`
  - `models/model_channel_orchestrator_output.py`

### Steps (TDD)

1. **Test first**: Write `tests/unit/nodes/node_channel_orchestrator/test_handler_channel_orchestrate.py`
   - Given a `ModelChannelEnvelope` with `channel_type=DISCORD`, `message_text="hello"`, handler returns output with `reply_text` populated
   - Given a message with `thread_id`, handler preserves threading context in reply
   - Mock the delegation/routing layer — orchestrator should call through to it
   - Assert `CHANNEL_REPLY_REQUESTED` event is emitted in handler output
   - Assert `CHANNEL_MESSAGE_PROCESSED` observability event is emitted
   - Assert failure cases: delegation timeout, delegation error, empty response each produce the correct reply_text and observability outcome
2. **Write contract.yaml** (following the contract package pattern):
   ```yaml
   name: node_channel_orchestrator
   contract_name: node_channel_orchestrator
   node_name: node_channel_orchestrator
   contract_version: {major: 1, minor: 0, patch: 0}
   node_version: {major: 1, minor: 0, patch: 0}
   node_type: ORCHESTRATOR_GENERIC
   description: >
     Channel orchestrator — receives normalized messages from any channel adapter,
     routes through the assistant pipeline (delegation, context injection, response
     generation), and emits reply-requested events.
   event_bus:
     event_bus_enabled: true
     subscribe_topics:
       - "onex.cmd.omniclaw.channel-message-received.v1"
     publish_topics:
       - "onex.evt.omniclaw.channel-reply-requested.v1"
       - "onex.evt.omniclaw.channel-message-processed.v1"
   input_model:
     name: "ModelChannelOrchestratorInput"
     module: "omniclaude.nodes.node_channel_orchestrator.models"
   capabilities:
     - name: channel.orchestration
       description: Route channel messages through assistant pipeline
       version: 1.0.0
   downstream_effects:
     - node: NodeLocalLlmInferenceEffect
       capability: local_llm.inference
       description: LLM inference for response generation
   metadata:
     author: OmniNode Team
     license: MIT
     tags: [omniclaw, channel, orchestrator]
   ```
3. **Implement handler** (`handler_channel_orchestrate.py`):
   - Accept `ModelChannelEnvelope` as input
   - Extract `message_text`, `sender_id`, `channel_type` for routing context
   - Call the delegation/routing pipeline (same path as `UserPromptSubmit` hook but with channel context)
   - Build response with `reply_text`, `channel_id`, `channel_type`, `reply_to=message_id`
   - Return `ModelHandlerOutput` with events for `CHANNEL_REPLY_REQUESTED` and `CHANNEL_MESSAGE_PROCESSED`
   - Handle failure cases: delegation timeout, delegation exception, empty response (see failure behavior above)
4. **Implement node.py** (thin shell, <50 lines):
   ```python
   class NodeChannelOrchestrator(NodeOrchestrator):
       async def orchestrate(self, input_data):
           return await self._handler.handle(input_data)
   ```
5. **Verify**: `uv run pytest tests/unit/nodes/node_channel_orchestrator/ -v`

### Commit

```
feat(nodes): add channel orchestrator node for OmniClaw assistant brain [OMN-XXXX]
```

---

## Task 5: Create channel reply dispatcher handler

Handler that receives `channel-reply-requested` events, looks up the `channel_type` from the envelope, and routes to the appropriate channel adapter's outbound topic. This is the fan-out point from one generic reply event to N channel-specific outbound topics.

> **MATRIX topic**: MATRIX is present in `EnumChannelType` but has no outbound topic in this contract. This is intentional — the enum member is present for type completeness, but the adapter is not yet implemented in MVP dispatch. The dispatcher handles unknown/unmapped channel types by emitting an error event (no crash).

### Files

- **New**: `omniclaude/src/omniclaude/nodes/node_channel_reply_dispatcher/`
  - `__init__.py`
  - `contract.yaml`
  - `node.py`
  - `handlers/__init__.py`
  - `handlers/handler_dispatch_reply.py`

### Steps (TDD)

1. **Test first**: Write `tests/unit/nodes/node_channel_reply_dispatcher/test_handler_dispatch_reply.py`
   - Given reply with `channel_type=DISCORD`, handler routes to `onex.cmd.omniclaw.discord-outbound.v1`
   - Given reply with `channel_type=SLACK`, handler routes to `onex.cmd.omniclaw.slack-outbound.v1`
   - Given reply with `channel_type=MATRIX` (unmapped), handler emits error event (no crash)
   - Given reply with unknown `channel_type`, handler emits error event (no crash)
   - Assert routing table is declarative (dict lookup, not if/elif chain)
2. **Write contract.yaml**:
   ```yaml
   name: node_channel_reply_dispatcher
   contract_name: node_channel_reply_dispatcher
   node_name: node_channel_reply_dispatcher
   contract_version: {major: 1, minor: 0, patch: 0}
   node_version: {major: 1, minor: 0, patch: 0}
   node_type: EFFECT_GENERIC
   description: >
     Dispatches reply-requested events to channel-specific outbound topics
     based on channel_type. Fan-out from generic reply to N adapters.
     MATRIX is an enum member but has no outbound topic in MVP.
   event_bus:
     event_bus_enabled: true
     subscribe_topics:
       - "onex.evt.omniclaw.channel-reply-requested.v1"
     publish_topics:
       - "onex.cmd.omniclaw.discord-outbound.v1"
       - "onex.cmd.omniclaw.slack-outbound.v1"
       - "onex.cmd.omniclaw.telegram-outbound.v1"
       - "onex.cmd.omniclaw.email-outbound.v1"
       - "onex.cmd.omniclaw.sms-outbound.v1"
   input_model:
     name: "ModelChannelReply"
     module: "omnibase_core.models.channel"
   metadata:
     author: OmniNode Team
     license: MIT
     tags: [omniclaw, channel, dispatcher]
   ```
3. **Implement handler** — declarative routing table:
   ```python
   OUTBOUND_TOPIC_MAP: dict[EnumChannelType, str] = {
       EnumChannelType.DISCORD: "onex.cmd.omniclaw.discord-outbound.v1",
       EnumChannelType.SLACK: "onex.cmd.omniclaw.slack-outbound.v1",
       EnumChannelType.TELEGRAM: "onex.cmd.omniclaw.telegram-outbound.v1",
       EnumChannelType.EMAIL: "onex.cmd.omniclaw.email-outbound.v1",
       EnumChannelType.SMS: "onex.cmd.omniclaw.sms-outbound.v1",
       # MATRIX intentionally omitted — enum member present, adapter not yet implemented
   }
   ```
4. **Verify**: `uv run pytest tests/unit/nodes/node_channel_reply_dispatcher/ -v`

### Commit

```
feat(nodes): add channel reply dispatcher for OmniClaw fan-out routing [OMN-XXXX]
```

---

## Task 6: Write golden chain test for channel message flow

EventBusInmemory end-to-end test: publish `channel-message-received` -> orchestrator processes -> `channel-reply-requested` emitted -> dispatcher routes to channel-specific outbound topic. Proves the core loop without any real channel.

### Files

- **New**: `omniclaude/tests/integration/nodes/test_channel_golden_chain.py`

### Steps (TDD)

1. **Write the test**:
   - Create `EventBusInmemory` instance
   - Wire `NodeChannelOrchestrator` subscribed to `CHANNEL_MESSAGE_RECEIVED`
   - Wire `NodeChannelReplyDispatcher` subscribed to `CHANNEL_REPLY_REQUESTED`
   - Publish a `ModelChannelEnvelope` with `channel_type=DISCORD`, `message_text="What is ONEX?"`
   - Assert: `CHANNEL_REPLY_REQUESTED` event emitted with non-empty `reply_text`
   - Assert: `CHANNEL_MESSAGE_PROCESSED` observability event emitted
   - Assert: `onex.cmd.omniclaw.discord-outbound.v1` receives the routed reply
   - Assert: correlation_id is preserved end-to-end (same UUID across all events)
   - **Negative assertions**:
     - Assert the correct outbound topic (`discord-outbound`) receives the reply, not just "something was emitted"
     - Assert NO other channel outbound topics received the reply (e.g., `slack-outbound`, `telegram-outbound` got nothing)
     - Assert correlation_id matches across envelope -> reply -> outbound (not just "exists")
2. **Mark**: `@pytest.mark.integration` (requires EventBusInmemory, no external services)
3. **Verify**: `uv run pytest tests/integration/nodes/test_channel_golden_chain.py -v`

### Commit

```
test(integration): add golden chain test for OmniClaw channel message flow [OMN-XXXX]
```

---

## Architecture Diagram

```
                                    +-------------------+
                                    |  Channel Adapter  |
                                    |  (Discord, etc.)  |
                                    +---------+---------+
                                              | publishes
                                              v
                              onex.cmd.omniclaw.channel-message-received.v1
                                              |
                                              v
                              +----------------------------+
                              |  NodeChannelOrchestrator   |
                              |  (assistant brain)         |
                              |  - routing                 |
                              |  - delegation              |
                              |  - context injection       |
                              |  - response generation     |
                              +--------------+-------------+
                                             | emits
                                             v
                              onex.evt.omniclaw.channel-reply-requested.v1
                                             |
                                             v
                              +------------------------------+
                              |  NodeChannelReplyDispatcher  |
                              |  (fan-out by channel_type)   |
                              +--------------+---------------+
                                             | routes to
                       +---------------------+---------------------+
                       v                     v                     v
           discord-outbound.v1   slack-outbound.v1   telegram-outbound.v1
                       |                     |                     |
                       v                     v                     v
                  +---------+         +----------+          +-----------+
                  | Discord |         |  Slack   |          | Telegram  |
                  | Adapter |         | Adapter  |          |  Adapter  |
                  +---------+         +----------+          +-----------+
```

---

## Dependency Graph

```
Task 1 (EnumChannelType)
  +-- Task 2 (ModelChannelEnvelope) -- uses EnumChannelType
  |     +-- Task 2b (ModelChannelReply) -- uses EnumChannelType
  |           +-- Task 3 (TopicBase topics) -- independent but needed by Tasks 4-5
  |                 +-- Task 4 (Channel Orchestrator) -- consumes ModelChannelEnvelope + topics
  |                 +-- Task 5 (Reply Dispatcher) -- consumes ModelChannelReply + topics
  |                       +-- Task 6 (Golden Chain Test) -- wires Tasks 4 + 5
```

Tasks 1-3 can be parallelized (Task 2 depends on Task 1 only for the enum import). Task 2b can parallel with Task 2 (same enum dependency). Tasks 4 and 5 can be parallelized after Tasks 1-3 complete. Task 6 requires all prior tasks.

---

## Contract Boundaries Introduced in This Part

| Contract | Type | Description |
|----------|------|-------------|
| `EnumChannelType` | Enum | Canonical channel taxonomy for MVP-supported adapters (DISCORD, SLACK, TELEGRAM, EMAIL, SMS, MATRIX) |
| `ModelChannelEnvelope` | Pydantic model | Normalized inbound message contract — produced by channel adapters, consumed by orchestrator |
| `ModelChannelReply` | Pydantic model | Normalized outbound reply contract — produced by orchestrator, consumed by channel adapters |
| `TopicBase.CHANNEL_MESSAGE_RECEIVED` | Topic | Canonical inbound topic (`onex.cmd.omniclaw.channel-message-received.v1`) |
| `TopicBase.CHANNEL_REPLY_REQUESTED` | Topic | Canonical reply topic (`onex.evt.omniclaw.channel-reply-requested.v1`) |
| `TopicBase.CHANNEL_MESSAGE_PROCESSED` | Topic | Observability completion topic (`onex.evt.omniclaw.channel-message-processed.v1`) |
| Channel-specific outbound topics | Topics | Adapter fan-out targets: `discord-outbound.v1`, `slack-outbound.v1`, `telegram-outbound.v1`, `email-outbound.v1`, `sms-outbound.v1` |

---

routing: plan-to-tickets + epic-team
