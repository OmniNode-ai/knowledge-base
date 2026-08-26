# Pivots

Architectural pivots are first-class evolutionary artifacts that capture fundamental changes in architectural understanding. A pivot is not a bug fix, a refinement, or even a decision — it is a record of a moment when the team discovered that a core assumption was wrong or incomplete, forcing a genuine shift in how the system is understood.

---

## What Pivots Are

A pivot documents a paradigm shift: the before-model, the operational pressure that broke it, and the after-model that replaced it. It is an architectural postmortem at the level of mental models, not implementations.

Pivots exist because architectures do not fail suddenly. They accumulate pressure. An assumption holds for months, then a pattern of failures or friction events reveals that the assumption was always wrong — or was right under conditions that no longer apply. The pivot captures that moment of recognition so it is not re-discovered and re-litigated in future sessions.

Key properties:
- A pivot is about **understanding**, not output. The codebase may or may not change when a pivot is accepted; what always changes is the mental model used to reason about the system.
- Pivots are **durable**. Once accepted, a pivot remains in the record even if later superseded. The history of understanding is part of the system's history.
- Pivots are **evidenced**. A pivot without a traceable outcome behind it (an incident record, a test failure, a cited PR or OCC receipt) is a hypothesis, not a pivot. Evidence anchors the pivot to observable system behavior — cited, not hosted here; OCC (`onex_change_control`) is the sole evidence authority.

---

## ADR vs. Pivot

These two artifact types answer different questions and are not interchangeable.

| | ADR | Pivot |
|---|---|---|
| **Core question** | What decision was made? | Why did our understanding fundamentally change? |
| **Trigger** | A choice between options | Accumulated pressure exposing a wrong assumption |
| **Scope** | A specific design or implementation choice | A mental model or worldview about how the system works |
| **Audience** | Future engineers implementing in the same space | Future engineers reasoning about system evolution |
| **Evidence requirement** | Decision rationale, alternatives considered | Failure modes observed, operational pressure documented |
| **Reversibility** | Can be superseded by a new ADR | Becomes Historical or Superseded; the original understanding is preserved |

**Example distinction:** An ADR might record "we chose Kafka over RabbitMQ for event transport." A pivot would record "we discovered that treating the event bus as an implementation detail — rather than the system's canonical source of truth — led to divergent state across services and broken replay guarantees." The ADR is a choice. The pivot is a worldview correction.

When a pivot is accepted, it typically triggers one or more new ADRs. The pivot explains *why* the model changed; the ADRs record the specific decisions that follow from the new model.

---

## Lifecycle State Machine

```
Observed → Emerging → Accepted → Historical
                                      ↓
                                  Superseded
```

### Observed
Early signals exist that an assumption may be wrong. One or two friction events, a test failure that didn't fit the existing model, or a session that required workarounds that felt architecturally wrong. A pivot is created at `Observed` status to capture the signal before it is forgotten.

At this stage: the original assumption is documented, the pressure event is logged, but confidence is low. No doctrine changes yet.

### Emerging
The pattern is consistent across multiple sessions, services, or incidents. The old model is showing strain — not just one anomaly but a recurring class of failures or friction. The failure modes are documented. The team suspects the assumption is wrong but has not yet validated the replacement model.

At this stage: failure modes are enumerated, the pressure is multi-incident, but the new model is still forming. Confidence is `medium`.

### Accepted
Operational evidence supports the new model. The replacement assumption has been tested — directly or through inference from the evidence record — and holds. Doctrine has been updated or a formal update is in progress. Related ADRs reference this pivot.

At this stage: the pivot is considered resolved. The new model is canonical. Confidence is `high`.

### Historical
The pivot is part of the stable architectural record. It explains why certain design choices exist. No further updates are expected unless a new pivot supersedes it. Engineers reading unfamiliar parts of the system should read relevant Historical pivots as orientation.

### Superseded
A later pivot replaced this understanding. The original pivot is preserved in full — it explains what was believed at a point in time and why. The `refs` frontmatter field should reference the superseding pivot.

---

## How to Identify a Pivot-Worthy Transition

Not every architectural insight is a pivot. These signals indicate that a genuine paradigm shift is occurring rather than a refinement or correction:

**Recurring pressure across multiple sessions.** If the same class of workaround, the same design tension, or the same failure mode appears in three or more independent contexts, the underlying assumption is probably wrong — not the individual implementations.

**Existing assumptions becoming unstable.** When a rule that has guided decisions for months begins producing contradictions — valid decisions that conflict with each other under the existing model — the model itself needs examination.

**Failure modes that existing doctrine doesn't cover.** When an incident or test failure cannot be explained by any current doctrine rule, and the explanation requires reasoning about the system in a fundamentally different way, that is a candidate pivot.

