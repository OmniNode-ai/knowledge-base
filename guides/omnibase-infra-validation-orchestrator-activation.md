---
type: guide
status: current
date: "2026-09-02"
title: "Validation Orchestrator — Activation Guide"
topics: [omnibase-infra, validation, orchestrator, activation]
refs: []
---

<!-- Migrated from omnibase_infra:src/omnibase_infra/nodes/node_validation_orchestrator/ACTIVATION.md on 2026-09-02. -->

# Validation Orchestrator — Activation Guide

## Overview

`NodeValidationOrchestrator` drives the validation pipeline: receives pattern
candidates, builds validation plans, coordinates executor and adjudicator nodes,
and publishes validation results.

## Event Flow

```
Pattern candidate submitted
  --> onex.evt.platform.validation-candidate-submitted.v1
    --> NodeValidationOrchestrator (build_plan handler)
      --> onex.evt.platform.validation-plan-created.v1
      --> onex.evt.platform.validation-execution-requested.v1
        --> Executor runs checks
          --> onex.evt.platform.validation-checks-completed.v1
            --> onex.evt.platform.validation-adjudication-requested.v1
              --> Adjudicator evaluates results
                --> onex.evt.platform.validation-adjudication-completed.v1
                  --> onex.evt.platform.validation-result-published.v1
                  --> onex.evt.platform.validation-lifecycle-updated.v1
```

## Triggering a Validation Run

Validation runs are triggered by publishing a pattern candidate event to
`onex.evt.platform.validation-candidate-submitted.v1`. This can happen:

1. **Automatically**: When omniintelligence discovers a new pattern that
   qualifies for validation (pattern_discovery pipeline)
2. **Manually**: Via the runtime API or by publishing a test event to Kafka

## Omnidash Consumer

The omnidash `ValidationProjection` (DB-backed) queries the `validation_runs`
table. The `read-model-consumer.ts` projects validation result events into
this table. The `/validation` page shows:
- Total validation runs
- Pass/fail statistics
- Recent validation results

## Subscription Topics

| Topic | Purpose |
|-------|---------|
| `onex.evt.platform.validation-candidate-submitted.v1` | Trigger: new candidate |
| `onex.evt.platform.validation-checks-completed.v1` | Executor finished checks |
| `onex.evt.platform.validation-adjudication-completed.v1` | Adjudicator verdict |

## Publication Topics

| Topic | Purpose |
|-------|---------|
| `onex.evt.platform.validation-plan-created.v1` | Plan built for candidate |
| `onex.evt.platform.validation-execution-requested.v1` | Request executor to run |
| `onex.evt.platform.validation-adjudication-requested.v1` | Request adjudicator |
| `onex.evt.platform.validation-result-published.v1` | Final result |
| `onex.evt.platform.validation-lifecycle-updated.v1` | Lifecycle state change |

## Verification

1. Start runtime services (`infra-up-runtime`)
2. Submit a test pattern candidate to the submission topic
3. Monitor Kafka for validation pipeline events
4. Check omnidash `/validation` page shows the run
