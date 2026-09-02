---
type: runbook
status: current
date: "2026-09-02"
title: "Dead Letter Queue (DLQ) Replay Guide"
topics: [omnibase-infra, dlq, replay]
refs: []
---

<!-- Migrated from omnibase_infra:docs/operations/DLQ_REPLAY_RUNBOOK.md on 2026-09-02. -->

# Dead Letter Queue (DLQ) Replay Guide

## Overview

The DLQ Replay utility allows operators to reprocess failed messages from the Dead Letter Queue back to their original topics. This is useful after fixing the root cause of failures (e.g., database connectivity restored, bug fixed, etc.).

**Script Location**: `scripts/dlq_replay.py`

**Related Documentation**:
- DLQ Message Format - Message schema and headers
- Retry, Backoff, and Compensation Strategy
- Error Handling Patterns

---

## Prerequisites

### Environment Variables

**Required**:
```bash
# Kafka connection (REQUIRED - no default for security)
export KAFKA_BOOTSTRAP_SERVERS="<infrastructure-host>:19092"
```

**Optional (for PostgreSQL tracking)**:
```bash
# PostgreSQL tracking configuration (required if --enable-tracking is used)
# Use the role configured in your OMNIBASE_INFRA_DB_URL (see .env.example).
export OMNIBASE_INFRA_DB_URL="postgresql://role_omnibase_infra:your_password@<infrastructure-host>:5436/omnibase_infra"
```

### Network Access

- Kafka/Redpanda broker must be accessible
- If using `--enable-tracking`, PostgreSQL must be accessible

---

## Commands

### list - View DLQ Messages

List messages currently in the DLQ with their replay eligibility status:

```bash
# List first 100 messages (default)
python scripts/dlq_replay.py list --dlq-topic dlq-events

# List with increased limit
python scripts/dlq_replay.py list --dlq-topic dlq-events --limit 500

# List with filters (see Filtering section below)
python scripts/dlq_replay.py list --dlq-topic dlq-events --filter-topic dev.orders
```

**Output**:
```
================================================================================
DLQ Messages from: dlq-events
================================================================================

[1] 550e8400-e29b-41d4-a716-446655440000
    Topic:     dev.order-service.order.created.v1
    Error:     InfraTimeoutError
    Reason:    Database connection timeout after 30s
    Timestamp: 2025-01-15T14:32:17.456789+00:00
    Retries:   3
    Status:    ELIGIBLE

[2] 7c9e6679-7425-40de-944b-e07fc1f90ae7
    Topic:     dev.user-service.user.registered.v1
    Error:     ValidationError
    Reason:    Invalid email format
    Timestamp: 2025-01-15T14:35:22.123456+00:00
    Retries:   1
    Status:    SKIP: Non-retryable error type: ValidationError

Total messages listed: 2
```

### replay - Replay Messages

Replay eligible messages back to their original topics:

```bash
# Dry run - see what would be replayed without publishing
python scripts/dlq_replay.py replay --dlq-topic dlq-events --dry-run

# Replay all eligible messages
python scripts/dlq_replay.py replay --dlq-topic dlq-events

# Replay with rate limiting (default: 100 msg/sec)
python scripts/dlq_replay.py replay --dlq-topic dlq-events --rate-limit 50

# Replay with message limit
python scripts/dlq_replay.py replay --dlq-topic dlq-events --limit 100

# Replay with PostgreSQL tracking
python scripts/dlq_replay.py replay --dlq-topic dlq-events --enable-tracking
```

**Output**:
```
================================================================================
Replay Summary
================================================================================
Total processed: 150
  Completed:     120
  Skipped:       25
  Failed:        5
  Tracking:      enabled
```

### stats - View DLQ Statistics

Show aggregated statistics about DLQ contents:

```bash
python scripts/dlq_replay.py stats --dlq-topic dlq-events
```

