---
type: reference
status: current
date: "2026-08-26"
title: "OmniMemory Handler Reuse Matrix"
topics:
  - omnimemory
  - handlers
  - reuse
  - nodes
refs:
  - architecture/omnimemory-four-node-architecture.md
  - guides/omnimemory-pii-handling.md
  - guides/omnimemory-performance-testing.md
---

> **Last verified:** 2026-08-26 — migrated from the `omnimemory` repository. Triage verdict `CORRECT_THEN_MIGRATE`. Verified against live source: all eight named memory nodes exist as `node_*` directories in `omnimemory`, and nearly every cited `omnibase_infra` handler class and module (`HandlerDb`, `HandlerQdrant`, `HandlerFileSystem`, `HandlerGraph`, `HandlerHttp`, `HandlerMcp`, `HandlerManifestPersistence`, the registration-storage and service-discovery handlers, the runtime-tick/heartbeat handlers, the Postgres upsert/deactivate/partial-retry handlers, and the registry/routing/contract-source handlers) is present at the path claimed.
>
> **One correction was applied on migration:** the handler table listed a `HandlerVault` class in a `handler_vault` module. No such class or module exists in `omnibase_infra`. Secrets are fronted by a handler for the platform's managed secret store, exposing read-only operations only (`get_secret`, `list_secrets`, `get_secrets_batch`) — there is no write path through it. The row, the security-posture row, and the credential-management bullets have been rewritten accordingly, and are deliberately written against the capability rather than the vendor product, so a self-hoster can substitute their own secret store.
>
> **Scope note (not a correction):** "Core 8" is the scope this document was written for. `omnimemory` has since grown roughly ten further node directories (intent, document-parse, navigation-history, persona and agent-learning nodes) that this matrix does not cover. The document never claimed to be exhaustive, so this is stated rather than patched.

# Handler Reuse Matrix - Core 8 Nodes

## Overview

This document maps existing handlers from `omnibase_infra` to the Core 8 memory nodes in OmniMemory. The goal is to maximize reuse and minimize new code by leveraging proven infrastructure patterns.

## Contract Version

**ONEX Compliance**: 4.0

## Existing Handlers in omnibase_infra

> **Note**: All paths below are Python module paths within the `omnibase_infra` package.
> Install via PyPI: `uv add omnibase-infra`. Handler classes follow the naming
> convention `Handler<Name>` (e.g., `HandlerDb`, `HandlerQdrant`).

### Core Infrastructure Handlers (`omnibase_infra.handlers`)

| Handler Class | Module | Purpose | Key Operations | Reuse Potential |
|---------------|--------|---------|----------------|-----------------|
| `HandlerDb` | `handler_db` | PostgreSQL database | query, execute | HIGH - storage/retrieval |
| `HandlerQdrant` | `handler_qdrant` | Vector store | store_embedding, query_similar, batch operations | HIGH - semantic search |
| `HandlerFileSystem` | `handler_filesystem` | Secure file I/O | read_file, write_file, list_directory | MEDIUM - persistent storage |
| `HandlerGraph` | `handler_graph` | Graph database (Neo4j/Memgraph) | execute_query, create_node, traverse | HIGH - relationship memory |
| `HandlerHttp` | `handler_http` | HTTP REST client | GET, POST | MEDIUM - external LLM calls |
| *(managed secret store handler — name withheld, see note above)* | *(vendor-specific module)* | Secrets management | read-only: `get_secret`, `list_secrets`, `get_secrets_batch` | LOW - security only |
| `HandlerMcp` | `handler_mcp` | MCP protocol | MCP operations | LOW - agent communication |
| `HandlerManifestPersistence` | `handler_manifest_persistence` | Manifest storage | persist manifests | LOW - specialized |

### Registration Storage Handlers (`omnibase_infra.handlers.registration_storage`)

| Handler Class | Module | Purpose | Reuse Potential |
|---------------|--------|---------|-----------------|
| `HandlerRegistrationStoragePostgres` | `handler_registration_storage_postgres` | PostgreSQL registration | MEDIUM - storage patterns |
| `HandlerRegistrationStorageMock` | `handler_registration_storage_mock` | Mock for testing | HIGH - testing patterns |

