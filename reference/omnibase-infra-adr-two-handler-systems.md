---
type: reference
status: current
date: "2026-09-02"
title: "ADR: Two Handler Systems in omnibase_infra"
topics: [omnibase-infra, adr, two, handler]
refs: []
---

<!-- Migrated from omnibase_infra:docs/decisions/adr-two-handler-systems.md on 2026-09-02. -->

# ADR: Two Handler Systems in omnibase_infra

**Status**: Accepted
**Date**: 2026-02-24

---

## Context

During  research (2026-02-06), it was discovered that omnibase_infra contains
two completely separate handler systems that are superficially similar — both are called
"handlers", both process messages — but have fundamentally different discovery, routing,
wiring, and contract semantics.

This distinction was **not documented anywhere**, which caused  to be planned
under the false assumption that the orchestrator needed its own Docker Compose service.
Future contributors will make the same architectural mistake without this ADR.

The two systems are:

1. **Infrastructure Handlers** (`ProtocolHandler`) — protocol adapters for external services
2. **Orchestrator Handlers** (`ProtocolMessageHandler`) — domain event handlers in the registration workflow

---

## Decision

The two handler systems are **formally distinct architectural layers** and must remain
separate. They are not variations of the same pattern — they serve different purposes,
have different discovery mechanisms, and different contract semantics.

### System 1: Infrastructure Handlers (`ProtocolHandler`)

Infrastructure handlers are **protocol adapters** for external services (HTTP, database,
Consul, Vault, MCP, filesystem, etc.). They are the I/O boundary of the ONEX runtime.

**Base protocol**: `ProtocolHandler` (via `BaseHandler`)

**Discovery**: Auto-discovered at startup by `ContractHandlerDiscovery`, which scans for
`handler_contract.yaml` files on the filesystem. No Python import is required to register
a new infrastructure handler — the presence of a contract YAML is sufficient.

**Contract schema**: `handler_contract.yaml` with:
- `handler_id`: unique transport identifier (e.g., `effect.filesystem.handler`)
- `descriptor`: timeouts, retry policy, circuit breaker, concurrency policy
- `capability_outputs`: what operations the handler can perform
- `event_bus.subscribe_topics`: which Kafka topics to subscribe to (when applicable)
- `input_model` / `output_model`: Pydantic model references

**Routing**: Envelope-based, routed by `transport_type` field (HTTP, DATABASE, CONSUL,
VAULT, MCP, etc.). The `MessageDispatchEngine` owns the subscription lifecycle.

**Wiring**: `EventBusSubcontractWiring` reads `event_bus.subscribe_topics` from the
handler contract and wires Kafka subscriptions automatically.

**Three-dimensional type system**:
- `handler_type` (`EnumHandlerType`): architectural role — always `INFRA_HANDLER` for protocol adapters
- `handler_category` (`EnumHandlerTypeCategory`): behavioral classification — always `EFFECT` for external I/O
- `transport_type` (`EnumInfraTransportType`): protocol identifier — `HTTP`, `DATABASE`, `KAFKA`, `CONSUL`, etc.

**Examples**:
- `HandlerHttpRest` — HTTP client adapter
- `HandlerDb` — PostgreSQL adapter
- `HandlerConsul` — Consul service-discovery adapter
- `HandlerVault` — HashiCorp Vault secrets adapter
- `HandlerMCP` — Model Context Protocol adapter
- `HandlerFilesystem` — Local filesystem adapter

**Key property**: Infrastructure handler contracts are **read by the runtime** at startup.
The contract YAML directly governs behavior (timeouts, retries, Kafka subscriptions).

### System 2: Orchestrator Handlers (`ProtocolMessageHandler`)

Orchestrator handlers are **domain event handlers** inside specific ONEX nodes (currently
the registration orchestrator). They respond to lifecycle events like node introspection,
runtime ticks, and registration acknowledgements.

**Base protocol**: `ProtocolMessageHandler`