**Output**:
```
================================================================================
DLQ Statistics: dlq-events
================================================================================

Total messages: 250

By Original Topic:
  dev.order-service.order.created.v1: 100
  dev.user-service.user.registered.v1: 85
  dev.payment-service.payment.processed.v1: 65

By Error Type:
  InfraTimeoutError: 120
  InfraConnectionError: 80
  ValidationError: 30
  InfraUnavailableError: 20

By Retry Count:
  0 retries: 50
  1 retries: 75
  2 retries: 60
  3 retries: 65
```

---

## Filtering Options

All filter options can be used with `list` and `replay` commands.

### Filter by Topic

Replay only messages from a specific original topic:

```bash
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-topic dev.order-service.order.created.v1
```

### Filter by Error Type

Replay only messages with a specific error type:

```bash
# Replay only connection errors (likely fixed by restoring connectivity)
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-error-type InfraConnectionError

# Replay only timeout errors
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-error-type InfraTimeoutError
```

### Filter by Correlation ID

Replay a specific message by its correlation ID:

```bash
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-correlation-id 550e8400-e29b-41d4-a716-446655440000
```

### Time-Range Filtering

Filter messages by their failure timestamp using ISO 8601 format:

```bash
# Replay messages from the last 24 hours
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --start-time 2025-01-25T00:00:00Z

# Replay messages up to a specific time
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --end-time 2025-01-15T23:59:59Z

# Replay messages within a specific time window
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --start-time 2025-01-01T00:00:00Z \
    --end-time 2025-01-15T23:59:59Z

# Combine time filter with topic filter
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-topic dev.orders \
    --start-time 2025-01-01T00:00:00Z

# Combine time filter with error type filter
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-error-type InfraConnectionError \
    --start-time 2025-01-20T00:00:00Z \
    --end-time 2025-01-21T00:00:00Z
```

**Time Format Notes**:
- Use ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DDTHH:MM:SS+00:00`
- The `Z` suffix indicates UTC timezone
- If no timezone is specified, UTC is assumed
- Time filters are orthogonal to other filters and can be combined with `--filter-topic`, `--filter-error-type`, or `--filter-correlation-id`

---

## PostgreSQL Replay Tracking

Enable PostgreSQL-based tracking to persist replay attempt history for auditing and analysis.

### Configuration

Set the required environment variable:

```bash
# Use the per-service role matching your OMNIBASE_INFRA_DB_URL configuration.
export OMNIBASE_INFRA_DB_URL="postgresql://role_omnibase_infra:your_password@<infrastructure-host>:5436/omnibase_infra"
```

### Usage

```bash
# Enable tracking for a replay operation
python scripts/dlq_replay.py replay --dlq-topic dlq-events --enable-tracking

# Combine with dry-run (tracking still records what would be replayed)
python scripts/dlq_replay.py replay --dlq-topic dlq-events --enable-tracking --dry-run
```

### What Gets Tracked

Each replay attempt records:
- Original message correlation ID
- New replay correlation ID
- Original and target topics
- Replay status (COMPLETED, FAILED, SKIPPED)
- Timestamp
- Error message (if failed)
- DLQ offset and partition
- Retry count

### Querying Replay History

```sql
-- View recent replay attempts
SELECT * FROM dlq_replay_history
ORDER BY replay_timestamp DESC
LIMIT 100;

-- Count replays by status
SELECT replay_status, COUNT(*)
FROM dlq_replay_history
GROUP BY replay_status;

-- Find failed replays for a specific topic
SELECT * FROM dlq_replay_history
WHERE original_topic LIKE '%order%'
  AND success = false