### Service Discovery Handlers (`omnibase_infra.handlers.service_discovery`)

| Handler Class | Module | Purpose | Reuse Potential |
|---------------|--------|---------|-----------------|
| `HandlerServiceDiscoveryMock` | `handler_service_discovery_mock` | Mock discovery | HIGH - testing patterns |

### Node-Specific Handlers (`omnibase_infra.nodes.node_registration_orchestrator.handlers`)

| Handler Class | Module | Purpose | Reuse Potential |
|---------------|--------|---------|-----------------|
| `HandlerRuntimeTick` | `handler_runtime_tick` | Timeout detection, lifecycle ticks | HIGH - lifecycle patterns |
| `HandlerNodeHeartbeat` | `handler_node_heartbeat` | Heartbeat processing | MEDIUM - health patterns |
| `HandlerNodeIntrospected` | `handler_node_introspected` | Node introspection | LOW - specialized |
| `HandlerNodeRegistrationAcked` | `handler_node_registration_acked` | Registration acknowledgment | LOW - specialized |

### Registry Effect Handlers (`omnibase_infra.nodes.node_registry_effect.handlers`)

| Handler Class | Module | Purpose | Reuse Potential |
|---------------|--------|---------|-----------------|
| `HandlerPostgresUpsert` | `handler_postgres_upsert` | PostgreSQL upsert | HIGH - storage patterns |
| `HandlerPostgresDeactivate` | `handler_postgres_deactivate` | PostgreSQL deactivation | MEDIUM - lifecycle |
| `HandlerPartialRetry` | `handler_partial_retry` | Retry logic | HIGH - resilience patterns |

### Runtime Handlers (`omnibase_infra.runtime`)

| Handler Class | Module | Purpose | Reuse Potential |
|---------------|--------|---------|-----------------|
| `HandlerRegistry` | `handler_registry` | Handler registry | HIGH - registry patterns |
| `HandlerRoutingLoader` | `handler_routing_loader` | Route loading | MEDIUM - routing |
| `HandlerContractSource` | `handler_contract_source` | Contract loading | MEDIUM - contracts |
| `HandlerPluginLoader` | `handler_plugin_loader` | Plugin loading | LOW - specialized |

---

## Core 8 Node Handler Mapping

### EFFECT Nodes

| Memory Node | Operation | Reuse Strategy | Source Handler Class | Notes |
|-------------|-----------|----------------|---------------------|-------|
| **memory_storage_effect** | store | DIRECT | `HandlerDb` | PostgreSQL for persistent storage |
| memory_storage_effect | store_vector | DIRECT | `HandlerQdrant` | Vector embeddings storage |
| memory_storage_effect | store_file | DIRECT | `HandlerFileSystem` | File-based persistence |
| memory_storage_effect | retrieve | DIRECT | `HandlerDb` | SQL queries for retrieval |
| memory_storage_effect | retrieve_vector | DIRECT | `HandlerQdrant` | Vector retrieval by ID |
| **memory_retrieval_effect** | search | DIRECT | `HandlerQdrant` | `query_similar()` for semantic search |
| memory_retrieval_effect | search_graph | ADAPTER | `HandlerGraph` | `traverse()` for relationship search |
| memory_retrieval_effect | search_text | ADAPTER | `HandlerDb` | Full-text SQL search |

### COMPUTE Nodes

| Memory Node | Operation | Reuse Strategy | Source Handler Class | Notes |
|-------------|-----------|----------------|---------------------|-------|
| **semantic_analyzer_compute** | analyze | NEW | - | New handler for semantic analysis |
| semantic_analyzer_compute | embed | ADAPTER | `HandlerHttp` | Call external embedding service |
| semantic_analyzer_compute | extract_entities | NEW | - | NLP entity extraction |
| **similarity_compute** | compare | ADAPTER | `HandlerQdrant` | Leverage `query_similar()` logic |
| similarity_compute | cosine_distance | NEW | - | Pure compute - no I/O |
| similarity_compute | euclidean_distance | NEW | - | Pure compute - no I/O |

