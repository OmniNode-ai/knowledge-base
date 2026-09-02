---
type: reference
status: current
date: "2026-09-02"
title: "OmniMarket node_golden_chain_sweep"
topics:
  - omnimarket
  - nodes
  - onex-runtime
refs: []
---

<!-- Migrated from omnimarket:src/omnimarket/nodes/node_golden_chain_sweep/SKILL.md on 2026-09-01 -->

# golden_chain_sweep

Validates field-level correctness of **pre-collected** projection rows against
chain definitions.

> **Evidence scope.** This node is **pure compute over
> caller-supplied `projected_rows`** — it performs **zero live I/O**: no Kafka
> publish, no DB poll, no `count(*)`, no row-count delta. A `pass` means only
> that the rows the caller handed in contain the expected field keys. It does
> **NOT** prove that any event flowed end-to-end or that any row materialized in
> a live tail table.
>
> **Do NOT cite a `golden_chain_sweep` pass as live row / end-to-end data-flow
> evidence.** It is a deterministic field-presence validator, suitable for
> regression/diagnostic checks over rows you have already fetched by other means.
> A real live-Postgres fetch + row-count-delta assertion (publish a head event,
> read the tail-table row back, assert the delta) is tracked as a follow-on task
> and is **not** implemented here yet.

## Chain Registry

Chains are defined in `golden_chains.yaml` (co-located with this node).
The sweep tool reads this file at startup — adding a new chain here automatically
includes it in sweep coverage without touching any Python code.

**Registry schema** (each entry under `chains:`):

| Field | Required | Description |
|---|---|---|
| `name` | yes | Unique chain identifier, used as key in `--chains` filter |
| `head_topic` | yes | Kafka topic that initiates the chain |
| `tail_table` | yes | DB projection table that should receive the event |
| `expected_fields` | no | Fields that must be present in the projected row |
| `timestamp_field` | no | Tail-row column holding the row's event/ingest time (default `created_at`). Read only when `max_row_age_seconds` is set. |
| `max_row_age_seconds` | no | Per-chain recency threshold. When set, a field-complete row older than this many seconds is downgraded to **STALE** (a distinct non-PASS tri-state) instead of reading green. Omit to disable the freshness check. |

**Example:**

```yaml
chains:
  - name: registration
    head_topic: onex.evt.omniclaude.routing-decision.v1
    tail_table: agent_routing_decisions
    expected_fields:
      - correlation_id
      - selected_agent

  - name: pattern_learning
    head_topic: onex.evt.omniintelligence.pattern-stored.v1
    tail_table: pattern_learning_artifacts
    timestamp_field: created_at
    max_row_age_seconds: 86400   # STALE if the latest row is > 24h old
    expected_fields:
      - correlation_id
```

> **Freshness.** Field-presence alone reads green on a weeks-old
> fixture row even when the producer is idle. A chain with `max_row_age_seconds`
> additionally asserts the latest tail row is recent: a field-complete but
> stale row is reported as `STALE` (overall sweep status `warn` — non-blocking)
> with the row age, so a green verdict requires recent flow, not merely a
> matching historical row. The reference clock is supplied via `--now-iso`
> (CLI) / `now_iso` (request) — the compute never reads the system clock.

If `golden_chains.yaml` is missing or unreadable, the node falls back to an
empty chain list and logs a warning.

## Usage

```bash
# Run all chains from registry
python -m omnimarket.nodes.node_golden_chain_sweep

# Run specific chains
python -m omnimarket.nodes.node_golden_chain_sweep --chains registration,routing

# Pass pre-collected projection data
python -m omnimarket.nodes.node_golden_chain_sweep \
    --projected-rows '{"registration": {"correlation_id": "abc", "selected_agent": "x"}}'
```

## Output

JSON `GoldenChainSweepResult` to stdout. Exit code 0 on overall pass, 1 otherwise.

## CI census gate

This node is a **validator**, not a collector — it only ever looks at the
`projected_rows` a caller hands it. The omnimarket CI harness that actually
**collects** those rows is `census_collector.py` (co-located). It is a real
in-memory probe, not prose and not an operator flag:

- `reachability.py` **derives** (from node contracts + handler introspection)
  which chains omnimarket can prove head→tail in-memory (**Group A**) vs which
  are cross-repo/runtime-dependent and routed to omnibase_infra CI (**Group B**).
  The split is computed, never hand-maintained.
- `census_collector.py` drives each Group-A chain's **real** projection handler
  on an `InmemoryDatabaseAdapter`, reads the materialized tail row back, runs the
  sweep with a `ModelChainCensus` (recording `scanned_count` = surfaces queried),
  and exits non-zero unless `overall_status == pass` **and** `scanned_count > 0`.

```bash
# omnimarket CI (Group A gate): fail-closed on an empty/failing census
uv run python -m omnimarket.nodes.node_golden_chain_sweep.census_collector

# omnibase_infra CI (Group B): emit the DERIVED cross-repo routing manifest
uv run python -m omnimarket.nodes.node_golden_chain_sweep.census_collector --mode route
```

`scanned_count == 0` (no census collected) fails closed to `NOT_COLLECTED` — a
green verdict over an absent census is impossible. This closed the vacuous-green
hole where CI gated on the *workflow* completing rather than the node's verdict.
