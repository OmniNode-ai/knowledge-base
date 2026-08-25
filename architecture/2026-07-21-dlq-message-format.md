---
type: architecture
status: accepted
date: "2026-07-21"
title: "Dead Letter Queue (DLQ) Message Format"
topics: [omnibase-infra, dlq, message, format]
refs: []
---


# Dead Letter Queue (DLQ) Message Format

## Overview

The Dead Letter Queue (DLQ) is a critical component of ONEX's message processing infrastructure. When a message cannot be processed after exhausting all retry attempts, it is published to the DLQ for investigation, auditing, and potential reprocessing.

**Purpose**:
- **Error Isolation**: Prevent poison messages from blocking healthy message processing
- **Auditability**: Preserve complete context of failed messages for debugging
- **Recovery**: Enable manual or automated reprocessing after fixes are applied
- **Observability**: Provide visibility into system failures and error patterns

**Related Documentation**:
- Retry, Backoff, and Compensation Strategy
- Error Handling Patterns
- Error Recovery Patterns

---

## DLQ Topic Configuration

The DLQ topic is configured via `ModelKafkaEventBusConfig`:

```python
from omnibase_infra.event_bus.models.config import ModelKafkaEventBusConfig

config = ModelKafkaEventBusConfig(
    bootstrap_servers="kafka:9092",
    group_id="my-consumer-group",
    dead_letter_topic="my-service.dlq",  # Default: "{group_id}.dlq"
)
```

---

## DLQ Payload Schema

When a message is published to the DLQ, it contains the original message with comprehensive failure metadata.

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DLQPayload",
  "type": "object",
  "required": [
    "original_topic",
    "original_message",
    "failure_reason",
    "failure_timestamp",
    "correlation_id",
    "retry_count",
    "error_type"
  ],
  "properties": {
    "original_topic": {
      "type": "string",
      "description": "The Kafka topic from which the message originated"
    },
    "original_message": {
      "type": "object",
      "description": "The original message that failed processing",
      "properties": {
        "key": {
          "type": ["string", "null"],
          "description": "Original message key (UTF-8 decoded)"
        },
        "value": {
          "type": "string",
          "description": "Original message value (UTF-8 decoded)"
        },
        "offset": {
          "type": "integer",
          "description": "Kafka offset of the original message"
        },
        "partition": {
          "type": "integer",
          "description": "Kafka partition of the original message"
        }
      },
      "required": ["value", "offset", "partition"]
    },
    "failure_reason": {
      "type": "string",
      "description": "Human-readable error message describing the failure"
    },
    "failure_timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO-8601 timestamp when the failure occurred"
    },
    "correlation_id": {
      "type": "string",
      "format": "uuid",
      "description": "UUID for distributed tracing correlation"
    },
    "retry_count": {
      "type": "integer",
      "minimum": 0,
      "description": "Number of message-level retry attempts before DLQ"
    },
    "error_type": {
      "type": "string",
      "description": "Python exception class name (e.g., 'ValueError', 'InfraConnectionError')"
    }
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `original_topic` | string | The Kafka topic from which the failed message originated |
| `original_message.key` | string \| null | The original message key, UTF-8 decoded. Null if no key was present |
| `original_message.value` | string | The original message body, UTF-8 decoded |
| `original_message.offset` | integer | The Kafka offset of the original message for replay reference |
| `original_message.partition` | integer | The Kafka partition of the original message |
| `failure_reason` | string | Human-readable description of why processing failed |
| `failure_timestamp` | string (ISO-8601) | When the failure occurred and message was sent to DLQ |
| `correlation_id` | string (UUID) | Distributed tracing ID to correlate with logs and other events |
| `retry_count` | integer | Number of message-level retry attempts before DLQ routing |
| `error_type` | string | The Python exception class name for categorization |

---

## DLQ Headers Schema

DLQ messages include both standard ONEX event headers and DLQ-specific headers for routing and filtering.

### Standard Headers (from ModelEventHeaders)

These headers are present on all ONEX event bus messages:

| Header | Type | Description |
|--------|------|-------------|
| `content_type` | string | Always `"application/json"` for DLQ messages |
| `correlation_id` | string (UUID) | Same as payload `correlation_id` |
| `message_id` | string (UUID) | Unique identifier for this DLQ message |
| `timestamp` | string (ISO-8601) | When the DLQ message was created |
| `source` | string | Format: `"{environment}.{group}"` (e.g., `"dev.order-service"`) |
| `event_type` | string | Always `"dlq_message"` for DLQ entries |
| `schema_version` | string | Schema version (default: `"1.0.0"`) |
| `priority` | string | Message priority level |
| `retry_count` | string | Current retry count (as string) |
| `max_retries` | string | Maximum allowed retries (as string) |

### DLQ-Specific Headers

These additional headers are appended specifically for DLQ messages:

| Header | Type | Description |
|--------|------|-------------|
| `original_topic` | string | The topic where processing failed |
| `failure_reason` | string | Error message describing the failure |
| `failure_timestamp` | string (ISO-8601) | When the failure occurred |

**Note**: All header values are UTF-8 encoded bytes in Kafka.

---

## Example DLQ Message

### Payload

```json
{
  "original_topic": "dev.order-service.order.created.v1",
  "original_message": {
    "key": "order-12345",
    "value": "{\"order_id\": \"12345\", \"customer_id\": \"cust-789\", \"total\": 99.99}",
    "offset": 42,
    "partition": 3
  },
  "failure_reason": "Database connection timeout after 30s",
  "failure_timestamp": "2024-01-15T14:32:17.456789+00:00",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "retry_count": 3,
  "error_type": "InfraTimeoutError"
}
```

### Headers

```
content_type: application/json
correlation_id: 550e8400-e29b-41d4-a716-446655440000
message_id: 7c9e6679-7425-40de-944b-e07fc1f90ae7
timestamp: 2024-01-15T14:32:17.789012+00:00
source: dev.order-service
event_type: dlq_message
schema_version: 1.0.0
priority: normal
retry_count: 0
max_retries: 3
original_topic: dev.order-service.order.created.v1
failure_reason: Database connection timeout after 30s
failure_timestamp: 2024-01-15T14:32:17.456789+00:00
```

---

## DLQ Processing Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Message Processing Flow                       │
│                                                                   │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────────┐   │
│  │ Message │───>│ Handler  │───>│ Retry   │───>│ Exhausted? │   │
│  │ Consumed│    │ Attempt  │    │ Policy  │    │            │   │
│  └─────────┘    └──────────┘    └─────────┘    └────────────┘   │
│                       │                              │           │
│                       │ Success                      │ Yes       │
│                       ▼                              ▼           │
│                 ┌──────────┐                   ┌──────────┐     │
│                 │ Commit   │                   │ Publish  │     │
│                 │ Offset   │                   │ to DLQ   │     │
│                 └──────────┘                   └──────────┘     │
│                                                      │           │
│                                                      ▼           │
│                                               ┌──────────┐      │
│                                               │ Commit   │      │
│                                               │ Offset   │      │
│                                               └──────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Conditions for DLQ Routing

A message is routed to the DLQ when:

1. **Retry exhaustion**: `retry_count >= max_retries` (default: 3 retries)
2. **Handler exception**: The message handler raises an exception
3. **DLQ enabled**: `dead_letter_topic` is configured (non-empty string)

### Post-DLQ Behavior

