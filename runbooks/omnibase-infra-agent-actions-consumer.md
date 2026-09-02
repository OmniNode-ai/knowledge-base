---
type: runbook
status: current
date: "2026-09-02"
title: "Agent Actions Consumer - Operational Runbook"
topics: [omnibase-infra, agent, actions, consumer]
refs: []
---

<!-- Migrated from omnibase_infra:src/omnibase_infra/services/observability/agent_actions/RUNBOOK.md on 2026-09-02. -->

# Agent Actions Consumer - Operational Runbook

## Overview

The Agent Actions Consumer is an async Kafka consumer that ingests agent
observability events from 7 topics and persists them to PostgreSQL. It
runs as a standalone service (`omninode-agent-actions-consumer`) on port
8087 (health check).

## Architecture

```
Kafka (7 topics) --> AgentActionsConsumer --> WriterAgentActionsPostgres --> PostgreSQL
                         |                           |
                    Health Check :8087         Circuit Breaker
                         |
                    DLQ Producer --> DLQ Topic
```

## Health Check

**Endpoint**: `GET http://localhost:8087/health`

**Response codes**:
- `200` - HEALTHY
- `503` - DEGRADED or UNHEALTHY

**Status meanings**:
- **HEALTHY**: Consumer running, circuit closed, recent successful writes
- **DEGRADED**: Consumer running but circuit open/half-open, or stale polls/writes
- **UNHEALTHY**: Consumer stopped or crashed

## Circuit Breaker Recovery

### Symptoms
- Health check returns `503` with `circuit_breaker_state: "open"`
- Logs show repeated `InfraConnectionError` or `InfraTimeoutError`

### Recovery Steps

1. **Check PostgreSQL connectivity**:
   ```bash
   psql -h localhost -p 5436 -U postgres -d omnibase_infra -c "SELECT 1"
   ```

2. **Check circuit breaker state**:
   ```bash
   curl -s http://localhost:8087/health | jq '.circuit_breaker_state'
   ```

3. **Wait for auto-recovery**: The circuit breaker auto-resets after
   `circuit_breaker_reset_timeout` seconds (default: 60s). It enters
   half-open state, allowing one request through. On success, it closes.

4. **If database is unreachable**: Fix the database issue. The consumer
   will auto-recover once the circuit half-opens and a write succeeds.

5. **Force restart** (last resort):
   ```bash
   docker restart omninode-agent-actions-consumer
   ```

## Dead Letter Queue (DLQ)

Messages that permanently fail (JSON decode errors, validation errors) are
forwarded to the DLQ topic: `onex.evt.omniclaude.agent-actions-dlq.v1`.

### Inspecting DLQ messages

```bash
# List DLQ messages
kcat -C -b localhost:19092 \
  -t onex.evt.omniclaude.agent-actions-dlq.v1 \
  -c 10 -e | jq .
```

Each DLQ message contains:
- `source_topic`: Original topic
- `source_partition`: Original partition
- `source_offset`: Original offset
- `error_reason`: Why the message failed
- `original_value`: The raw message content
- `timestamp`: When it was sent to DLQ
- `consumer_id`: Which consumer instance processed it

### Replaying DLQ messages

After fixing the root cause (e.g., schema mismatch), messages can be
replayed by producing them back to the original topic.

## Verifying Data Flow

### Check recent writes

```sql
-- Recent agent actions (last 5 minutes)
SELECT COUNT(*), action_type
FROM agent_actions
WHERE created_at > NOW() - INTERVAL '5 minutes'
GROUP BY action_type
ORDER BY count DESC;

-- Recent routing decisions
SELECT COUNT(*), selected_agent
FROM agent_routing_decisions
WHERE created_at > NOW() - INTERVAL '5 minutes'
GROUP BY selected_agent
ORDER BY count DESC;

-- Check all tables have recent data
SELECT 'agent_actions' AS table_name, MAX(created_at) AS latest FROM agent_actions
UNION ALL
SELECT 'agent_routing_decisions', MAX(created_at) FROM agent_routing_decisions
UNION ALL
SELECT 'agent_transformation_events', MAX(created_at) FROM agent_transformation_events
UNION ALL
SELECT 'router_performance_metrics', MAX(created_at) FROM router_performance_metrics
UNION ALL
SELECT 'agent_detection_failures', MAX(created_at) FROM agent_detection_failures
UNION ALL
SELECT 'agent_execution_logs', MAX(updated_at) FROM agent_execution_logs
UNION ALL
SELECT 'agent_status_events', MAX(created_at) FROM agent_status_events;
```

### Check consumer lag

```bash
# Via Redpanda Console
open http://localhost:8080

# Via rpk
docker exec omnibase-infra-redpanda rpk group describe agent-observability-postgres
```

### Check consumer metrics

```bash
curl -s http://localhost:8087/health | jq '{
  messages_processed,
  messages_failed,
  batches_processed,
  circuit_breaker_state
}'
```

## Topic Normalization Strategy

Five legacy bare topic names were migrated to ONEX canonical format in
an earlier normalization pass:

| Legacy Name | ONEX Canonical Name |
|---|---|
| `agent-actions` | `onex.evt.omniclaude.agent-actions.v1` |
| `agent-routing-decisions` | `onex.evt.omniclaude.routing-decision.v1` |
| `agent-transformation-events` | `onex.evt.omniclaude.agent-transformation.v1` |
| `router-performance-metrics` | `onex.evt.omniclaude.performance-metrics.v1` |
| `agent-detection-failures` | `onex.evt.omniclaude.detection-failure.v1` |

Two topics are unchanged:
- `agent-execution-logs` - Producer name unconfirmed, monitored via per-topic counter
- `onex.evt.agent.status.v1` - Not omniclaude-produced

## TTL Cleanup

The TTL cleanup service runs every 10 minutes (configurable) and deletes
rows older than 30 days (configurable). It uses batched DELETEs (1000 rows
per batch) to avoid lock contention.

### Check cleanup status

```bash
# Via health endpoint (if integrated)
curl -s http://localhost:8087/health | jq '.ttl_cleanup'

# Via database
SELECT COUNT(*) AS old_rows, 'agent_actions' AS table_name
FROM agent_actions
WHERE created_at < NOW() - INTERVAL '30 days'
UNION ALL
SELECT COUNT(*), 'agent_execution_logs'
FROM agent_execution_logs
WHERE updated_at < NOW() - INTERVAL '30 days';
```

## Configuration

All configuration is via environment variables with the
`OMNIBASE_INFRA_AGENT_ACTIONS_` prefix. Key settings:

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Kafka bootstrap servers |
| `POSTGRES_DSN` | (required) | PostgreSQL connection string |
| `BATCH_SIZE` | `100` | Max records per batch |
| `BATCH_TIMEOUT_MS` | `1000` | Batch accumulation timeout |
| `HEALTH_CHECK_HOST` | `127.0.0.1` | Health check bind address |
| `HEALTH_CHECK_PORT` | `8087` | Health check port |
| `DLQ_ENABLED` | `true` | Enable dead letter queue |
| `DLQ_TOPIC` | `onex.evt.omniclaude.agent-actions-dlq.v1` | DLQ topic name |
| `MAX_RETRY_COUNT` | `3` | Max retries before DLQ |

For container deployments, override `HEALTH_CHECK_HOST` to `0.0.0.0`.
