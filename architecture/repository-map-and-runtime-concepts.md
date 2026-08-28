---
type: architecture
status: accepted
date: "2026-08-28"
title: "Repository Map and Runtime Concepts"
topics: [omnibase-core, omnibase-spi, omnibase-infra, omnibase-compat, runtime, overview]
refs: []
---

# Repository Map and Runtime Concepts

## Purpose

A newcomer can read any single OmniNode repository, find it coherent, and still be unable to answer two questions: **what do the other repositories do, and how does my repository reach them at runtime?**

This document answers exactly those two questions. It is the orientation layer above the per-repository architecture documents: read this first, then read the document for whichever repository you are working in.

## Scope

Two things, in order:

1. **The repository map** — what each repository owns, what it is forbidden to own, and which direction dependencies flow.
2. **Runtime concepts** — the small set of ideas that explain how code in separate repositories becomes one running system.

## Non-Goals

- Not a setup guide. To get a stack running, start from the getting-started guides.
- Not a per-repository deep dive. Each repository has its own architecture document with component-level detail.
- Not a deployment topology. Hosting and environments are out of scope here.

---

## Part 1 — The repository map

### The mental model in one paragraph

There are two different senses of "how the repositories connect", and conflating them is the most common source of confusion.

The first is **build-time layering**: which package may `import` which other package. That is a strict, one-way, mechanically enforced staircase across four packages.

The second is **runtime connection**: how a capability in one repository invokes a capability in another. That is not imports at all — it is messages on a bus, resolved by contract at runtime.

A repository's position in the import staircase tells you almost nothing about which repositories it talks to when the system is running. Keep the two axes separate.

### Axis 1 — the build-time staircase

Four packages form the platform substrate. Each may import only from layers below it.

```
omnibase_compat  ->  omnibase_core  ->  omnibase_spi  ->  omnibase_infra
   (floor)            (vocabulary)       (protocols)      (implementations)
```

| Package | Owns | Must not own |
|---|---|---|
| `omnibase_compat` | Wire DTOs, enums, and primitives shared across repositories. Zero upstream runtime dependencies. | Business logic, persistence, implementation adapters. It is a staging area with expiry discipline, not a permanent home. |
| `omnibase_core` | The platform vocabulary: domain models, the four node archetypes, contract resolution, validators, the command-line surface. | Transport libraries. A build-time guard rejects any core module importing a transport client. |
| `omnibase_spi` | Runtime-checkable protocol definitions — the interfaces implementations must satisfy. Imports core for the model types those signatures mention. | Implementations, and any import of the implementation layer. |
| `omnibase_infra` | Concrete implementations: the event bus, the runtime host, persistence, the dispatch path, and a large node population. | Nothing below it may import it. |

Two properties make this checkable rather than aspirational:

- **The dependency declarations are the proof.** Each package's project metadata names its allowed upstreams. You can verify the whole staircase by reading four dependency lists, without reading any Python.
- **Inversion fails loudly.** Import the wrong direction and the interpreter raises a circular-import error at startup. The failure mode is immediate and unambiguous by design.

**One sanctioned exception, and it is registered rather than folklore.** The local-runtime protocol family lives in `omnibase_core`, not in `omnibase_spi`. The reason is structural: `omnibase_spi` hard-depends on `omnibase_core`, and core's own boundary check forbids listing spi among core's dependencies — so a spi placement would force `core -> spi -> core`. Core's local runtime consumes these protocols, so core is the only non-circular home. The same reasoning puts the message-handler protocol in core, since it references core model types.

The exception is recorded in a machine-readable registry that audit tooling is required to consult *before* reporting "protocols outside spi" as a violation. If you find a protocol in core, check the registry before filing anything — a matched entry is a settled decision, not drift.

### Axis 2 — the product and agent repositories

Above the substrate sit the repositories carrying product behaviour. These are not extra layers in the import staircase; they are consumers of it.

