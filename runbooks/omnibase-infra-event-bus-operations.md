---
type: runbook
status: current
date: "2026-09-02"
title: "Event Bus Operations Runbook"
topics: [omnibase-infra, event, bus, operations]
refs: []
---

<!-- Migrated from omnibase_infra:docs/operations/EVENT_BUS_OPERATIONS_RUNBOOK.md on 2026-09-02. -->

# Event Bus Operations Runbook

Operational guide for deploying, configuring, monitoring, and troubleshooting the EventBusKafka in production environments.

## Overview

The EventBusKafka provides production-grade message streaming using Apache Kafka with built-in resilience patterns:

- **Topic-based routing** with Kafka partitioning
- **Circuit breaker** for connection failure protection
- **Retry with exponential backoff** on publish failures
- **Dead letter queue (DLQ)** for failed message processing
- **Resilience** against transient broker failures (per platform-wide rule #8: Kafka is required infrastructure)

**Source Location**: `src/omnibase_infra/event_bus/event_bus_kafka.py`

## Pre-Deployment Checklist

### Kafka Cluster Requirements

- [ ] Kafka cluster version 2.6+ deployed and healthy
- [ ] Bootstrap servers accessible from application network
- [ ] Required topics created with appropriate partitioning
- [ ] Topic ACLs configured for producer/consumer access
- [ ] Replication factor set for fault tolerance (minimum 3 for production)
- [ ] Dead letter queue topic created (if DLQ enabled)

### Network Requirements

- [ ] Firewall rules allow traffic to Kafka brokers
- [ ] DNS resolution working for broker hostnames
- [ ] Network latency to brokers < 50ms (recommended)
- [ ] SSL/TLS certificates installed (if using secure transport)

### Application Requirements

- [ ] Environment variables configured (see Configuration section)
- [ ] Sufficient memory allocated for producer/consumer buffers
- [ ] Logging configured for operational visibility
- [ ] Health check endpoints exposed for monitoring

## Service Ports Reference

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Kafka Broker (plaintext) | 9092 | TCP | Unencrypted Kafka traffic |
| Kafka Broker (SSL) | 9093 | TCP | TLS-encrypted Kafka traffic |
| Event Bus Service | 8083 | HTTP | Event bus API endpoint |

## Environment Configuration

All configuration is managed through environment variables with sensible defaults.

### Connection Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | - | Comma-separated broker addresses. **Must be overridden** — per rule #7 localhost defaults are for local development only; per rule #8 Kafka is required infrastructure. |
| `KAFKA_ENVIRONMENT` | `local` | - | Environment identifier (e.g., `dev`, `staging`, `prod`) |
| `KAFKA_GROUP` | `default` | - | Consumer group identifier |

### Timeout and Retry Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KAFKA_TIMEOUT_SECONDS` | `30` | 1-300 | Operation timeout in seconds |
| `KAFKA_MAX_RETRY_ATTEMPTS` | `3` | 0-10 | Maximum publish retry attempts |
| `KAFKA_RETRY_BACKOFF_BASE` | `1.0` | 0.1-60.0 | Base delay for exponential backoff |

### Circuit Breaker Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KAFKA_CIRCUIT_BREAKER_THRESHOLD` | `5` | 1-100 | Failures before circuit opens |
| `KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT` | `30.0` | 1.0-3600.0 | Seconds before auto-reset attempt |

### Consumer Settings

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `KAFKA_CONSUMER_SLEEP_INTERVAL` | `0.1` | 0.01-10.0 | Poll interval in seconds |
| `KAFKA_AUTO_OFFSET_RESET` | `latest` | `earliest`, `latest` | Offset reset policy |
| `KAFKA_ENABLE_AUTO_COMMIT` | `true` | `true`, `false` | Auto-commit offsets |

### Producer Settings

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `KAFKA_ACKS` | `all` | `all`, `1`, `0` | Acknowledgment policy |
| `KAFKA_ENABLE_IDEMPOTENCE` | `true` | `true`, `false` | Enable exactly-once semantics |

### Dead Letter Queue Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_DEAD_LETTER_TOPIC` | None | Topic for failed messages (DLQ disabled if not set) |

### Example Configuration

```bash
# Production configuration
export KAFKA_BOOTSTRAP_SERVERS="kafka1:9092,kafka2:9092,kafka3:9092"
export KAFKA_ENVIRONMENT="prod"
export KAFKA_GROUP="my-service"
export KAFKA_TIMEOUT_SECONDS=60
export KAFKA_MAX_RETRY_ATTEMPTS=5
export KAFKA_CIRCUIT_BREAKER_THRESHOLD=10
export KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT=60.0
export KAFKA_DEAD_LETTER_TOPIC="dlq-events"
export KAFKA_ACKS="all"
export KAFKA_ENABLE_IDEMPOTENCE="true"
```

### YAML Configuration

Configuration can also be loaded from YAML files:

```yaml
# kafka_config.yaml
bootstrap_servers: "kafka1:9092,kafka2:9092,kafka3:9092"
environment: "prod"
group: "my-service"
timeout_seconds: 60
max_retry_attempts: 5
retry_backoff_base: 2.0
circuit_breaker_threshold: 10
circuit_breaker_reset_timeout: 60.0
acks: "all"
enable_idempotence: true
auto_offset_reset: "latest"
enable_auto_commit: true
dead_letter_topic: "dlq-events"
```

```python
from pathlib import Path
from omnibase_infra.event_bus.event_bus_kafka import EventBusKafka

bus = EventBusKafka.from_yaml(Path("/etc/kafka/config.yaml"))
```

## Health Check Endpoints

### Health Check Response

The `health_check()` method returns comprehensive status information:

```python
health = await bus.health_check()
# {
#     "healthy": True,
#     "started": True,
#     "environment": "prod",
#     "group": "my-service",
#     "bootstrap_servers": "kafka1:9092,kafka2:9092,kafka3:9092",
#     "circuit_state": "closed",
#     "subscriber_count": 15,
#     "topic_count": 5,
#     "consumer_count": 5
# }
```

### Key Health Indicators

| Field | Healthy Value | Description |
|-------|---------------|-------------|
| `healthy` | `true` | Overall health status |
| `started` | `true` | Event bus has started |
| `circuit_state` | `closed` | Circuit breaker state |
| `subscriber_count` | > 0 | Active subscriptions |
| `consumer_count` | = topic_count | Active consumers per topic |

### HTTP Health Endpoint Example

```python
from fastapi import FastAPI
from omnibase_infra.event_bus.event_bus_kafka import EventBusKafka

app = FastAPI()
bus = EventBusKafka.default()

@app.get("/health/event-bus")
async def event_bus_health():
    """Event bus health check endpoint."""
    health = await bus.health_check()
    status_code = 200 if health["healthy"] else 503
    return JSONResponse(content=health, status_code=status_code)

@app.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    health = await bus.health_check()
    if health["healthy"] and health["started"]:
        return {"status": "ready"}
    return JSONResponse({"status": "not_ready"}, status_code=503)
```

## Circuit Breaker Monitoring

### Circuit Breaker States

```
CLOSED ──(failures >= threshold)──> OPEN
   ^                                   │
   │                                   │ (timeout elapsed)
   │                                   v
   └──(success)─────────────────── HALF_OPEN
```

| State | Behavior | Monitoring Action |
|-------|----------|-------------------|
| `closed` | Normal operation | No action required |
| `half_open` | Testing recovery | Monitor closely, potential instability |
| `open` | Blocking requests | **ALERT**: Investigate root cause |

### Monitoring Metrics

```python
from prometheus_client import Gauge, Counter

# Circuit breaker state gauge (0=closed, 1=half_open, 2=open)
circuit_breaker_state = Gauge(
    "kafka_event_bus_circuit_state",
    "Circuit breaker state",
    ["environment", "group"]
)

# Request counters
kafka_requests_total = Counter(
    "kafka_event_bus_requests_total",
    "Total Kafka requests",
    ["environment", "topic", "result"]  # result: success, failure, rejected
)

async def collect_circuit_metrics(bus: EventBusKafka):
    """Collect circuit breaker metrics."""
    health = await bus.health_check()
    state_value = {"closed": 0, "half_open": 1, "open": 2}
    circuit_breaker_state.labels(
        environment=health["environment"],
        group=health["group"]
    ).set(state_value.get(health["circuit_state"], 2))
```

### Tuning Circuit Breaker

| Scenario | Threshold | Reset Timeout | Rationale |
|----------|-----------|---------------|-----------|
| **High reliability** | 3 | 60s | Fast failure detection, longer recovery |
| **High throughput** | 10 | 30s | Tolerant of transient failures |
| **Bursty traffic** | 5 | 45s | Balanced approach |
| **External dependency** | 15 | 120s | More tolerance for external service issues |

```bash
# High reliability configuration
export KAFKA_CIRCUIT_BREAKER_THRESHOLD=3
export KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT=60.0

# High throughput configuration
export KAFKA_CIRCUIT_BREAKER_THRESHOLD=10
export KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT=30.0
```

## Dead Letter Queue (DLQ) Handling

### DLQ Message Format

Failed messages are published to the DLQ with comprehensive metadata:

```json
{
    "original_topic": "events.user.created",
    "original_message": {
        "key": "user-123",
        "value": "{\"user_id\": \"123\", \"email\": \"<contact-address>\"}",
        "offset": "12345",
        "partition": 2
    },
    "failure_reason": "Handler timeout after 30 seconds",
    "failure_timestamp": "2025-01-15T10:30:00.000Z",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "retry_count": 3,
    "error_type": "InfraTimeoutError"
}
```

### DLQ Headers

| Header | Description |
|--------|-------------|
| `original_topic` | Topic where message was consumed |
| `failure_reason` | Error message |
| `failure_timestamp` | When failure occurred (ISO-8601) |
| `correlation_id` | Request tracking ID |

### DLQ Processing Strategy

```python
from omnibase_infra.event_bus.event_bus_kafka import EventBusKafka

bus = EventBusKafka.default()

async def process_dlq_message(msg):
    """Process dead letter queue messages."""
    import json
    payload = json.loads(msg.value.decode("utf-8"))

    # Log for investigation
    logger.error(
        "DLQ message received",
        extra={
            "original_topic": payload["original_topic"],
            "failure_reason": payload["failure_reason"],
            "correlation_id": payload["correlation_id"],
            "error_type": payload["error_type"],
        }
    )

    # Optionally retry or alert
    if payload["retry_count"] < 5:
        # Re-publish to original topic for retry
        await bus.publish(
            topic=payload["original_topic"],
            key=payload["original_message"]["key"].encode(),
            value=payload["original_message"]["value"].encode(),
        )
    else:
        # Send alert for manual investigation
        await send_alert(payload)

# Subscribe to DLQ
await bus.subscribe("dlq-events", "dlq-processor", process_dlq_message)
```

### DLQ Monitoring Commands

```bash
# Count messages in DLQ topic
kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 \
    --topic dlq-events \
    --from-beginning \
    --timeout-ms 5000 2>/dev/null | wc -l

# View DLQ messages
kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 \
    --topic dlq-events \
    --from-beginning \
    --max-messages 10 \
    --property print.headers=true \
    --property print.timestamp=true
```

## Troubleshooting Guide

### Connection Issues

**Symptom**: `InfraConnectionError: Failed to connect to Kafka`

**Diagnosis**:
```bash
# Test broker connectivity
nc -zv kafka1 9092
nc -zv kafka2 9092
nc -zv kafka3 9092

# Check DNS resolution
nslookup kafka1
nslookup kafka2

# Check Kafka cluster health
kafka-broker-api-versions.sh --bootstrap-server kafka:9092
```

**Resolution**:
1. Verify network connectivity to all brokers
2. Check firewall rules for port 9092/9093
3. Confirm bootstrap servers configuration is correct
4. Verify Kafka cluster is running and healthy
5. Check for SSL/TLS certificate issues if using encrypted transport

### Timeout Errors

**Symptom**: `InfraTimeoutError: Timeout connecting to Kafka after 30s`

**Diagnosis**:
```bash
# Check network latency
ping kafka1
ping kafka2

# Check broker load
kafka-consumer-groups.sh --bootstrap-server kafka:9092 --describe --all-groups

# Check for slow consumers
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group my-service.default \
    --describe
```

**Resolution**:
1. Increase `KAFKA_TIMEOUT_SECONDS` if network latency is high
2. Check broker resource utilization (CPU, memory, disk I/O)
3. Verify no network congestion between application and brokers
4. Consider increasing Kafka broker resources

### Circuit Breaker Open

**Symptom**: `InfraUnavailableError: Circuit breaker is OPEN`

**Diagnosis**:
```python
health = await bus.health_check()
if health["circuit_state"] == "open":
    print(f"Circuit opened due to consecutive failures")
    print(f"Will reset in {KAFKA_CIRCUIT_BREAKER_RESET_TIMEOUT} seconds")
```

**Resolution**:
1. Check Kafka cluster health
2. Review application logs for failure patterns
3. Temporarily increase `KAFKA_CIRCUIT_BREAKER_THRESHOLD` if transient issues
4. Wait for circuit to transition to `half_open` for recovery test
5. If persistent, investigate underlying Kafka or network issues

### High Retry Count

**Symptom**: Many publish retries, increased latency

**Diagnosis**:
```bash
# Check for these log patterns
grep "Retrying Kafka operation" /var/log/application.log | wc -l
grep "Publish error" /var/log/application.log | tail -20
```

**Resolution**:
1. Check Kafka broker health and replication status
2. Verify network stability
3. Tune retry settings:
   ```bash
   export KAFKA_MAX_RETRY_ATTEMPTS=5
   export KAFKA_RETRY_BACKOFF_BASE=2.0
   ```
4. Consider adding more Kafka brokers for capacity

### Consumer Lag

**Symptom**: Messages processing slowly, growing backlog

**Diagnosis**:
```bash
# Check consumer group lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --describe

# Output shows LAG column - high numbers indicate backlog
```

**Resolution**:
1. Scale consumer instances horizontally
2. Increase topic partition count for parallelism
3. Optimize message handler performance
4. Reduce `KAFKA_CONSUMER_SLEEP_INTERVAL` for faster polling

### Memory Issues

**Symptom**: OOM errors, high memory usage

**Diagnosis**:
```bash
# Check process memory
ps aux | grep python
cat /proc/<pid>/status | grep -E 'VmRSS|VmSize'
```

**Resolution**:
1. Reduce concurrent subscriptions if possible
2. Configure message batching at producer level
3. Increase container memory limits
4. Review message size - consider compression

## Common Operational Tasks

### Topic Management

```bash
# Create a new topic
kafka-topics.sh --bootstrap-server kafka:9092 \
    --create \
    --topic events.user.created \
    --partitions 6 \
    --replication-factor 3

# List all topics
kafka-topics.sh --bootstrap-server kafka:9092 --list

# Describe topic configuration
kafka-topics.sh --bootstrap-server kafka:9092 \
    --describe \
    --topic events.user.created

# Increase partitions (cannot decrease)
kafka-topics.sh --bootstrap-server kafka:9092 \
    --alter \
    --topic events.user.created \
    --partitions 12

# Delete a topic
kafka-topics.sh --bootstrap-server kafka:9092 \
    --delete \
    --topic events.user.created
```

### Consumer Group Management

```bash
# List all consumer groups
kafka-consumer-groups.sh --bootstrap-server kafka:9092 --list

# Describe consumer group with lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --describe

# Reset consumer offsets to earliest (requires group to be inactive)
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --topic events.user.created \
    --reset-offsets \
    --to-earliest \
    --execute

# Reset to specific offset
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --topic events.user.created \
    --reset-offsets \
    --to-offset 1000 \
    --execute

# Reset to specific timestamp
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --topic events.user.created \
    --reset-offsets \
    --to-datetime 2025-01-15T00:00:00.000 \
    --execute

# Delete consumer group (must be inactive)
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --delete \
    --group prod.my-service
```

### Message Inspection

```bash
# Consume messages from beginning (for debugging)
kafka-console-consumer.sh --bootstrap-server kafka:9092 \
    --topic events.user.created \
    --from-beginning \
    --max-messages 10 \
    --property print.key=true \
    --property print.headers=true \
    --property print.timestamp=true

# Consume from specific offset
kafka-console-consumer.sh --bootstrap-server kafka:9092 \
    --topic events.user.created \
    --partition 0 \
    --offset 1000 \
    --max-messages 10

# Produce test message
echo '{"test": "message"}' | kafka-console-producer.sh \
    --bootstrap-server kafka:9092 \
    --topic events.test
```

### Graceful Shutdown

```python
import signal
import asyncio

bus = EventBusKafka.default()

async def graceful_shutdown():
    """Gracefully shutdown event bus."""
    logger.info("Initiating graceful shutdown...")

    # Stop accepting new messages
    await bus.close()

    logger.info("Event bus shutdown complete")

def handle_sigterm(signum, frame):
    """Handle SIGTERM for container shutdown."""
    asyncio.create_task(graceful_shutdown())

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)
```

## Scaling Considerations

### Horizontal Scaling

| Component | Scaling Strategy | Notes |
|-----------|------------------|-------|
| Producers | Scale freely | Each instance connects independently |
| Consumers | Scale to partition count | Max consumers = partitions |
| Topics | Increase partitions | Cannot decrease after creation |

### Partition Planning

```
Recommended Partitions = Max(Expected Consumer Instances, Expected Peak Messages/sec / 1000)
```

Example:
- 10 consumer instances planned
- 50,000 messages/second peak
- Partitions = max(10, 50000/1000) = max(10, 50) = **50 partitions**

### Consumer Group Scaling

```bash
# Check current consumer distribution
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --describe --members

# Partitions are rebalanced when consumers join/leave
```

### Resource Sizing

| Traffic Level | Memory | CPU | Timeout | Circuit Threshold |
|---------------|--------|-----|---------|-------------------|
| Low (<1k msg/s) | 256Mi | 250m | 30s | 5 |
| Medium (1-10k msg/s) | 512Mi | 500m | 45s | 8 |
| High (10-100k msg/s) | 1Gi | 1000m | 60s | 10 |
| Very High (>100k msg/s) | 2Gi | 2000m | 90s | 15 |

## Disaster Recovery

### Backup Procedures

```bash
# Export topic configuration
kafka-topics.sh --bootstrap-server kafka:9092 \
    --describe \
    --topic events.user.created > topic_config.txt

# Export consumer group offsets
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --describe > consumer_offsets.txt
```

### Recovery Procedures

**Scenario 1: Consumer Group Reset**
```bash
# Stop all consumers
kubectl scale deployment my-service --replicas=0

# Reset offsets to recover from corruption
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
    --group prod.my-service \
    --topic events.user.created \
    --reset-offsets \
    --to-earliest \
    --execute

# Restart consumers
kubectl scale deployment my-service --replicas=3
```

**Scenario 2: Topic Recreation**
```bash
# Delete corrupted topic
kafka-topics.sh --bootstrap-server kafka:9092 \
    --delete \
    --topic events.user.created

# Recreate with same configuration
kafka-topics.sh --bootstrap-server kafka:9092 \
    --create \
    --topic events.user.created \
    --partitions 6 \
    --replication-factor 3 \
    --config retention.ms=604800000
```

**Scenario 3: Kafka Cluster Recovery**
1. Restore Kafka cluster from backup
2. Verify all brokers are healthy
3. Check topic replication status
4. Restart application consumers
5. Monitor for message loss or duplication

### Circuit Breaker Manual Reset

In extreme cases, the circuit breaker can be manually reset:

```python
# Access internal state (for emergency use only)
async with bus._circuit_breaker_lock:
    bus._circuit_breaker_open = False
    bus._circuit_breaker_failures = 0
    bus._circuit_breaker_open_until = 0.0

logger.warning("Circuit breaker manually reset - monitor closely")
```

## Performance Tuning

### Producer Tuning

| Parameter | Default | High Throughput | Low Latency |
|-----------|---------|-----------------|-------------|
| `acks` | `all` | `1` | `1` |
| `enable_idempotence` | `true` | `false` (if acks=1) | `true` |
| `timeout_seconds` | `30` | `60` | `10` |
| `max_retry_attempts` | `3` | `5` | `2` |

### Consumer Tuning

| Parameter | Default | High Throughput | Low Latency |
|-----------|---------|-----------------|-------------|
| `consumer_sleep_interval` | `0.1` | `0.01` | `0.05` |
| `auto_offset_reset` | `latest` | `latest` | `latest` |
| `enable_auto_commit` | `true` | `false` (manual) | `true` |

### Backoff Tuning

Exponential backoff formula: `delay = base * (2^attempt) * jitter`

| Scenario | Base | Max Attempts | Result |
|----------|------|--------------|--------|
| Fast fail | `0.5` | `2` | 0.5s, 1s |
| Balanced | `1.0` | `3` | 1s, 2s, 4s |
| Resilient | `2.0` | `5` | 2s, 4s, 8s, 16s, 32s |

## Production Deployment Checklist

### Pre-Deployment

- [ ] Environment variables configured for target environment
- [ ] Kafka cluster accessible and healthy
- [ ] Required topics created with appropriate partitions
- [ ] Dead letter queue topic created (if enabled)
- [ ] Health check endpoints exposed
- [ ] Monitoring and alerting configured
- [ ] Resource limits set in container configuration
- [ ] Graceful shutdown handlers implemented

### Post-Deployment

- [ ] Verify `health_check()` returns healthy status
- [ ] Confirm circuit breaker in `closed` state
- [ ] Check consumer groups created and consuming
- [ ] Monitor for error logs in first 15 minutes
- [ ] Validate end-to-end message flow
- [ ] Check DLQ topic for any failures

### Rollback Criteria

- Circuit breaker opens within 5 minutes of deployment
- Error rate exceeds 5%
- Consumer lag growing continuously
- Health check failing
- Memory usage exceeding limits

## Related Documentation

- Thread Pool Tuning Runbook (internal knowledge base)
- Circuit Breaker Implementation
- Error Recovery Patterns
- EventBusKafka Source (`../../src/omnibase_infra/event_bus/event_bus_kafka.py`)
- Configuration Model (`../../src/omnibase_infra/event_bus/models/config/model_kafka_event_bus_config.py`)
