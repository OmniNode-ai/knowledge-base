---
type: pivot
status: accepted
date: "2026-05-23"
title: "Dashboard Authority Collapse"
observed_date: "2026-02-01"
confidence: high
topics: [dashboard, projections, client-state, authority, truth]
refs:
  - doctrine/authoritative-projections-own-truth.md
  - doctrine/state-is-materialized-projection.md
  - doctrine/truth-must-be-proven.md
  - adrs/ADR-0003-registration-runtime-registry-boundary.md
  - adrs/ADR-0004-registry-owned-consumer-surface.md
---

# PIVOT-0002: Dashboard Authority Collapse

## Original Assumption

The dashboard was understood as an intelligent aggregator — a system that knew how to pull from multiple data sources, reconcile inconsistencies, deduplicate overlapping records, and present a unified view. Client-side logic that merged event streams, resolved conflicts, and computed derived metrics was considered part of the dashboard's value: it made sense of raw data that the backend provided in incomplete or overlapping form.

This assumption extended to state management. Dashboard client state was the accumulated result of merges, deduplication passes, and cache-local computations. When the backend provided partial or inconsistent data, the dashboard was expected to fill the gaps through client-side inference.

The architecture implicitly treated the dashboard as a co-owner of truth: what the user saw was a product of both backend data and client-side interpretation. If the user saw different things in different browser tabs, or if a refresh changed the numbers, that was considered a caching or timing problem rather than a fundamental architectural violation.

## Pressure Encountered

The first dashboard implementation made this assumption explicit by design. It consumed multiple event topics, deduplication logic ran client-side, and computed metrics were assembled from merged streams.

The failures were visible immediately in production but difficult to diagnose because they were non-reproducible. The same dashboard opened in two browser windows showed different node counts, different registration states, and different cost totals — not because of network timing, but because each window had accumulated a different client-side state from the same event streams.

Additional pressure came when backend projections were compared against client-rendered values. The backend projections showed state derived from the full event sequence through a declared reducer. The dashboard showed state derived from whichever subset of events each client had received and processed. The two surfaces diverged silently and there was no authoritative way to determine which was correct.

The registration system presented a concentrated version of this problem. Multiple tables and views represented "registry state" from different angles: a runtime-maintained in-memory list, a projection table, a legacy compatibility view, and a dashboard-cached version derived from event subscriptions. Each consumer believed its view was authoritative. None of them was.

## Failure Modes Observed

**Multi-client divergence.** Two browser windows connected to the same backend showed different system state. Refreshing resolved the divergence temporarily, but client-side state would diverge again within minutes. Users could not determine which window showed the correct state.

**Client-projection disagreement.** Metrics visible on the dashboard differed from values returned by direct backend API calls to the projection layer. In some cases the dashboard showed nodes as registered that the projection had already marked as expired. In others, the dashboard showed higher counts than the projection because client-side deduplication was less aggressive than projection-side deduplication.

**Garbage node persistence.** The platform registry showed stale or invalid nodes as active even when the backend projection did not. Client-side state caches did not expire entries on the same schedule as the server-side projection. Entries that the projection had correctly removed continued to appear in the dashboard until the client cache was invalidated.

**Verification impossibility.** Because client-side state was constructed from event streams rather than read from a single projection surface, there was no canonical query that could verify what a user was seeing. A test that checked the projection API would pass. A test that checked what the dashboard rendered might fail, pass, or produce an indeterminate result depending on client state accumulated since the last load.

## Pivot

The dashboard is a renderer of projection-owned truth. It is not a co-owner of truth, a deduplication authority, or a state accumulator.

**Clients consume projections.** The backend exposes projections. Dashboard pages subscribe to or query those projections. They do not merge event streams, perform their own deduplication, or accumulate state that the projection does not own.

**Client-side state is presentation-only.** UI interaction state — which panel is expanded, which filter is selected, whether a modal is open — is legitimate client-side state. Business truth — node counts, registration status, cost totals, event sequences — must come from projections. If a backend projection does not exist for a piece of data the dashboard needs, the correct response is to build the projection, not to compute the value client-side.