ORDER BY replay_timestamp DESC;
```

---

## Replay Headers

Replayed messages include tracking headers to identify them:

| Header | Description |
|--------|-------------|
| `x-replay-count` | Total number of replay attempts |
| `x-replayed-at` | ISO 8601 timestamp of replay |
| `x-replayed-by` | Always `dlq_replay_script` |
| `x-original-dlq-offset` | DLQ offset for traceability |
| `x-replay-correlation-id` | New correlation ID for this replay |
| `correlation_id` | Original message correlation ID (preserved) |

---

## Non-Retryable Error Types

The following error types are automatically skipped during replay as they represent permanent failures:

| Error Type | Description |
|------------|-------------|
| `ValidationError` | Message schema/content validation failure |
| `AuthorizationError` | Insufficient permissions |
| `NotFoundError` | Required resource does not exist |
| `ConflictError` | State conflict (e.g., duplicate key) |
| `ParseError` | Malformed message content |
| `SchemaError` | Schema mismatch or incompatibility |
| `InvalidConfigurationError` | Configuration errors |

Messages with these error types require manual investigation and data correction before replay.

---

## Safety Controls

### Max Replay Count

Prevents infinite replay loops by limiting total replay attempts per message:

```bash
# Default: 5 maximum replays
python scripts/dlq_replay.py replay --dlq-topic dlq-events

# Increase limit for specific scenarios
python scripts/dlq_replay.py replay --dlq-topic dlq-events --max-replay-count 10
```

### Rate Limiting

Controls replay throughput to avoid overwhelming downstream systems:

```bash
# Default: 100 messages/second
python scripts/dlq_replay.py replay --dlq-topic dlq-events

# Reduce rate for sensitive systems
python scripts/dlq_replay.py replay --dlq-topic dlq-events --rate-limit 10

# Increase rate for batch processing
python scripts/dlq_replay.py replay --dlq-topic dlq-events --rate-limit 500
```

### Message Limit

Limit the number of messages processed in a single run:

```bash
# Replay only first 50 eligible messages
python scripts/dlq_replay.py replay --dlq-topic dlq-events --limit 50
```

### Dry Run

Always preview what would be replayed before actual execution:

```bash
python scripts/dlq_replay.py replay --dlq-topic dlq-events --dry-run
```

---

## Operational Workflows

### Post-Incident Replay

After resolving an infrastructure issue (e.g., database restored):

```bash
# 1. View statistics to understand the scope
python scripts/dlq_replay.py stats --dlq-topic dlq-events

# 2. Preview what would be replayed (dry run)
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-error-type InfraConnectionError \
    --dry-run

# 3. Replay with tracking enabled
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-error-type InfraConnectionError \
    --enable-tracking \
    --rate-limit 50
```

### Time-Bounded Replay

Replay messages from a specific incident window:

```bash
# Incident occurred between 10:00 and 11:00 UTC on 2025-01-20
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --start-time 2025-01-20T10:00:00Z \
    --end-time 2025-01-20T11:00:00Z \
    --enable-tracking
```

### Single Message Replay

Replay a specific message after manual verification:

```bash
python scripts/dlq_replay.py replay --dlq-topic dlq-events \
    --filter-correlation-id 550e8400-e29b-41d4-a716-446655440000 \
    --enable-tracking
```

---

## Troubleshooting

### Cannot Connect to Kafka

```
Error: Could not connect to Kafka at ...
```

**Resolution**:
1. Verify `KAFKA_BOOTSTRAP_SERVERS` environment variable is set
2. Check network connectivity to the broker
3. Ensure Kafka/Redpanda is running

### Tracking Service Failed to Initialize

```
WARNING: Failed to initialize tracking service: ...
```

**Resolution**:
1. Verify `OMNIBASE_INFRA_DB_URL` environment variable is set
2. Check PostgreSQL connectivity
3. Ensure database schema includes `dlq_replay_history` table

### Invalid Time Format

```
Error: Invalid start_time format: ...
```

**Resolution**:
Use ISO 8601 format: `2025-01-01T00:00:00Z`

---

## Related Tickets


---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2025-01 | Added time-range filtering (`--start-time`, `--end-time`) |
| 1.1.0 | 2025-01 | Added PostgreSQL replay tracking (`--enable-tracking`) |
| 1.0.0 | 2024-12 | Initial DLQ replay utility |
