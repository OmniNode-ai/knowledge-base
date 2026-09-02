---
type: architecture
status: accepted
date: "2026-09-01"
title: "OmniMarket Event Registry"
topics:
  - omnimarket
  - events
  - kafka
refs: []
---

<!-- Migrated from omnimarket:docs/architecture/event-registry.md on 2026-09-01 -->

# Event Registry

OmniMarket maintains a single canonical event registry that is the source of
truth for how omniclaude hook events map to Kafka topics.

## Canonical source

The canonical registry is the YAML file at:

```
src/omnimarket/nodes/node_emit_daemon/registries/topics.yaml
```

This file is the single authoritative declaration of:

- event type name
- fan-out Kafka topic(s)
- `partition_key_field` — the event field used as the Kafka message key
- `required_fields` — fields that must be present in every published envelope

Previously there were two surfaces: the emit-daemon YAML (authoritative
at runtime) and a hand-maintained Python projection in omniclaude
(`hooks/event_registry.py` + `hooks/topics.py`). The earlier drift validator
compared only topic membership, so field-level divergence (e.g.
a missing `required_fields` entry on the YAML side) passed silently. The YAML
was then made the single canonical source and the validator was promoted to a full
structural comparison.

## Drift gate

`src/omnimarket/validators/event_registry_drift.py` is the drift gate. It
compares the canonical YAML against the omniclaude Python projection on every
CI run. The gate fails if any of the following diverge:

- event-type membership (YAML vs Python)
- fan-out topic set for a shared event
- `partition_key_field` for a shared event
- `required_fields` for a shared event

Legitimate intentional divergence (emit-daemon-only synthetic events such as
`daemon.health.probe`) is declared in the baseline file at:

```
scripts/validation/event_registry_drift_baseline.txt
```

New entries in the baseline require a comment explaining the reason. Adding an
entry without fixing the underlying divergence is not acceptable; the baseline
exists only for events that are structurally correct but asymmetric by design.

## Registering a new event

1. Add the event to the canonical YAML at
   `src/omnimarket/nodes/node_emit_daemon/registries/topics.yaml`.
2. Add the corresponding entry to the omniclaude Python projection
   (`hooks/event_registry.py` and `hooks/topics.py` in the omniclaude repo).
3. Run the drift validator locally to confirm no divergence:

   ```bash
   uv run python src/omnimarket/validators/event_registry_drift.py
   ```

4. CI runs the validator automatically; a failing gate blocks merge.

## What the gate enforces

- Every event type in the YAML must appear in the Python projection (and vice
  versa, unless baseline-allowlisted).
- `partition_key_field` must match on both sides for shared events.
- `required_fields` must match on both sides for shared events.
- A missing or divergent entry is a hard CI failure, not a warning.
