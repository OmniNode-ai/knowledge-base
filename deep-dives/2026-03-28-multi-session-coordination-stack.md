---
type: deep-dive
status: public-curated
date: 2026-03-28
title: "Multi-Session Coordination: Building the Session Intelligence Stack End-to-End"
period: "2026-03-25 to 2026-03-30"
topics:
  - session-management
  - knowledge-graph
  - embeddings
  - multi-agent
  - coordination
refs:
  - doctrine/state-is-materialized-projection.md
  - doctrine/contracts-define-reality.md
---

# 2026-03-28: Multi-Session Coordination — Building the Session Intelligence Stack End-to-End

## Summary

The session intelligence stack was built end-to-end in a single coordinated push: from session identity injection through hook payloads, through Kafka projectors writing to Postgres and Memgraph, through decision embeddings indexed in Qdrant, to a `resume-session` skill that queries all three stores to reconstruct context across session boundaries. The motivation was a concrete problem: agent sessions that start fresh have no access to decisions made in prior sessions, forcing expensive re-derivation or incomplete context. The stack answered the question of how a new session knows what prior sessions knew.

## Core Work

The session intelligence stack spans five integration points:

**Session identity propagation.** Each hook event payload was extended with a `task_id` field. The agent process injection path was updated to make the current task identifier available to all emitted events. This created a thread connecting all events from a single session.

**Session registry.** A Postgres table and projection handler were created to persist session state: which tasks ran, when they started and ended, and what coordination signals they emitted or consumed. The projection handler subscribes to session lifecycle events and writes rows into this registry, making it queryable via standard SQL.

**Session graph.** A Memgraph schema was defined for session relationships: sessions, tasks, decisions, and the dependency edges between them. A Kafka-to-Memgraph projector consumes session events and writes nodes and edges into the graph. This representation makes it efficient to answer questions like "what sessions contributed to the current task?" and "which decisions in earlier sessions does the current task depend on?"

**Decision embeddings.** A decision embedding pipeline consumes decision events from Kafka, generates vector embeddings, and indexes them in Qdrant with metadata linking each embedding to its originating session and task. A projection worker maintains this index continuously as new decisions are emitted.

**Resume skill.** The `resume-session` skill queries all three stores — Postgres for session metadata, Memgraph for relationship traversal, Qdrant for semantic similarity — and synthesizes a context reconstruction. A new session can call this skill to retrieve relevant prior decisions, understand what tasks have already been attempted, and avoid re-deriving conclusions that prior sessions already reached.

## Architectural Pressure

**Session isolation was both a feature and a limitation.** Each agent session starts with a clean context window and no memory of prior sessions. This isolation prevents context contamination and makes individual sessions more predictable. But for long-running workstreams that span multiple sessions, it meant re-deriving context that prior sessions had already computed, and missing the accumulated judgment that accumulates across many sessions working on the same problem.

**Multiple storage backends serve different query patterns.** Postgres handles point queries ("what was the outcome of task X?") and range queries ("all sessions that touched module Y"). Memgraph handles graph traversal ("what is the dependency path from this decision back to its root assumptions?"). Qdrant handles semantic similarity ("what prior decisions are semantically related to this current question?"). No single storage backend serves all three patterns efficiently, so the stack uses all three, with each projection handler responsible for one backend.

**Projection correctness before query correctness.** The session intelligence stack was useful only if the projections were accurate. Before building the query interface, the projection handlers needed to be validated against real session data. The approach was to build projections first, validate them against a week of historical session data, then build the query layer on top of confirmed-correct projections.

**The stack was untested end-to-end at merge time.** All individual components had unit tests. The integration path — from hook event through all three projectors to the resume skill — was not tested end-to-end at the point the stack merged. This was a known risk acknowledged in the post-merge notes; the end-to-end integration gate was explicitly marked as a follow-up requirement.

## Discoveries

