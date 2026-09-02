---
type: architecture
status: accepted
date: "2026-09-02"
title: "Kafka Schema Handshake Gate"
topics: [omnibase-infra, kafka, schema, handshake]
refs: []
---

<!-- Migrated from omnibase_infra:docs/event-bus/schema-handshake.md on 2026-09-02. -->

# Kafka Schema Handshake Gate

**Script**: `scripts/validate-kafka-schema-handshake.py`
**CI job**: `schema-handshake` in `.github/workflows/test.yml`

---

## What it does

The schema handshake gate catches **cross-repo Kafka boundary drift** before it merges
into `main`.  It performs a pure Pydantic round-trip for every registered
producer→consumer pair:

1. Validate the producer sample against the producer model.
2. Serialise to JSON (simulating the Kafka wire format).
3. Deserialise using the consumer model.

A `pydantic.ValidationError` at step 3 means the producer and consumer have
drifted — the boundary is broken.  No Kafka broker is required.

**Background**:  was caused by a field rename between the
`omniintelligence` producer (`intent_class: EnumIntentClass`) and the
`omnimemory` consumer (`intent_category: str`) on the same
`onex.evt.intent.classified.v1` topic.  This gate would have caught that at PR
review time.

---

## Running locally

```bash
# Full scan — all registered boundary pairs
uv run python scripts/validate-kafka-schema-handshake.py

# Fast path — only pairs whose models were changed vs origin/main
uv run python scripts/validate-kafka-schema-handshake.py --changed-only

# Machine-readable JSON output (human output is also always printed)
uv run python scripts/validate-kafka-schema-handshake.py --format json
```

### Prerequisites

The sibling repos must be installed as editable packages in your active
environment.  From the `omnibase_infra` worktree:

```bash
uv pip install -e ../omniintelligence -e ../omnimemory
```

If the packages are absent the script exits with code `2` and prints a
diagnostic message — it does **not** fail the gate (same behaviour as the
pytest `importorskip` guard in the existing boundary compat test).

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | All validated pairs passed (xfail pairs skipped, not failed). |
| `1`  | One or more pairs **failed** — Kafka boundary contract broken. |
| `2`  | Sibling packages not installed — gate skipped with warning. |

---

## Adding a new boundary pair

Edit `tests/integration/event_bus/test_kafka_boundary_compat.py` and append a
new entry to `BOUNDARY_PAIRS`:

```python
BoundaryPair(
    producer_cls=ProducerModel,
    consumer_cls=ConsumerModel,
    sample={
        # Minimal valid dict accepted by ProducerModel.
        "field_a": "value",
        "emitted_at": datetime(2026, 1, 1, tzinfo=UTC),
    },
    topic="onex.evt.<producer>.<event>.v1",
    xfail_reason=None,  # set to "OMN-XXXX: reason" if the pair is known-broken
)
```

The `validate-kafka-schema-handshake.py` script reads `BOUNDARY_PAIRS`
directly from that module — no other changes needed.

### Fields

| Field | Description |
|-------|-------------|
| `producer_cls` | Pydantic model used by the **publishing** service. |
| `consumer_cls` | Pydantic model used by the **consuming** service. |
| `sample` | Minimal valid dict accepted by `producer_cls`. |
| `topic` | Kafka topic name (used in test IDs and error messages). |
| `xfail_reason` | OMN ticket ref for known drift; `None` means PASS expected. |

---

## What to do when the check fails

1. **Read the error output** — it shows the topic, producer class, consumer
   class, and the exact `pydantic.ValidationError`.

2. **Identify the drift** — usually a renamed field, a changed type, or a
   required field added to the consumer that the producer does not emit.

3. **Fix the consumer or producer**:
   - If the producer owns the event schema, update the consumer to match.
   - If the consumer has stricter requirements, coordinate with the owning
     team to agree on a canonical field contract.

4. **If the fix is tracked in a separate PR**, add `xfail_reason` to the pair
   as a short-term measure:

   ```python
   xfail_reason="OMN-XXXX: producer emits foo but consumer expects bar — fix in PR #NNN"
   ```

   An `xfail` pair still runs and still appears in the output — it just does
   not fail the gate while the upstream fix is pending.

5. **Remove `xfail_reason`** once the upstream fix is merged.  The pair will
   then fail if the drift is re-introduced.

---

## CI behaviour

The CI job runs in **`--changed-only`** mode: it only validates pairs whose
producer or consumer model files were touched by the PR.  This keeps CI fast
for PRs that do not touch any boundary models.

If you rename a boundary model file, the heuristic may not detect the change.
Run the full scan locally in that case:

```bash
uv run python scripts/validate-kafka-schema-handshake.py
```

The `kafka-boundary-compat` job in `test.yml` runs the full pytest
boundary compat suite separately and is complementary to this gate.
