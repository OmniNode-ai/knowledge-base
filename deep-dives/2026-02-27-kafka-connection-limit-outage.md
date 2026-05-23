---
type: deep-dive
status: public-curated
date: 2026-02-27
title: "Kafka Connection Limit Outage: TCP Socket Leak Under Reconnect Storms"
period: "2026-02-27"
topics:
  - kafka
  - resilience
  - event-bus
  - connection-management
refs:
  - adr/ADR-006-event-bus-abstraction.md
---

# 2026-02-27: Kafka Connection Limit Outage — TCP Socket Leak Under Reconnect Storms

## Summary

A multi-hour P1 outage caused by a TCP socket leak in the Kafka client library revealed a critical architectural gap: the platform had no explicit reconnect backoff policy, leaving every consumer and producer at the mercy of a 50ms default that turned a brief broker unavailability into a full connection exhaustion event. Resolution required a complete data volume wipe to clear corrupted broker connection state. The incident drove mandatory reconnect backoff configuration and session-bound lifecycle management for long-lived consumer processes.

## Core Work

The ONEX platform runs all inter-service communication through a Kafka-compatible event bus. At the time of the incident, the event bus layer used `aiokafka` for both producers and consumers without explicit reconnect configuration. A brief broker unavailability triggered the default reconnect behavior: each `AIOKafkaProducer` and `AIOKafkaConsumer` instance entered a tight retry loop capped at 50ms per attempt. Each attempt opened a new TCP socket. Old sockets in `TIME_WAIT` or `CLOSE_WAIT` state were not cleaned up before the next attempt.

With multiple processes running concurrently — an event publisher, a dashboard consumer, and five runtime containers — the socket creation rate reached approximately 20 new connections per second per process. The broker's internal connection counter hit its limit within roughly 60 seconds of the initial unavailability.

## Architectural Pressure

Three compounding forces converged:

**Default reconnect policy was not production-safe.** The `aiokafka` default of `reconnect_backoff_max_ms=50` was chosen for low-latency reconnection in stable environments. Under broker unavailability, it became a socket amplifier. No documentation or configuration example in the codebase warned about this behavior.

**Broker connection counter corruption survived restarts.** The broker's internal connection counter did not properly decrement when connections were abruptly killed. The corrupted counter state persisted across container restarts. Multiple forced restarts failed to clear it. At the memory limit configured for the broker in development mode, the computed maximum connection count effectively reached zero — rejecting all new connections from all clients including localhost.

**Long-lived consumer processes accumulated socket state.** The event publisher had been running continuously for over three days without any session-bound lifecycle management. Long-lived processes that have accumulated socket state are significantly more likely to trigger this failure mode on any transient broker disruption, because they hold more TIME_WAIT sockets that compete with new connection attempts.

The only recovery path was a full broker data volume wipe. All topic offsets and message history were lost. Topics were auto-recreated on runtime restart.

## Discoveries

**Reconnect storms require explicit backoff floors.** The 50ms default creates a 20x/second socket creation rate. A 30-second maximum backoff reduces this to at most 1 attempt per 30 seconds — a 600x reduction in socket pressure. This should be a required configuration for any long-lived Kafka client in a system that may experience transient broker unavailability.

**Broker connection counter corruption is not self-healing.** The assumption that a broker container restart clears all transient state was wrong. Internal bookkeeping state that tracks connection counts can corrupt across restarts when connections are abruptly terminated. The safe recovery path requires a full data volume wipe, not just a container restart. This was not documented and cost significant diagnosis time.

**Event publisher lifecycle must be session-scoped.** A publisher that runs indefinitely accumulates socket state and becomes a liability. Binding publisher lifetime to session lifetime (start on session open, stop on session end) both reduces steady-state socket accumulation and makes failure modes more predictable.

**Silent connection exhaustion is difficult to detect.** The broker stopped accepting connections without emitting visible application errors on the client side. Clients logged reconnect attempts but not connection count exhaustion at the broker. The diagnostic path required checking broker-side metrics directly.

## Decisions Made

**Mandatory reconnect backoff configuration.** Both producers and consumers must configure `reconnect_backoff_ms=1000` (1 second initial) and `reconnect_backoff_max_ms=30000` (30 seconds maximum). The 50ms default is not permitted in production configuration.

**Session-bound publisher lifecycle.** Long-lived event publishers must be terminated on session end. The session end hook was updated to send SIGTERM to any running publisher process via a PID file.

**Explicit broker connection limit.** The broker's maximum connection count was pinned explicitly in the compose configuration rather than computed from available memory. Memory-derived limits proved non-deterministic and reset to near-zero after repeated container restarts.

**Runbook for connection exhaustion.** A documented recovery runbook was written covering: diagnosis (count active connections, identify leaking processes), mitigation (stop all consumers, wait for TIME_WAIT drain), and recovery (try non-nuclear restart first, fall back to data volume wipe only if restart fails).

## Candidate ADRs

- Kafka reconnect policy must be explicitly configured with bounded backoff — no implicit defaults for production consumers or producers
- Broker data volume wipe as documented recovery step for connection counter corruption

## Candidate Pivots

This incident was not a pivot point for the platform architecture — the event bus abstraction remained correct. The lessons were operational: reconnect configuration is infrastructure policy, not application code, and must be enforced at a platform level rather than left to individual service implementations.

## Related Doctrine

- **Section 8 (Fail-Fast on Configuration Gaps):** The absence of explicit backoff configuration should have been detectable before the incident. Platform-level validation of required client configuration would have caught the 50ms default.
- **Section 4 (Deterministic Recovery Paths):** The discovery that container restarts do not clear broker connection state violated the assumption that service restarts produce clean state. Recovery procedures must account for persistent state that survives restart.

## Related Evidence

- TCP connection count diagnostics: `netstat -an | grep "BROKER_PORT.*ESTABLISHED" | wc -l`
- Broker connection metrics endpoint: `/metrics` with `kafka_rpc_active_connections` and `kafka_rpc_connections_rejected`
- Recovery confirmed by runtime health checks returning healthy across all five runtime services post-volume-wipe

## Open Questions

- Is there a way to detect impending connection exhaustion before it becomes a hard failure? A broker metric alert at, say, 80% of the configured connection limit would provide warning before outage.
- Should the Kafka client layer enforce reconnect backoff configuration at initialization time, failing fast if the 50ms default is used?

## Follow-up Work

- Wire reconnect backoff configuration validation into the event bus initialization path, rejecting configurations that use the 50ms default
- Add broker connection count to the platform health monitoring surface
- Document the data volume wipe recovery path in the platform runbook
