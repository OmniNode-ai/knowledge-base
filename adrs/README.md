# Architecture Decision Records

Architecture Decision Records — the formal decision ledger. Each ADR captures a single architectural decision: what was decided, what was considered and rejected, and what the consequences are expected to be.

**Lifecycle:** Proposed → Accepted → Superseded → Deprecated → Rejected

A Proposed ADR is under review. Accepted means the decision is in effect. Superseded means a later ADR replaced it (with a link). Deprecated means the decision is no longer relevant. Rejected means it was considered and not adopted.

## ADR Index

| ADR | Date | Status | Summary |
|-----|------|--------|---------|
| [ADR-0001](ADR-0001-dependabot-approval-manual.md) | 2026-03-25 | Accepted | Dependabot PR approval remains a manual step; GitHub organization policy prevents programmatic automation |
| [ADR-0002](ADR-0002-data-verification-invocation.md) | 2026-04-23 | Accepted | Data verification invoked via Kafka command topic; table selection from ticket contract; receipts block Done not merge |
| [ADR-0003](ADR-0003-registration-runtime-registry-boundary.md) | 2026-04-23 | Accepted | Runtime owns discovery/wiring; registration owns orchestration; registry projections own durable read truth |
| [ADR-0004](ADR-0004-registry-owned-consumer-surface.md) | 2026-04-23 | Accepted | `registration_projections` is the canonical registry source; synchronous consumers go through the registry API |
| [ADR-0005](ADR-0005-dispatch-lifecycle-canonical.md) | 2026-04-28 | Accepted | Typed FSM events (`ModelDispatchLifecycleEvent`) are canonical dispatch lifecycle truth; YAML records are projections only |
| [ADR-0006](ADR-0006-skill-liveness-validator-home.md) | 2026-04-28 | Accepted | Skill liveness validator code lives in `omnibase_core`; invoked from agent plugin (pre-commit) and market repo (CI) |
| [ADR-0007](ADR-0007-skills-canonical-plan.md) | 2026-04-28 | Accepted | One canonical skills migration plan declared; duplicate archived with explicit merge requirements |
