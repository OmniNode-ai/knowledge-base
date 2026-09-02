---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Kafka is Required Infrastructure (Rule #8)"
topics: [omnibase-infra, adr, kafka, required]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-kafka-required-infrastructure.md on 2026-09-02. -->

# ADR: Kafka is Required Infrastructure (Rule #8)

**Status**: Accepted
**Date**: 2026-02-10

## Context

The platform originally operated under the rule "Never block on Kafka — Kafka is optional;
operations must succeed without it." This was encoded in the architecture handshake as a
constraint that all repos observed.

As the platform matured, Kafka became the sole event transport for inter-node communication,
projection publishing, DLQ routing, and wiring health monitoring. The "optional Kafka"
invariant was no longer accurate — every production deployment requires a running Kafka
cluster, and "graceful degradation" without Kafka meant silently dropping events.

## Decision

**Kafka is required infrastructure** (platform-wide rule #8). Specifically:

- Connection failures during `start()` raise and must be treated as fatal by callers.
- There is no "degraded mode" — if Kafka is unreachable, the node cannot operate.
- Async/non-blocking patterns are still required to avoid blocking the calling thread
  while waiting for Kafka acks.
- Resilience patterns (circuit breaker, retry with backoff) protect against *transient*
  broker failures, not permanent unavailability.

This replaces the previous rule "Never block on Kafka."

## Consequences

- Callers of `EventBusKafka.start()` and `ProviderKafkaProducer.create()` must not
  swallow connection errors.
- Integration tests that previously mocked Kafka away need explicit opt-in for
  Kafka-less testing via markers (`@pytest.mark.no_kafka`).
- The `localhost:9092` defaults in config models remain as development conveniences but
  must be overridden in deployed environments (per rule #7: no hardcoded configuration).