| Repository | Owns | Connects by |
|---|---|---|
| `omnimarket` | Marketplace and product logic. The largest node population on the platform — routing, delegation, classification, evaluation, and the capability catalogue. | Consumes core models and spi protocols; runs on the infra runtime; reached over the bus. |
| `omniclaude` | The coding-agent boundary: thin shims, hooks, and agent-facing contracts. | Shims dispatch to nodes. Business logic does not accumulate here — it belongs in the node that owns the capability. |
| `omniintelligence` | Intelligence capabilities: intent, drift, and review nodes. | Nodes on the bus, like any other node population. |
| `omnimemory` | Document ingestion and semantic retrieval. | Nodes on the bus; provider integrations sit behind protocol-shaped adapters. |
| `omnidash` | The dashboard — a composable widget surface. | Renders **projections**. User interface only. |
| `omniweb` | The public web property. | Independent of the runtime data path. |
| `onex_change_control` | Governance and drift detection — the evidence authority. | Nothing depends on it. Shapes it needs are relocated to their proper home rather than imported back out of it. |

Two rules about this tier are worth stating explicitly, because both are frequently violated by newcomers:

- **`omniclaude` is shims and contracts only.** A shim that grows a decision tree has taken ownership of logic belonging in a node. Reusable capability moves out.
- **Nothing depends on `onex_change_control`.** It observes and records; it is not a library.

### Where a new artifact belongs

The placement rule is one sentence: **put an artifact in the lowest layer that satisfies all of its consumers.**

Worked through:

- A model two or more repositories need → `omnibase_core`. Not the compat floor (temporary staging), and not duplicated per repository.
- A model only one product repository needs → that repository.
- A protocol interface → `omnibase_spi`, unless it references core-resident runtime types, in which case consult the exception registry.
- A concrete implementation of a protocol → `omnibase_infra`, or the product repository owning the capability.
- Product or marketplace behaviour → `omnimarket`, as a node.

---

## Part 2 — Runtime concepts

Part 1 described where code *lives*. This part describes how it *runs*. Five ideas cover it.

### Concept 1 — three primitives, and nothing else

The architecture is exactly three constructive primitives:

- **CONTRACT** — a YAML file that is the source of truth. It declares the node's identity, its routing, its topics, and its parameters. Behaviour is declared here, not hardcoded.
- **NODE** — a thin declarative shell of one of four archetypes. It carries no logic.
- **HANDLER** — the class that owns all the logic.

The important phrase is *nothing else*. There are no plugin base classes, and no bespoke engines, managers, registries, routers, daemons, or runners in the target architecture. When you find yourself wanting one, the answer is a node with a contract and a handler.

This constraint is what makes the system legible: once you can read a contract and a handler, you can read any capability in any repository, because there is only one shape.

### Concept 2 — four node archetypes, with enforced output purity

Every node is exactly one of four archetypes, and the archetype determines what the node may produce:

| Archetype | Purpose | May produce |
|---|---|---|
| **EFFECT** | Touches the outside world — network, storage, message queues. | Events |
| **COMPUTE** | Pure deterministic transformation. No I/O. | A typed result |
| **REDUCER** | State aggregation. | Projections |
| **ORCHESTRATOR** | Multi-step coordination. | Events and intents |

This is not a naming convention. The constraint is validated, so a compute node cannot quietly start emitting projections, and an effect node cannot return a bare result. Purity is a property the system checks, not a promise the author makes.

The practical consequence for a reader: **the archetype in a node's directory name tells you what that node can and cannot do before you open a single file.**

### Concept 3 — the canonical handler shape

This is the concept most worth getting right, because it is the seam every capability passes through.

A handler exposes a typed core:

```python
def handle(self, request: ModelSomethingInput) -> ModelSomethingOutput:
    ...
```

The handler takes **a validated, typed request model as its single argument** and returns **a typed response model**. That is the whole signature.

What makes this work across a distributed system is that **the handler is not responsible for the transport envelope**. A shared runtime adapter owns the envelope boundary: it deserializes the incoming message, validates it into the typed request model, invokes the handler with that model alone, then serializes the returned model and publishes it to the topic the contract resolves. Correlation identity is preserved across that boundary by the adapter, not by the handler.

The design consequences are the point:

- The handler is **pure, typed, and directly testable**. Construct an input model, call the method. No bus, no broker, no envelope fixtures.
- The envelope lives in **exactly one place** — the shared adapter — rather than being re-implemented per node.
- A handler core that reaches for the envelope type directly has broken the boundary. That is a defect, and it is mechanically detected: a shape gate classifies every node's handler and rejects a core referencing the envelope type.

If you encounter older material presenting an envelope-wrapping signature as the handler contract, treat it as superseded. The typed-request core is the canonical shape and the enforced one.

### Concept 4 — the bus is the transport, and addressing is runtime-resolved

Services do not call each other. There is no service-to-service HTTP inside the platform.

- **Between services, the transport is the event bus.** A node publishes; interested nodes consume.
- **Locally, an in-memory bus is the default.** The same handler code runs unchanged; only the bus implementation differs. This is why a node is testable without infrastructure.
- **Addressing is resolved at runtime from contracts.** Node code does not name topics. The contract declares them and the runtime resolves them. Hand-written topic strings in application code are a defect, not a shortcut.
- **Customers never speak to the bus.** External access is HTTPS through the gateway, and the gateway's handlers are where egress filtering happens. The bus is internal.

Why this matters for cross-repository work: **a node in one repository reaches a node in another without importing it.** The connection is a contract-declared topic resolved at runtime. That is why the import staircase and the runtime graph look nothing alike — and why you cannot infer one from the other.

### Concept 5 — truth is projected, not queried

The concept that most often surprises people arriving from a conventional service architecture.

State is derived, in this order:

```
contract  ->  event on the bus  ->  reducer  ->  projection  ->  read surface
```

- Events on the bus are the durable record of what happened.
- Reducers fold those events into **projections** — materialized read models.
- Read surfaces, including the dashboard, render projections.

**The dashboard renders projections; it does not query services.** This has a direct diagnostic consequence that saves a great deal of time: *if a field is missing in the user interface, the bug is almost always in the projection, not in the display code.* Chase the projection first.

The doctrine behind this: truth is established through contracts, event logs, materialized projections, and deterministic replay — not through a service's in-memory opinion. A capability is proven when it produces durable evidence in those surfaces and replay reproduces it.

### Configuration, briefly

Configuration follows the same contract-first posture. Contracts carry a base declaration; overlays layer environment- and user-specific values onto it by deep merge. Secrets are referenced by name in the contract and resolved from a secrets manager at runtime — the value never appears in the contract.

Environment variables are for **bootstrap only** — enough to find the configuration system. Using them as a general configuration channel is a defect. Where an environment variable is genuinely required, fail fast on absence rather than silently substituting a default: a silent default produces a wrong-environment failure that surfaces far from its cause.

---

## Reading order for a newcomer

1. **This document** — the two axes, and the five runtime concepts.
2. **A contract.** Open any `contract.yaml`. It is the most information-dense file in the system.
3. **The handler it names.** Confirm the typed-request shape for yourself.
4. **The runtime overview** — how the host loads contract-declared nodes and runs them.
5. **The repository-specific architecture document** for whichever repository you are working in.

## Current Versus Target State

Two divergences are worth stating plainly rather than smoothing over, because a reader will encounter both:

- **Handler-shape migration is in flight.** The typed-request core is canonical and enforced for new work, and a growth ratchet prevents the non-conforming population from increasing. A frozen baseline of existing non-conforming nodes is known debt that shrinks only against explicit proof. You will therefore encounter handlers on disk that do not yet match the canonical shape. The shape above is what new work must be, and what the gate enforces.
- **Legacy plugin-style base classes still exist in the implementation layer.** They are migration debt, not architecture. Do not subclass them for new work; the steady-state target is zero.

The honest summary: the three primitives and the four archetypes are settled and enforced. Migrating the existing node population to the canonical handler shape is real, ratcheted, and incomplete.

## Acceptance Criteria

A reader who has absorbed this document can, without assistance:

- Name what each repository owns and state the one-way direction of the import staircase.
- Explain why a protocol found in the core package is not automatically a layering violation.
- Write the canonical handler signature and say what the shared runtime adapter is responsible for.
- Explain why two repositories that never import each other still exchange messages at runtime.
- Given a field missing from the dashboard, name the layer to investigate first.
