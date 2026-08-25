---
type: runbook
status: current
date: "2026-08-24"
title: "Fault-injection fixture — DLQ offset-withholding proof"
topics: [omnibase-infra, fault, inject, fixture, dlq]
refs: []
---

# Fault-injection fixture — DLQ offset-withholding proof

**Node:** `node_fault_inject_fixture_compute` (`src/omnibase_infra/nodes/node_fault_inject_fixture_compute/`)
**Ticket:** <ticket> (<ticket> follow-on)
**Status:** Code landed (contract + handler + catalog service definition). Live
deployment and the live double-failure proof described below have **not**
been run as part of <ticket> — see "What is not yet proven" at the bottom.

## Why this exists

<ticket>'s result-applier fix has two halves: (a) a failed publish safely
lands in the DLQ instead of being silently swallowed ("ACK via DLQ"), and (b)
when the DLQ write *also* fails, `BoundaryApplyPublishError` propagates so the
consumer offset is withheld (redelivery on restart instead of silent loss).
The <ticket> live probe against `node_test_generator_compute` proved (a) but
could not prove (b): the DLQ write re-publishes the *original small inbound
command*, never the oversized outbound result, so amplifying one contract's
result can never also fail its own DLQ leg — and IAM-denying the shared
`onex.dlq.omnibase-infra.commands.v1` topic would affect every other
contract's failures for the fault window, not just a synthetic test.

This fixture solves both problems by owning its own command/result topic
pair and, when deployed via the dedicated catalog service below, its own
private `dead_letter_topic` override that is deliberately left unprovisioned.

## Mechanism

1. Publish `ModelFaultInjectFixtureCommand` to
   `onex.cmd.omnibase-infra.fault-inject-fixture.v1` with `inflate_result_bytes`
   tuned past the live broker's `message.max.bytes` / producer
   `max_request_size`. <ticket> measured ~1,048,588 bytes live on onex-dev —
   **re-probe this value before reuse**, it is a live broker-config fact, not
   a constant (see the <ticket> comment thread for the binary-search method).
2. `HandlerFaultInjectFixture.handle()` returns a result whose `padding`
   field is exactly `inflate_result_bytes` bytes (unit-proven in
   `tests/unit/nodes/test_node_fault_inject_fixture_compute/test_handler_fault_inject_fixture.py`).
3. The runtime's boundary-apply-publish path
   (`omnibase_infra/runtime/auto_wiring/handler_wiring.py`,
   `_route_apply_publish_failure`) attempts the primary publish to
   `onex.evt.omnibase-infra.fault-inject-fixture-completed.v1` — fails
   (oversized).
4. It then attempts the DLQ write. Because this fixture's dedicated
   deployment sets `KAFKA_DEAD_LETTER_TOPIC` to
   `onex.dlq.omnibase-infra.fault-inject-fixture.v1` — a topic that is
   deliberately never provisioned — that write also fails.
5. Both legs failed → `BoundaryApplyPublishError` → offset withheld. Confirm
   via the same evidence pattern as the <ticket> probe:
   - publish failure log for the primary topic
   - publish failure log (or absence of a DLQ record) for the private DLQ topic
   - consumer group offset for this fixture's dedicated group does **not**
     advance past the fault message (compare before/after; expect redelivery
     on restart)
   - `metric_name=boundary_swallow_prevented` / equivalent boundary metric,
     confirming the new-fix code path fired rather than a legacy swallow
   - **zero effect** on any other contract's traffic: spot-check an unrelated
     consumer group's offset and the shared
     `onex.dlq.omnibase-infra.commands.v1` topic before/after — neither
     should move.

## Deployment

`docker/catalog/services/fault-inject-fixture.yaml` defines a dedicated
runtime process for this fixture, modeled on
`docker/catalog/services/dlq-replay-consumer.yaml` (the existing
single-purpose persistent-consumer pattern in this repo):

- `ONEX_GROUP_ID: onex-fault-inject-fixture` — its own consumer group, so its
  offset is observable independently of every other consumer.
- `KAFKA_DEAD_LETTER_TOPIC: onex.dlq.omnibase-infra.fault-inject-fixture.v1`
  — the private, unprovisioned DLQ override
  (`ModelKafkaEventBusConfig.dead_letter_topic` takes precedence over the
  category-derived shared DLQ topic per `mixin_kafka_dlq.py:264-265`).

The `fault-injection` bundle (`docker/catalog/bundles.yaml`) is deliberately
**not** included in the `runtime` bundle — it is opt-in and depends_on
`omninode-runtime` + `redpanda`, which it does not itself provide (only
`core`). Bring it up alongside `runtime`:

```bash
cd omnibase_infra
uv run onex docker-catalog validate         # validate the manifest first
uv run onex docker-catalog generate         # regenerate the compose file — never hand-edit it
onex up runtime fault-injection             # or the lane-appropriate equivalent
```

## What is not yet proven (open as of <ticket>'s PR)

- **Live deployment.** The catalog service file has not been deployed to any
  lane. `KAFKA_DEAD_LETTER_TOPIC` is a process-wide
  `ModelKafkaEventBusConfig` field (env `KAFKA_DEAD_LETTER_TOPIC`), not a
  per-node override — confirm at deploy time that this dedicated container
  only ever handles this fixture's own contract (via `ONEX_GROUP_ID` +
  subscribed topics) and never picks up traffic for any other
  `omnibase_infra` contract that happens to be loadable from the same
  package image, since `active_runtime_packages` scopes at the *package*
  level (`contracts/services/runtime_policy.contract.yaml`), not the
  individual-node level.
- **The live double-failure run itself** (acceptance criteria 1–2 of
  <ticket>): actually publishing an oversized command against a deployed
  instance of this fixture and reading back the primary-publish failure, the
  DLQ-leg failure, and the withheld offset. Follow the <ticket> probe's
  evidence pattern (see that ticket's comment thread) once this fixture is
  deployed.

## Re-running this fixture for a future boundary-fix regression

1. Confirm the fixture's dedicated deployment is up (`docker ps` /
   `docker compose ps` for the `fault-inject-fixture` service on the target
   lane).
2. Re-probe the live broker's effective size ceiling for that lane (do not
   assume the <ticket> onex-dev value still holds, or holds on a different
   lane).
3. Publish `ModelFaultInjectFixtureCommand` with `inflate_result_bytes` set
   just past that ceiling to `onex.cmd.omnibase-infra.fault-inject-fixture.v1`.
4. Read back per the evidence checklist in "Mechanism" step 5 above.
5. Record the run's evidence (logs + offsets + topic readback) on the ticket
   driving the boundary-fix regression check — this fixture does not
   auto-record anything itself.
