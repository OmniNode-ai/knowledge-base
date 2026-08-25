---
type: architecture
status: accepted
date: "2026-08-25"
title: "OmniIntelligence Contract Package Specification"
topics:
  - omniintelligence
  - contract-yaml
  - event-bus
  - auto-wiring
refs:
  - reference/omniintelligence-event-surface.md
---

# Intelligence Contract Package Specification

> **Last Updated**: 2026-08-25 — migrated from `omniintelligence` to the knowledge base. During migration, the Discovery Rules were corrected: the source document listed `event_bus_enabled: true` as a required key gating auto-wiring. Live source (`contract_topics.py`'s `_discover_effect_node_packages()` / `_has_subscribe_topics()`) does not check that key at all — the actual gate is a non-empty `event_bus.subscribe_topics` list. `event_bus_enabled` was removed from contract auto-wiring discovery in an earlier refactor and survives today only as a vestigial, unused key in 2 of the repo's 60 contracts (both compute nodes with no `subscribe_topics`, so the key has no effect either way). The YAML example and Discovery Rules below reflect the live mechanism, not the original (now-incorrect) description.

## Overview

Every intelligence effect node in `omniintelligence` declares its event bus
wiring in a `contract.yaml` file. The runtime discovers these contracts at
startup and auto-wires topic subscriptions. This document specifies the
contract structure required for a node package to participate in auto-wiring.

## Package Layout

A conforming node package lives under `src/omniintelligence/nodes/<node_name>/`
and must contain:

```
src/omniintelligence/nodes/node_example_effect/
  __init__.py           # Python package marker
  contract.yaml         # REQUIRED: node contract with event_bus section
  node.py               # Node class (extends NodeEffect)
  handlers/             # Handler functions
  models/               # Pydantic I/O models
```

The exception is `omniintelligence.review_pairing`, which lives outside `nodes/`
but follows the same contract structure.

## Contract Requirements for Auto-Wiring

The `event_bus` section in `contract.yaml` must satisfy:

```yaml
event_bus:
  version:
    major: 1
    minor: 0
    patch: 0

  subscribe_topics:                # REQUIRED: at least one topic for auto-wiring
    - "onex.cmd.omniintelligence.example-command.v1"

  publish_topics:                  # OPTIONAL: empty list if no output events
    - "onex.evt.omniintelligence.example-result.v1"
```

### Discovery Rules

1. **Non-empty `subscribe_topics`** -- packages with an empty list or missing
   `subscribe_topics` under `event_bus` are excluded from auto-wiring. This is
   the sole discovery gate; there is no separate enable/disable flag.
2. **Valid YAML** -- malformed `contract.yaml` files are logged as warnings
   and skipped (graceful degradation).

### Topic Naming Convention

```
onex.{kind}.{service}.{event-name}.v{N}
```

- `kind`: `cmd` for commands/inputs, `evt` for events/outputs
- `service`: `omniintelligence` for single-producer topics; omitted for
  multi-producer domain events
- `event-name`: kebab-case descriptor
- `v{N}`: version number

## Discovery Mechanism

`contract_topics._discover_effect_node_packages()` scans:

1. All subdirectories of `omniintelligence.nodes` (via `importlib.resources`)
2. `omniintelligence.review_pairing`

For each directory containing `contract.yaml`, it checks for a non-empty
`event_bus.subscribe_topics` list (`_has_subscribe_topics()`). Qualifying
packages are returned as fully-qualified Python package names.

`collect_subscribe_topics_from_contracts()` then reads the actual topic
strings from each discovered package's contract.

### Additional Topics

`_ADDITIONAL_SUBSCRIBE_TOPICS` appends topics for dispatch handlers that
are not backed by a dedicated effect node contract (e.g.,
`onex.cmd.omniintelligence.code-analysis.v1` for cross-repo commands).

## Adding a New Effect Node

1. Create the node package under `src/omniintelligence/nodes/node_<name>_effect/`
2. Add `contract.yaml` with a non-empty `event_bus.subscribe_topics` list
3. Implement the handler referenced in `handler_routing`
4. The node will be auto-discovered at next runtime startup -- no manual
   registration required

## Validation

The parity test at `tests/integration/runtime/test_auto_wiring_replaces_hardcoded_list.py`
verifies that all historically known packages are discoverable and that
collected topics are valid.