**Discovery**: Hardcoded Python imports in `plugin.py` → `wiring.py`. The runtime does
not discover orchestrator handlers automatically. Each handler must be explicitly imported
and registered in the plugin's `wire_handlers()` method.

**Contract schema**: The parent node's `contract.yaml` with `consumed_events` /
`published_events` sections. These sections are **specification-only** — the runtime does
NOT read them to configure routing. They serve as documentation and for tooling analysis.

**Routing**: Category-based via `payload_type_match` strategy in `IntrospectionEventRouter`.
The handler is selected based on matching the payload Python type, not a transport enum.

**Wiring**: Manual kernel bootstrap. The plugin's `wire_handlers()` calls
`wire_registration_handlers()` which explicitly instantiates and wires each handler.
The plugin's `wire_dispatchers()` registers dispatchers with `MessageDispatchEngine`.

**Examples** (all inside `node_registration_orchestrator/handlers/`):
- `HandlerNodeIntrospected` — processes `ModelNodeIntrospectionEvent` (registration trigger)
- `HandlerRuntimeTick` — processes periodic runtime tick events
- `HandlerNodeRegistrationAcked` — processes registration acknowledgement
- `HandlerNodeHeartbeat` — processes node heartbeat events
- `HandlerTopicCatalogQuery` — handles topic catalog queries

**Key property**: Orchestrator handler contracts (`consumed_events`/`published_events`) are
**NOT read by the runtime**. They document the handler's event interface for contributors
and tooling but have no runtime effect.

---

## Comparison Table

| Dimension | Infrastructure Handlers | Orchestrator Handlers |
|-----------|------------------------|----------------------|
| Base protocol | `ProtocolHandler` | `ProtocolMessageHandler` |
| Python location | `src/omnibase_infra/handlers/` | `src/omnibase_infra/nodes/<node>/handlers/` |
| Discovery | Auto via `ContractHandlerDiscovery` | Hardcoded imports in `plugin.py` |
| Contract file | `handler_contract.yaml` | Parent node's `contract.yaml` |
| Contract read at runtime? | **Yes** — governs behavior | **No** — documentation/spec only |
| Routing mechanism | `transport_type` enum via dispatch engine | `payload_type_match` via `IntrospectionEventRouter` |
| Kafka wiring | `EventBusSubcontractWiring` (from contract) | Manual `wire_registration_handlers()` |
| Handler type | `INFRA_HANDLER` / `DOMAIN_HANDLER` | `ORCHESTRATION_HANDLER` |
| Deployment unit | Part of the runtime service | Part of the same runtime service (no separate container) |
| Adding a new handler | Add Python class + `handler_contract.yaml` | Add Python class + update `wiring.py` imports |

---

## Why Two Systems Exist

### Infrastructure handlers are generic and pluggable

Infrastructure handlers adapt external protocols (HTTP, SQL, KV stores, service mesh).
They are:
- **Protocol-agnostic at the dispatch level**: the dispatch engine doesn't need to know
  which protocol is behind a handler
- **Independently configurable via contract**: timeouts, retries, and circuit breakers
  are declared in YAML without code changes
- **Discoverable at startup**: new handlers can be added by dropping a YAML + Python file
  without modifying any kernel or plugin code

This makes sense for the infrastructure layer where handlers are numerous (one per external
service type) and mostly follow the same pattern.

### Orchestrator handlers have complex dependency graphs

Orchestrator handlers (especially in the registration workflow) have tight dependencies on:
- Specific projectors (`ProjectionReaderRegistration`)
- Domain services (`RegistrationReducerService`)
- Database connection pools (asyncpg)
- Other handlers in the same workflow

These dependencies require manual dependency injection at bootstrap time. Auto-discovery
would require a more sophisticated DI framework than the current container supports.
The complexity of the dependency graph makes hardcoded wiring the pragmatic choice.

Additionally, orchestrator handlers implement multi-step workflows where **order matters**:
the introspection event handler must run before the registration ack handler can succeed.
Manual wiring makes this ordering explicit and auditable.