### REDUCER Nodes

| Memory Node | Operation | Reuse Strategy | Source Handler Class | Notes |
|-------------|-----------|----------------|---------------------|-------|
| **memory_consolidator_reducer** | consolidate | ADAPTER | `HandlerDb` | SQL aggregations + custom logic |
| memory_consolidator_reducer | deduplicate | ADAPTER | `HandlerQdrant` | Vector similarity for dedup |
| memory_consolidator_reducer | merge | NEW | - | Memory merging logic |
| **statistics_reducer** | aggregate | ADAPTER | `HandlerDb` | SQL aggregations (COUNT, SUM, AVG) |
| statistics_reducer | compute_metrics | NEW | - | Memory usage metrics |
| statistics_reducer | summarize | NEW | - | Statistical summaries |

### ORCHESTRATOR Nodes

| Memory Node | Operation | Reuse Strategy | Source Handler Class | Notes |
|-------------|-----------|----------------|---------------------|-------|
| **memory_lifecycle_orchestrator** | coordinate | ADAPTER | `HandlerRuntimeTick` | Tick-based lifecycle events |
| memory_lifecycle_orchestrator | expire | ADAPTER | `HandlerPostgresDeactivate` | Deactivation patterns |
| memory_lifecycle_orchestrator | promote | NEW | - | Memory tier promotion |
| memory_lifecycle_orchestrator | archive | ADAPTER | `HandlerFileSystem` | Archive to cold storage |
| **agent_coordinator_orchestrator** | broadcast | ADAPTER | `HandlerHttp` | HTTP broadcast to agents |
| agent_coordinator_orchestrator | subscribe | NEW | - | Subscription management |
| agent_coordinator_orchestrator | notify | ADAPTER | `HandlerHttp` | Webhook notifications |

---

## Handler Reuse Strategy Summary

### Strategy Definitions

- **DIRECT**: Use handler as-is with minimal wrapping
- **ADAPTER**: Create thin adapter layer to transform inputs/outputs
- **NEW**: Implement new handler (no suitable existing handler)

### Reuse Statistics

| Strategy | Count | Percentage |
|----------|-------|------------|
| DIRECT | 10 | 40% |
| ADAPTER | 11 | 44% |
| NEW | 4 | 16% |

---

## Security Considerations

When reusing handlers from `omnibase_infra`, security must be addressed at multiple layers. Each handler type presents distinct security challenges that require specific mitigations.

### Input Validation Requirements

All handlers must validate inputs before processing. Validation requirements vary by handler type:

| Handler Type | Validation Requirements | Implementation |
|--------------|------------------------|----------------|
| **Database (handler_db.py)** | Parameterized queries only, no string interpolation; validate column/table names against allowlist; enforce maximum query complexity | Use SQLAlchemy parameterized queries; reject raw SQL strings |
| **Vector Store (handler_qdrant.py)** | Validate embedding dimensions match schema; sanitize metadata keys/values; enforce payload size limits | Check vector dimensions before storage; limit metadata to predefined fields |
| **Filesystem (handler_filesystem.py)** | Path whitelisting (already implemented); validate file extensions; enforce size limits; reject symlinks to sensitive paths | Use `os.path.realpath()` and compare against whitelist |
| **HTTP (handler_http.py)** | Validate URLs against allowlist; sanitize request headers; enforce response size limits; validate SSL certificates | Maintain URL allowlist for LLM endpoints; reject self-signed certs in production |
| **Graph (handler_graph.py)** | Validate Cypher/Gremlin query structure; parameterize all user inputs; limit traversal depth | Use parameterized queries; enforce `max_depth` parameter |

### Data Sanitization at Boundaries

Memory content flowing through handlers must be sanitized to prevent data leakage and injection attacks.

#### PII Detection Integration

Use the existing `PIIDetector` utility at `src/omnimemory/utils/pii_detector.py` for content sanitization.