- Original message offset is committed (message won't be redelivered)
- DLQ publish is "best effort" - failures are logged but don't crash consumer
- Processing continues with next message in partition

---

## Monitoring and Alerting

### Recommended Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `dlq_messages_total` | Counter | Total messages published to DLQ |
| `dlq_messages_by_error_type` | Counter | DLQ messages grouped by `error_type` |
| `dlq_messages_by_topic` | Counter | DLQ messages grouped by `original_topic` |
| `dlq_publish_failures_total` | Counter | Failed attempts to publish to DLQ |

### Alert Thresholds

| Condition | Severity | Recommended Action |
|-----------|----------|-------------------|
| DLQ rate > 1% of throughput | Warning | Investigate error patterns |
| DLQ rate > 5% of throughput | Critical | Immediate investigation required |
| Single error_type spike | Warning | Check specific handler/dependency |
| DLQ publish failures | Critical | Check Kafka connectivity |

### Log Patterns

DLQ events are logged with structured context:

```python
# Successful DLQ publish
logger.info(
    f"Published failed message to DLQ: {dlq_topic}",
    extra={
        "original_topic": original_topic,
        "dlq_topic": dlq_topic,
        "correlation_id": str(correlation_id),
        "error_type": error_type,
    },
)

# Failed DLQ publish
logger.exception(
    f"Failed to publish to DLQ topic {dlq_topic}",
    extra={
        "original_topic": original_topic,
        "dlq_topic": dlq_topic,
        "correlation_id": str(correlation_id),
        "dlq_error": str(dlq_error),
    },
)
```

---

## Reprocessing DLQ Messages

### Manual Reprocessing

```python
from omnibase_infra.event_bus import KafkaEventBus
import json

async def reprocess_dlq_message(dlq_message: dict) -> None:
    """Reprocess a message from the DLQ after fixing the root cause."""
    event_bus = KafkaEventBus(config)
    await event_bus.start()

    try:
        # Extract original message
        original_topic = dlq_message["original_topic"]
        original_value = dlq_message["original_message"]["value"]
        original_key = dlq_message["original_message"]["key"]

        # Republish to original topic
        await event_bus.publish_raw(
            topic=original_topic,
            value=original_value.encode("utf-8"),
            key=original_key.encode("utf-8") if original_key else None,
        )
    finally:
        await event_bus.stop()
```

### Automated Reprocessing (with caution)

For automated reprocessing, ensure:

1. **Root cause is fixed**: The underlying issue must be resolved
2. **Idempotency**: Handlers must handle duplicate processing safely
3. **Rate limiting**: Avoid overwhelming the system with reprocessed messages
4. **Monitoring**: Track reprocessed messages separately from fresh messages

---

## Security Considerations

### Sanitization

DLQ messages follow the ONEX error sanitization guidelines via `sanitize_error_message()`:

**Error Message Sanitization**:
The `failure_reason` field in both the DLQ payload and Kafka headers is automatically sanitized
before publishing. If the error message contains any of the following patterns, the entire
message is replaced with `"{ExceptionType}: [REDACTED - potentially sensitive data]"`:

- Credentials: `password`, `secret`, `token`, `api_key`, `bearer`, `credential`
- Connection strings: `postgres://`, `mongodb://`, `mysql://`, `redis://`
- Key material: `-----BEGIN`, `private_key`
- And other sensitive patterns (see `SENSITIVE_PATTERNS` in `utils/util_error_sanitization.py`)

**What IS sanitized in DLQ**:
- `failure_reason` field in payload (sanitized error message)
- `failure_reason` header in Kafka message
- `error_message` field in `ModelDlqEvent` (for callbacks)
- Log entries related to DLQ publishing

**What is NOT sanitized in DLQ**:
- `original_message.value` - The original message payload is preserved for debugging.
  If your messages contain sensitive data, ensure proper access control on DLQ topics.

**Sanitization Example**:
```json
{
  "failure_reason": "ConnectionError: [REDACTED - potentially sensitive data]",
  "error_type": "ConnectionError"
}
```

### Access Control

- DLQ topics should have restricted access (ACLs)
- Only authorized operators should consume from DLQ
- Consider encryption for sensitive message payloads
- Original message payloads in DLQ retain their original content

---

## Implementation Reference

The DLQ implementation is located in:

- **KafkaEventBus**: `src/omnibase_infra/event_bus/kafka_event_bus.py`
  - `_publish_to_dlq()` method
- **Error Sanitization**: `src/omnibase_infra/utils/util_error_sanitization.py`
  - `sanitize_error_message()` function
  - `SENSITIVE_PATTERNS` constant
- **ModelEventHeaders**: `src/omnibase_infra/event_bus/models/model_event_headers.py`
- **Configuration**: `src/omnibase_infra/event_bus/models/config/model_kafka_event_bus_config.py`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2025-01 | Added error message sanitization for DLQ payloads and headers |
| 1.0.0 | 2024-01 | Initial DLQ message format specification |