---

## Consequences

### For contributors adding a new infrastructure handler

1. Create `handler_<name>.py` in `src/omnibase_infra/handlers/`
2. Create `handler_contract.yaml` in `src/omnibase_infra/contracts/handlers/<name>/`
3. Implement `ProtocolHandler` protocol (not `ProtocolMessageHandler`)
4. The handler is auto-discovered at startup — no kernel changes needed
5. For Kafka subscriptions, add `event_bus.subscribe_topics` to the contract YAML

### For contributors adding a new orchestrator handler

1. Create `handler_<name>.py` in `src/omnibase_infra/nodes/<node>/handlers/`
2. Implement `ProtocolMessageHandler` protocol (not `ProtocolHandler`)
3. **Manually** add the import and registration call in `wiring.py`
4. Note: the node's `contract.yaml` `consumed_events` section is **for documentation only**
5. There is no Docker Compose service for the orchestrator — it runs inside the main runtime

### Common mistakes to avoid

- **Do not** implement `ProtocolHandler` for an orchestrator handler or vice versa
- **Do not** add `handler_contract.yaml` for orchestrator handlers (that file is only for
  infrastructure handlers and will be misinterpreted by `ContractHandlerDiscovery`)
- **Do not** create a new Docker Compose service for an orchestrator — orchestrators run
  in the same process as the kernel
- **Do not** assume that adding `consumed_events` to an orchestrator's `contract.yaml`
  will wire Kafka subscriptions — it will not; only `handler_contract.yaml` files trigger
  automatic Kafka wiring via `EventBusSubcontractWiring`

### Future options

**Option A: Formalize the split** (recommended short-term)
- Document the two systems (this ADR)
- Keep infrastructure handlers auto-discovered via YAML
- Keep orchestrator handlers manually wired
- Add validation tooling to prevent cross-contamination

**Option B: Unify via enhanced DI** (tracked separately)
- Extend `ContractHandlerDiscovery` to support dependency injection for complex handlers
- Allow orchestrator handlers to declare dependencies in their contract YAML
- Auto-wire orchestrator handlers the same way as infrastructure handlers
- Risk: significant complexity, may break current clear separation of concerns

**Option C: Keep hybrid, add contract schema alignment** (related: contract schema alignment ticket)
- Align the `contract.yaml` schema for orchestrator handlers so that `consumed_events`
  is formally recognized as a routing specification (not just documentation)
- Implement a separate discovery mechanism for orchestrator handlers that reads the
  node's `contract.yaml` but uses a different wiring path than `EventBusSubcontractWiring`

The current architecture does not preclude any of these options. The split should be
preserved until a clear migration path for Option B or C is defined.

---

## References

- `src/omnibase_infra/handlers/` — Infrastructure handler implementations
- `src/omnibase_infra/nodes/node_registration_orchestrator/handlers/` — Orchestrator handler implementations
- `src/omnibase_infra/contracts/handlers/` — Infrastructure handler contracts
- `src/omnibase_infra/nodes/node_registration_orchestrator/contract.yaml` — Orchestrator node contract
- `src/omnibase_infra/nodes/node_registration_orchestrator/plugin.py` — Plugin with manual handler wiring
- `src/omnibase_infra/nodes/node_registration_orchestrator/wiring.py` — `wire_registration_handlers()`
- `src/omnibase_infra/runtime/event_bus_subcontract_wiring.py` — Auto-wiring for infrastructure handlers
- `src/omnibase_infra/runtime/service_message_dispatch_engine.py` — Dispatch engine
- adr-handler-type-vs-handler-category (`../reference/omnibase-infra-adr-handler-type-vs-handler-category.md`) — Three-dimensional handler type system
- adr-006-message-dispatch-engine-canonical-routing (`../reference/omnibase-infra-adr-message-dispatch-engine-canonical-routing.md`) — MessageDispatchEngine as canonical pattern
- : Research that discovered this architectural gap
- : Parent epic with architecture findings