> **Documentation**: See [OmniMemory PII Handling](../guides/omnimemory-pii-handling.md) for comprehensive integration patterns, sensitivity levels, configuration options, and best practices.

```python
from omnimemory.utils.pii_detector import PIIDetector, PIIDetectorConfig

# Configure PII detection for memory storage
pii_config = PIIDetectorConfig(
    high_confidence=0.98,
    enable_context_analysis=True,
    max_text_length=50000
)
detector = PIIDetector(config=pii_config)

# Sanitize before storage
async def store_memory_securely(content: str, handler: HandlerDb) -> str:
    result = detector.detect_pii(content, sensitivity_level="high")
    if result.has_pii:
        # Log detection (without PII) and use sanitized content
        logger.warning(f"PII detected: types={result.pii_types_detected}")
        content = result.sanitized_content
    return await handler.execute(insert_query, {"content": content})
```

#### Sanitization by Handler Type

| Handler | Sanitization Layer | Implementation |
|---------|-------------------|----------------|
| **handler_db.py** | SQL injection prevention | Parameterized queries; escape special characters; validate input types |
| **handler_qdrant.py** | Metadata sanitization | Strip HTML/scripts from metadata; validate JSON structure; limit string lengths |
| **handler_filesystem.py** | Path traversal prevention | Already implements path whitelisting; additionally validate no `..` sequences after normalization |
| **handler_http.py** | Request/response sanitization | Sanitize headers; validate JSON structure; strip sensitive headers from logs |
| **handler_graph.py** | Injection prevention | Parameterize all Cypher queries; validate node/edge labels against allowlist |

#### Boundary Enforcement

```
[User Input] → [PII Detection] → [Input Validation] → [Handler] → [Output Sanitization] → [Response]
                     ↓                   ↓                              ↓
              Log (sanitized)    Reject invalid           Strip internal metadata
```

### Circuit Breaker Timeout Configurations

Each handler type requires specific timeout configurations based on operation characteristics. Use `MixinAsyncCircuitBreaker` from `omnibase_infra`.

| Handler | Operation | Recommended Timeout | Circuit Breaker Config | Rationale |
|---------|-----------|---------------------|------------------------|-----------|
| **handler_db.py** | Simple query | 5s | failures=3, reset=30s | Fast local queries |
| **handler_db.py** | Complex aggregation | 30s | failures=5, reset=60s | Allows for large dataset processing |
| **handler_qdrant.py** | Single vector query | 2s | failures=3, reset=15s | Vector search is fast |
| **handler_qdrant.py** | Batch operations | 30s | failures=3, reset=30s | Batch may involve thousands of vectors |
| **handler_filesystem.py** | Read/write | 10s | failures=5, reset=30s | I/O varies with file size |
| **handler_http.py** | LLM embedding call | 60s | failures=2, reset=120s | External services may be slow |
| **handler_http.py** | Health check | 5s | failures=3, reset=30s | Should be fast |
| **handler_graph.py** | Simple traversal | 5s | failures=3, reset=30s | Shallow traversals |
| **handler_graph.py** | Deep traversal | 30s | failures=3, reset=60s | Deep graph queries |

**Configuration Example**:

```python
from omnibase_infra.mixins.mixin_async_circuit_breaker import MixinAsyncCircuitBreaker

class MemoryStorageHandler(MixinAsyncCircuitBreaker):
    def __init__(self):
        super().__init__(
            failure_threshold=3,
            reset_timeout_seconds=30,
            half_open_max_calls=1
        )

    async def store(self, data: MemoryData) -> str:
        async with self.circuit_breaker():
            return await self._db_handler.execute(
                query=self._insert_query,
                params=data.model_dump(),
                timeout=5.0  # Per-operation timeout
            )
```

### Error Handling

Secure error handling prevents information disclosure while maintaining debuggability.

#### Error Message Guidelines

| Context | Allowed in Response | Prohibited in Response |
|---------|---------------------|------------------------|
| **User-facing errors** | Generic error type, request ID, retry guidance | Stack traces, SQL queries, internal paths, connection strings |
| **Internal logs** | Full stack traces, sanitized query details, timing | Raw credentials, full PII, encryption keys |
| **Metrics/alerts** | Error counts, latency percentiles, error categories | Individual error content, user data |