**Worldview transitions.** When the team's language about the system shifts — when conversations start using different metaphors, different primitives, different causal chains — that linguistic shift often reflects an underlying model shift worth capturing.

**Post-incident realizations.** After a production incident or a significant integration failure, the root cause analysis may reveal that the failure was inevitable given the previous model. That realization is a pivot.

If you are uncertain whether something is a pivot or just a bug fix, ask: "Does fixing this require changing how we *think about* this part of the system, or just how we *implemented* it?" If the answer is thinking, it is a pivot.

---

## How to Write a Pivot

Use `_template.md` as the starting point. Each section serves a specific purpose:

**`Original Assumption`** — State the previous mental model in plain language. Be precise: what was believed, by whom (implicitly), and what decisions it justified. Avoid vague language like "we assumed things would work." State the concrete claim that turned out to be wrong.

**`Pressure Encountered`** — Describe the operational context that exposed the assumption. What was the team trying to do when the pressure appeared? What friction events, test failures, or incidents accumulated? This section should be traceable to specific sessions, tickets, or evidence artifacts.

**`Failure Modes Observed`** — List the concrete, observable failures that the old model produced. Be specific: which services broke, which invariants were violated, which tests failed, which guarantees could not be upheld. This is the evidence section that distinguishes a validated pivot from a hypothesis.

**`Pivot`** — One or two sentences: what fundamentally changed. This is the core of the artifact. It should be possible to read only this section and understand what shifted.

**`New Model`** — Describe the replacement understanding. What claim replaces the old one? What decisions does the new model justify? What behavior does it predict that the old model did not?

**`Preserved Invariants`** — What remained true across the transition? Pivots are disruptive but not total rewrites of understanding. Identifying preserved invariants prevents over-rotation and helps engineers understand what they can still rely on.

**`Doctrine Impact`** — Which doctrine rules changed, emerged, or were invalidated? Reference specific doctrine sections by name. If no doctrine update has landed yet, note it as pending and create a follow-up ticket.

**`Related ADRs`** — ADRs that were triggered by or informed this pivot. Include ADRs that were *invalidated* by the pivot, not just new ones.

**`Related Incident Analysis`** — A summary, in this pivot's own words, of the pressure events or incident analyses that support it. Cite tickets or outcomes by reference (not internal identifiers); do not host the incident write-up itself here.

**`Evidence`** — Specific, traceable proof that the new model holds, cited by reference: a PR, a CI run, an OCC receipt, a system metric. Evidence should be verifiable — not "we believe the new model is better" but "this cited outcome demonstrates the new model is correct." This section links to proof; it does not reproduce it.

**`Consequences`** — What the accepted pivot implies going forward. What work is now required? What previous work may need revisiting? What new constraints apply?

---

## Relationship to Other Artifacts

**Doctrine.** Accepted pivots are the primary driver of doctrine updates. When a pivot reaches `Accepted` status, the corresponding doctrine section must be updated or a ticket must be opened to do so. Doctrine that does not reflect accepted pivots is stale.

**ADRs.** Pivots explain *why* the context for decisions changed. ADRs record the specific decisions made under the new context. A cluster of ADRs that all cite the same new constraint is often evidence that a pivot is needed to capture the root cause of that constraint.

**Operational incidents.** An internal postmortem or work session that concludes "our previous model was wrong about X" is a direct pivot candidate. That narrative record stays internal (this repository does not host operational journals); the pivot itself is the durable, public distillation of what changed and why, referenced in the `Related Incident Analysis` section.

**Evidence artifacts.** Integration verification receipts, DoD evidence records, and incident postmortems all serve as pivot evidence, held in OCC (`onex_change_control`) — the sole evidence authority. The `Evidence` section of a pivot should cite these artifacts by reference, not host or reproduce them.

**Tickets.** A pivot at `Emerging` or `Accepted` status typically has one or more associated tickets: doctrine updates, ADR authoring, code changes that follow from the new model. Reference these in `Consequences`.

---

## Current Pivots

| ID | Title | Status | Date |
|----|-------|--------|------|
| [PIVOT-0001](PIVOT-0001-ingestion-is-not-interpretation.md) | Ingestion Is Not Interpretation | accepted | 2026-05-23 |
| [PIVOT-0002](PIVOT-0002-dashboard-authority-collapse.md) | Dashboard Authority Collapse | accepted | 2026-05-23 |
| [PIVOT-0003](PIVOT-0003-completion-requires-durable-evidence.md) | Completion Requires Durable Evidence | accepted | 2026-05-23 |
| [PIVOT-0004](PIVOT-0004-reducers-own-state-progression.md) | Reducers Own State Progression | accepted | 2026-05-23 |
| [PIVOT-0005](PIVOT-0005-event-streams-are-not-authoritative-state.md) | Event Streams Are Not Authoritative State | accepted | 2026-05-23 |