**Session graph traversal is more useful than session metadata lookup.** Initial designs assumed that point queries ("give me context from session X") would dominate usage. In practice, the most valuable queries were relational: "what prior decisions are this current task's ancestors?" and "which sessions worked on overlapping problems?". Memgraph's graph model handles these queries efficiently; a flat Postgres query structure would have required complex self-joins or denormalization.

**Embedding the decision, not the task.** An earlier design embedded full task descriptions for semantic search. The insight that emerged from the embedding pipeline experiments: decision embeddings were more useful than task embeddings. Decisions capture what was concluded, not just what was attempted. A semantic search for "similar prior work" returns more actionable results when it surfaces "prior decisions about X" than "prior tasks that mentioned X".

**Coordination signals require mutual legibility.** Sessions emit coordination signals (e.g., "I am working on module Y, do not conflict") that other sessions can consume. For this to work, the signal schema must be stable across sessions that may have been started at different times with different versions of the platform. Schema versioning was built into the coordination signal event model from the start.

**Three-store synthesis is latency-sensitive.** The resume skill queries three backends sequentially in the initial implementation. For interactive use, the combined latency was acceptable. For automated session startup, where the resume skill runs before the first user prompt is processed, sequential queries introduced a startup delay. Parallel queries with a timeout reduced this significantly.

## Decisions Made

**All three backends are required.** There is no single storage backend that efficiently serves all query patterns required by the session intelligence stack. Postgres, Memgraph, and Qdrant each serve a distinct role. The projection layer maintains all three in parallel.

**Session identity is a first-class event field.** All events emitted by an agent process carry a session identifier. This field is not optional and is not application-level metadata — it is infrastructure-level correlation data that the projection layer uses to maintain the session graph.

**Projections are the source of truth for historical context.** The session intelligence stack does not store raw event payloads for replay. It materializes derived state (session registry, decision graph, semantic index) from events as they arrive. Historical context queries always go through the projection layer, never through raw event replay.

**End-to-end integration gate is mandatory before the stack is used in production.** The components merged with known unit test coverage but no end-to-end proof. A follow-up gate was explicitly created requiring a live integration test showing the full path from session event emission through projection to resume skill query.

## Candidate ADRs

- Multi-backend session intelligence: Postgres for metadata, Memgraph for graph, Qdrant for semantic search
- Session identity as a required field in all agent-emitted events
- Decision embeddings as the semantic index unit (not task embeddings)

## Candidate Pivots

The introduction of the session intelligence stack represents a pivot in the platform's memory model: from session-isolated (each session starts fresh) to session-coordinated (sessions share a persistent intelligence layer). This changes what it means for an agent session to "know" something — knowledge is now persistent across session boundaries, not just within them.

## Related Doctrine

- **Section 9 (Semantic Continuity Across Invocations):** The session intelligence stack is the implementation of this doctrine. Continuity is not a property of the session runtime; it is a property of the coordination infrastructure that persists between session invocations.
- **Section 6 (Multi-Store Consistency):** The three-store model requires that projections to all three backends remain consistent with each other. This doctrine establishes that consistency is achieved through the event stream (all projectors consume the same events) rather than through cross-store transactions.

## Related Evidence

- Session registry projection handler: queries against the Postgres table confirmed correct rows for known test sessions
- Decision embedding pipeline: Qdrant similarity searches returning semantically related decisions from prior sessions
- End-to-end gate: pending at time of merge, required before production use

## Open Questions

- What is the correct projection reconciliation strategy when a session terminates abnormally and some events are missing from the projection? Currently, the projections may have partial state for sessions that did not complete normally.
- How should the semantic similarity threshold be tuned for the resume skill? Too strict and relevant prior decisions are missed; too loose and irrelevant results pollute the context.
- Should the coordination signal schema be versioned independently from the session event schema, or should they share a version?

## Follow-up Work

- Build end-to-end integration test covering the full path from session event to resume skill query
- Implement parallel queries in the resume skill to reduce startup latency
- Define a reconciliation strategy for partial projections from abnormally-terminated sessions
- Instrument the resume skill with latency metrics per backend to identify bottlenecks