#### Secure Error Pattern

```python
from omnibase_infra.models.model_infra_error_context import ModelInfraErrorContext

class SecureMemoryError(Exception):
    """Base exception that sanitizes error details for external consumption."""

    def __init__(self, message: str, internal_details: str, correlation_id: str):
        self.external_message = message  # Safe for users
        self.internal_details = internal_details  # For logs only
        self.correlation_id = correlation_id
        super().__init__(message)

    def to_user_response(self) -> dict:
        return {
            "error": self.external_message,
            "correlation_id": self.correlation_id,
            "retry_after": 30  # Guidance, not internals
        }

# Usage in handlers
try:
    result = await handler.execute(query)
except DatabaseError as e:
    # Log full details internally
    logger.error(f"Database error: {e}", extra={"query": sanitize_query(query)})
    # Return sanitized error externally
    raise SecureMemoryError(
        message="Memory storage temporarily unavailable",
        internal_details=str(e),
        correlation_id=ctx.correlation_id
    )
```

#### Error Logging with PII Protection

```python
def sanitize_for_logging(data: dict) -> dict:
    """Remove sensitive fields before logging."""
    sensitive_keys = {"password", "token", "api_key", "secret", "ssn", "credit_card"}
    return {
        k: "[REDACTED]" if k.lower() in sensitive_keys else v
        for k, v in data.items()
    }
```

### Authentication and Authorization

Handler access must be controlled at multiple layers.

#### Handler Access Control Matrix

| Handler | Auth Requirement | Authorization Model | Notes |
|---------|------------------|---------------------|-------|
| **handler_db.py** | Connection credentials | Role-based (PostgreSQL roles) | Use least-privilege DB users |
| **handler_qdrant.py** | API key | Collection-level ACLs | Separate keys per collection |
| **handler_filesystem.py** | Process permissions | Path whitelist + Unix permissions | Run with minimal filesystem access |
| **handler_http.py** | Bearer tokens / API keys | Endpoint-specific | Rotate keys; use short-lived tokens |
| **handler_graph.py** | Connection credentials | Label-based access control | Restrict node/edge type access |
| **secret-store handler** | Machine-identity client id + client secret | Policy-based, per-environment scopes | Use a dedicated machine identity per service; never a shared human credential |

#### Implementation Pattern

```python
from dataclasses import dataclass
from enum import Enum

class HandlerPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

@dataclass
class HandlerAuthContext:
    """Authentication context passed to all handler operations."""
    principal_id: str  # User or service ID
    permissions: set[HandlerPermission]
    correlation_id: str
    tenant_id: str | None = None  # For multi-tenant deployments

class SecureHandler:
    def __init__(self, required_permission: HandlerPermission):
        self._required_permission = required_permission

    def _check_authorization(self, ctx: HandlerAuthContext) -> None:
        if self._required_permission not in ctx.permissions:
            raise AuthorizationError(
                f"Permission {self._required_permission} required",
                correlation_id=ctx.correlation_id
            )

    async def execute(self, ctx: HandlerAuthContext, **kwargs):
        self._check_authorization(ctx)
        # Proceed with operation
```

#### Credential Management

- **Never hardcode credentials** - Resolve them through the secret-store handler, or through environment variables populated from it
- **Rotate credentials regularly** - Implement automated rotation in the secret store, not in application code
- **Audit access** - Log all handler invocations with principal ID (not credentials)
- **Use service accounts** - Avoid shared credentials between services

### Security Checklist for Handler Integration

Before integrating any handler from `omnibase_infra`, verify:

- [ ] Input validation implemented for all user-provided parameters
- [ ] PII detection integrated at data ingestion points
- [ ] Circuit breaker configured with appropriate timeouts
- [ ] Error messages sanitized (no internal details exposed)
- [ ] Credentials sourced from the secret store or a secure environment
- [ ] Access control enforced at handler level
- [ ] Audit logging enabled with sanitized payloads
- [ ] SQL/Cypher queries use parameterization (no string interpolation)
- [ ] File paths validated against whitelist
- [ ] HTTP endpoints validated against allowlist