**The projection surface is the truth contract.** When the dashboard and the projection API disagree, the projection API is correct. The dashboard is incorrect. Debugging starts at the projection subscription path, not at client state.

**No client-side merging of authoritative records.** A client that receives two events about the same entity and must decide which is "newer" or "correct" is exceeding its authority. That decision belongs to the projection's reducer.

## New Model

The dashboard architecture has two layers:

**Layer 1 — Projection surfaces (backend authority):**
Each piece of system state the dashboard needs to display has a corresponding backend projection. That projection sequences events, applies a reducer, and materializes the state the dashboard will render. The projection exposes a query API or a subscription topic. It owns the authoritative value.

**Layer 2 — Rendering (client authority):**
The dashboard subscribes to or queries projection surfaces. It renders what projections report. It may cache values for performance across interactions (session cache), but any cache entry must be invalidatable on demand, and the invalidation must produce a fresh read from the projection surface rather than a client-side recomputation.

The client is allowed to make the data presentable — format numbers, sort rows, highlight changes. It is not allowed to decide what the numbers mean.

The consequence for dashboard development: any new dashboard feature begins with defining what projection surface it will read, not with defining what client-side logic will compute the values.

## Preserved Invariants

- The event bus remains the source for projection updates. Projections subscribe to relevant topics; the dashboard does not subscribe to those same topics to maintain parallel state.
- Real-time updates are still achievable. The constraint is not "no live updates" but "updates must flow through projections, not through direct event stream subscription in the client."
- Performance optimizations remain valid. Caching at the API layer, pagination, and cursor-based loading are all consistent with this model as long as the cached values originate from projections.

## Doctrine Impact

This pivot directly influenced the doctrine on authoritative projections owning truth. The doctrine explicitly prohibits clients from merging event streams into truth, deduplicating authoritative records, or fabricating consistency. It restricts dashboard-v2 to consuming event-bus, projection, or API surfaces only.

The doctrine on state as a materialized projection codifies the consequence: there is no valid dashboard-computed system state. All state the dashboard displays must be explicitly constructed by a projection service.

The truth-must-be-proven doctrine reinforces the verification implication: dashboard renders that differ from projection values are not acceptable differences of opinion. They are incorrect renders, and the projection surface is the arbiter.

## Related ADRs

- `adrs/ADR-0003-registration-runtime-registry-boundary.md` — establishes the registry projection as the canonical truth surface, explicitly rejecting runtime memory and legacy compatibility views as read authority
- `adrs/ADR-0004-registry-owned-consumer-surface.md` — names the canonical registry projection surface that downstream consumers including the dashboard must read from

## Related Deep Dives

The registration system was the most concentrated demonstration of this problem. Multiple surfaces — runtime in-memory state, projection tables, legacy compatibility views — each represented "the truth" about node registration state to different consumers. The ADRs establishing the registry boundary were direct products of this pivot's analysis applied to the registration domain.

## Evidence

The most direct evidence was the node count discrepancy: platform registry pages showed stale nodes because client-side state was not on the same expiry schedule as the server projection. After the architectural change — removing client-side event stream subscriptions and replacing them with projection API reads — the registration pages converged across browser windows and matched the backend projection without exception.

The second evidence category was test stability: tests that asserted projection API values became stable and deterministic. Tests that asserted dashboard-rendered values became stable only after client-side state accumulation was eliminated.

## Consequences

**Positive:**
- Dashboard state is now verifiable: the correct state is always "what the projection says," and the projection can be queried directly
- Multi-client divergence is eliminated: all clients read from the same projection surface
- New dashboard pages have a clear design path: define the projection, build the subscription or query, render the result
- The dashboard codebase became simpler: all the deduplication and merging logic was removed

**Negative / tensions:**
- Backend projection coverage becomes a prerequisite for every dashboard feature. This slows dashboard development when a needed projection does not exist and requires a full backend change before the frontend can proceed.
- The strict boundary requires discipline during code review. Client-side state that "just derives a count from the events in memory" is tempting and violates the model.
- Latency characteristics changed. Some values that were previously computed at render time from cached events now require a projection query, which may have different latency properties depending on query complexity.
