---
type: runbook
status: current
date: "2026-08-26"
title: "Kafka/Redpanda Reconnect Tuning and Broker Recovery"
topics: [kafka, event-bus, resilience, reconnect, operations]
refs: []
---

# Kafka/Redpanda Reconnect Tuning and Broker Recovery

## Applicability

This runbook applies only to the **Kafka-backed production event bus** (`EventBusKafka` / `aiokafka`). It does not apply to the **in-memory development event bus** (`InMemoryEventBus`), which has no broker, no sockets, and no reconnect behavior — see [Event Bus Integration Guide](../architecture/event-bus-integration.md) for the two implementations. A self-hoster running only the in-memory bus can skip this document; it becomes relevant the moment a real Kafka or Kafka-compatible (e.g. Redpanda) broker is introduced.

## Problem

Kafka client libraries (including `aiokafka`) ship reconnect defaults tuned for fast recovery in stable environments, not for surviving broker unavailability. Left at their defaults, those settings turn a brief broker outage into a much larger one: reconnect attempts fire in a tight loop, each attempt opens a new TCP socket, and old sockets are not cleaned up before the next attempt fires. Under concurrent producers and consumers, this can exhaust the broker's connection budget within seconds, converting a transient blip into a hard outage for every client — including ones that were never part of the original problem.

## Reconnect backoff configuration (required)

Configure explicit, bounded backoff on every long-lived producer and consumer:

| Setting | Unsafe default | Required value | Why |
|---|---|---|---|
| `reconnect_backoff_ms` | as low as `50` | `1000` (1s initial) | A sub-100ms floor means a client can attempt many reconnects per second per broker unavailability window. |
| `reconnect_backoff_max_ms` | unset / low | `30000` (30s max) | Caps the retry rate at roughly 1 attempt/30s once backoff has grown, instead of retrying indefinitely at a near-constant high rate. |

The gap between a low default and this configuration is not cosmetic: a 50ms floor against a 30-second unavailability window can produce on the order of hundreds of connection attempts per client, each opening a socket. With multiple concurrent processes (a publisher, several consumers), the aggregate socket-open rate is the product of both — a small unavailability window can generate a socket-creation spike large enough to hit the broker's connection limit on its own, independent of any legitimate traffic.

Treat this configuration as mandatory for any client that stays connected for more than a single request/response cycle. Do not rely on the library default; set both values explicitly wherever a producer or consumer is constructed.

## Broker connection-counter corruption: a restart is not a fix

If a broker's internal connection counter becomes corrupted — for example after many connections are abruptly killed during a reconnect storm — that corruption can **survive a container restart**. The counter is broker-internal bookkeeping state, not necessarily reset by a process restart the way you'd expect. A broker whose computed maximum-connections value has degraded toward zero will reject new connections from every client, including ones on the same host, and a bare restart may not clear it.

**Recovery procedure, in order:**

1. **Diagnose first.** Count active connections against the broker port (e.g. `netstat -an | grep '<broker-port>.*ESTABLISHED' | wc -l`) and check the broker's own connection metrics if it exposes them (an active-connections / connections-rejected counter). Confirm the symptom is connection-limit exhaustion, not a different failure.
2. **Stop all consumers and producers** connecting to the affected broker, to stop new connection attempts while you work.
3. **Try a non-destructive restart of the broker container first.** This is sometimes sufficient — do not skip straight to the destructive step.
4. **If the restart does not clear it, wipe the broker's data volume.** This is the fallback when the connection counter is confirmed corrupted and a plain restart does not resolve it. A data-volume wipe drops all topic offsets and message history on that broker — topics are auto-recreated on the next runtime start, but any in-flight or unconsumed history is lost. This is a destructive recovery step; treat it as last-resort, and prefer it over an extended outage only when the counter genuinely will not clear otherwise.
5. **Pin an explicit connection limit** on the broker rather than leaving it computed from available container memory. A memory-derived limit is not deterministic across restarts and can itself degrade toward zero after repeated restarts under memory pressure — pinning an explicit value removes that variable from future incidents.

## Session-bound publisher lifecycle

A publisher process that runs indefinitely accumulates socket state over its lifetime (sockets left in `TIME_WAIT` or similar transitional states), and that accumulated state makes it measurably more likely to trigger the connection-exhaustion failure mode above on any future transient broker disruption — it is competing for the same connection budget with a larger baseline footprint than a short-lived process.

Bind publisher lifetime to a bounded scope rather than letting it run indefinitely:

- start the publisher when the scope that needs it opens (a session, a request, a batch job),
- stop it explicitly when that scope ends,
- do not leave a publisher process running across scope boundaries "just in case it's needed again."

If a long-lived publisher is genuinely required, ensure whatever supervises it can terminate it cleanly (e.g. via a PID file and a session-end hook sending `SIGTERM`) rather than letting it accumulate state for the life of the host process.

## Verifying dispatch, not just publish

A publisher reporting success (its send call returned, its exit code was zero) does not confirm the message was consumed. If the topic being published to has zero active consumers — because a consumer group was never wired up, or crashed and did not restart — every message is silently dropped with no error visible to the publisher. Confirm dispatch through an independent channel: inspect the consumer group's state (active consumer count, offset progression) rather than trusting the publisher's own return value. A consumer group with zero members means every message published to its topic(s) is being dropped, regardless of what the publisher reported.

## Detecting exhaustion before it is a hard failure

Connection exhaustion at the broker does not necessarily produce an application-level error on the client — it can present only as an absence of successful reconnects, with reconnect attempts logged but no explicit "connection limit reached" surfaced to the caller. Where the broker exposes connection metrics, alert on them approaching the configured limit (e.g. 80%) rather than waiting for outright rejection; that gives an operator warning before the failure mode described above becomes a full outage.