---

## Recommendations

### High-Priority Reuse (DIRECT)

1. **`HandlerDb`** (`omnibase_infra.handlers.handler_db`) - Core storage operations
   - Proven asyncpg implementation with connection pooling
   - Circuit breaker pattern already implemented
   - Supports parameterized queries for security

2. **`HandlerQdrant`** (`omnibase_infra.handlers.handler_qdrant`) - Vector operations
   - Full ProtocolVectorStoreHandler implementation
   - Batch operations, metadata filtering, similarity search
   - Health check caching

3. **`HandlerFileSystem`** (`omnibase_infra.handlers.handler_filesystem`) - File persistence
   - Path whitelisting for security
   - Size limits to prevent DoS
   - Symlink protection

### Medium-Priority Adapters (ADAPTER)

1. **`HandlerGraph`** (`omnibase_infra.handlers.handler_graph`) - Relationship memory
   - Create memory-specific adapter for graph traversal
   - Useful for "memories related to X" queries

2. **`HandlerHttp`** (`omnibase_infra.handlers.handler_http`) - External services
   - Wrap for LLM embedding calls
   - Wrap for agent broadcast

3. **`HandlerRuntimeTick`** (`omnibase_infra.nodes.node_registration_orchestrator.handlers.handler_runtime_tick`) - Lifecycle patterns
   - Adapt tick detection for memory expiration
   - Reuse projection query patterns

### New Handlers Required (NEW)

1. **`HandlerSemanticCompute`** (new: `omnimemory.handlers.handler_semantic_compute`) - Pure semantic analysis
   - Entity extraction
   - Topic modeling
   - Sentiment analysis

2. **`HandlerSimilarityCompute`** (new: `omnimemory.handlers.handler_similarity_compute`) - Pure vector math
   - Distance calculations
   - Threshold comparisons

3. **`HandlerMemoryMerge`** (new: `omnimemory.handlers.handler_memory_merge`) - Memory consolidation
   - Deduplication logic
   - Merge strategies

4. **`HandlerSubscription`** (new: `omnimemory.handlers.handler_subscription`) - Agent subscriptions
   - Topic-based subscriptions
   - Memory change notifications

---

## Implementation Priority

### Phase 1: Foundation (Completed)
1. Import `HandlerDb` for storage
2. Import `HandlerQdrant` for vectors
3. Import `HandlerFileSystem` for persistence
4. Create `memory_storage_effect` node using these handlers

### Phase 2: Search & Retrieval (Completed)
1. Import `HandlerGraph` for relationships
2. Create `memory_retrieval_effect` with adapters
3. Implement basic similarity compute

### Phase 3: Intelligence (Completed)
1. Create `HandlerSemanticCompute`
2. Adapt `HandlerHttp` for LLM calls
3. Implement `HandlerSimilarityCompute`

### Phase 4: Lifecycle & Coordination (Scaffolded - Implementation In Progress)
1. Adapt `HandlerRuntimeTick` for lifecycle
2. Create memory consolidator reducer (scaffolded, implementation in progress)
3. Implement agent coordinator orchestrator (in progress)

---

## Pattern Reuse from omnibase_infra

### Mixins to Reuse
- `MixinAsyncCircuitBreaker` - Fault tolerance
- `MixinEnvelopeExtraction` - Envelope parsing

### Error Patterns to Reuse
- `ModelInfraErrorContext` - Structured error context
- `InfraConnectionError`, `InfraTimeoutError` - Typed errors

### Model Patterns to Reuse
- `ModelHandlerOutput` - Standardized output wrapping
- Health check caching patterns
- Correlation ID propagation

---

## File Locations

**Source Handlers**: `omnibase-infra` package (PyPI) - handlers module

**Target Nodes**: `src/omnimemory/nodes/` (this repository)

### Installation

Install the `omnibase-infra` package from PyPI:

```bash
# Add as development dependency
uv add --group dev omnibase-infra

# Or add as a regular dependency
uv add omnibase-infra
```

> **Naming Convention**: The PyPI package name uses hyphens (`omnibase-infra`) while
> Python imports use underscores (`omnibase_infra`). This is standard Python packaging
> convention (PEP 503 normalizes hyphens to underscores for imports).

**Recommended Import Strategy**:
```python
# Import from omnibase_infra module (installed via omnibase-infra package)
from omnibase_infra.handlers.handler_db import HandlerDb
from omnibase_infra.handlers.handler_qdrant import HandlerQdrant
from omnibase_infra.handlers.handler_filesystem import HandlerFileSystem

# Create memory-specific adapters
class MemoryStorageAdapter:
    def __init__(self, db_handler: HandlerDb, vector_handler: HandlerQdrant):
        self._db = db_handler
        self._vector = vector_handler
```

---

## Health Status Aggregation

### Import Path

Health status enumeration is provided by `omnibase_core`:

```python
from omnibase_core.enums import EnumHealthStatus
```

### Enum Values

| Value | Description | Aggregation Priority |
|-------|-------------|---------------------|
| `HEALTHY` | Service/node is fully operational | 4 (lowest concern) |
| `DEGRADED` | Service/node is operational but with reduced capacity | 3 |
| `UNHEALTHY` | Service/node is not operational | 2 |
| `UNKNOWN` | Service/node status cannot be determined | 1 (highest concern) |

### Aggregation Rules

When aggregating health status across multiple services or nodes:

1. **Worst-case aggregation**: Overall status equals the worst individual status
2. **Priority order**: `UNKNOWN` > `UNHEALTHY` > `DEGRADED` > `HEALTHY`
3. **Scoring**: Health scores (0.0-1.0) can be averaged for composite health metrics

```python
from omnibase_core.enums import EnumHealthStatus

def aggregate_health_status(statuses: list[EnumHealthStatus]) -> EnumHealthStatus:
    """Aggregate multiple health statuses using worst-case rule."""
    priority = {
        EnumHealthStatus.UNKNOWN: 1,
        EnumHealthStatus.UNHEALTHY: 2,
        EnumHealthStatus.DEGRADED: 3,
        EnumHealthStatus.HEALTHY: 4,
    }
    if not statuses:
        return EnumHealthStatus.UNKNOWN
    return min(statuses, key=lambda s: priority.get(s, 0))
```

### Usage in Models

Health status is used in:

| Model | Field | Purpose |
|-------|-------|---------|
| `ModelServiceHealth` | `status` | Individual service health |
| `ModelServiceRegistry` | `status` | Registered service status |
| `ModelSystemHealth` | `overall_status` | Aggregated system health |

### Health Monitoring Integration

Handlers should report health status via standardized patterns:

```python
from omnibase_core.enums import EnumHealthStatus
from omnimemory.models.service import ModelServiceHealth

class HandlerHealthReport:
    """Standard health reporting for handlers."""

    async def get_health(self) -> ModelServiceHealth:
        """Return handler health status."""
        try:
            # Perform health check logic
            is_healthy = await self._check_dependencies()
            return ModelServiceHealth(
                service_id=self.service_id,
                service_name=self.service_name,
                status=EnumHealthStatus.HEALTHY if is_healthy else EnumHealthStatus.DEGRADED,
                is_healthy=is_healthy,
                # ... other fields
            )
        except Exception:
            return ModelServiceHealth(
                service_id=self.service_id,
                service_name=self.service_name,
                status=EnumHealthStatus.UNHEALTHY,
                is_healthy=False,
                # ... other fields
            )
```

---

## Contract Layout (ONEX Canonical Structure)

### Contract Schema Version

All ONEX contracts include a `contract_version` field at the root level:

```yaml
# Contract schema version - tracks the contract format itself
contract_version: "1.0.0"
```

**Versioning Scheme**:
- **MAJOR**: Breaking changes to contract schema structure
- **MINOR**: Backwards-compatible additions to schema
- **PATCH**: Documentation or cosmetic changes only

### Node Contract Structure (EFFECT/COMPUTE/REDUCER/ORCHESTRATOR)

Node contracts follow this canonical structure:

```yaml
# === CONTRACT METADATA ===
contract_version: "1.0.0"

# === REQUIRED ROOT FIELDS ===
name: "node_name_type"           # Format: <name>_<type> (e.g., memory_storage_effect)
version: {major: 0, minor: 1, patch: 0}
description: "Node description"
node_type: "EFFECT"              # One of: EFFECT, COMPUTE, REDUCER, ORCHESTRATOR
input_model: "InputModelName"    # Pydantic model class name
output_model: "OutputModelName"  # Pydantic model class name

# === IO OPERATIONS (Required for EFFECT nodes) ===
io_operations:
  - operation_type: "database_write"
    atomic: true
    timeout_seconds: 30
    validation_enabled: true

# === NODE CONFIGURATION ===
tool_specification:
  tool_name: "node_tool_name"
  version: {major: 0, minor: 1, patch: 0}
  description: "Tool description"
  main_tool_class: "NodeClassName"
  container_injection: "ONEXContainer"
  business_logic_pattern: "effect"  # Matches node_type

# === SERVICE CONFIGURATION ===
service_configuration:
  is_persistent_service: false
  requires_external_dependencies: true

# === INPUT/OUTPUT STATE ===
input_state:
  object_type: "object"
  required: ["field1", "field2"]
  optional: ["field3"]

output_state:
  object_type: "object"
  required: ["success", "result"]
  optional: ["error_message"]

# === ACTIONS ===
actions:
  - name: "action_name"
    description: "Action description"
    inputs: ["input1", "input2"]
    outputs: ["output1"]

# === DEPENDENCIES ===
dependencies:
  - name: dependency_name
    dependency_type: service     # service, protocol, or library
    description: "Dependency description"

# === PERFORMANCE ===
performance:
  max_response_time_ms: 100

# === EVENT TYPE CONFIGURATION ===
event_type:
  version: {major: 1, minor: 0, patch: 0}
  primary_events: ["event1", "event2"]
  event_categories: ["category1"]
  publish_events: true
  subscribe_events: false
  event_routing: "routing_key"

# === VALIDATION RULES ===
validation_rules:
  strict_typing_enabled: true
  input_validation_enabled: true
  output_validation_enabled: true
  performance_validation_enabled: true

# === TAGS ===
tags:
  - tag1
  - tag2
```

### Project Contract Structure

Project-level contracts define the overall architecture:

```yaml
# Contract schema version
contract_version: "1.0.0"

contract:
  name: project_name
  version: 1.0.0
  description: "Project description"
  architecture:
    pattern: onex_4_node
    nodes:
      effect:
        description: "Effect nodes description"
        responsibilities: [...]
      compute:
        description: "Compute nodes description"
        responsibilities: [...]
      reducer:
        description: "Reducer nodes description"
        responsibilities: [...]
      orchestrator:
        description: "Orchestrator nodes description"
        responsibilities: [...]

protocols:
  protocol_name:
    description: "Protocol description"
    methods: [...]

schemas:
  schema_name:
    description: "Schema description"
    fields: [...]

error_handling:
  strategy: monadic_result
  error_codes: [...]
  recovery:
    retry_policy: {...}
    circuit_breaker: {...}
```

### Contract Validation

Contracts are validated against:

1. **Schema compliance**: Required fields present and correctly typed
2. **Version consistency**: Contract version matches schema expectations
3. **Dependency resolution**: All declared dependencies are available
4. **ONEX compliance**: Node type matches business logic pattern

---

---

## Related Documentation

- [OmniMemory PII Handling](../guides/omnimemory-pii-handling.md) — PII detection integration patterns
- [OmniMemory Performance Testing](../guides/omnimemory-performance-testing.md) — performance benchmarks and targets
- [OmniMemory Four-Node Architecture](../architecture/omnimemory-four-node-architecture.md) — the node archetypes these handlers are wired into
