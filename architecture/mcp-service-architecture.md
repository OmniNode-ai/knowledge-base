---
type: architecture
status: accepted
date: "2026-07-21"
title: "MCP Service Architecture"
topics: [omnibase-infra, mcp, service]
refs: []
---

# MCP Service Architecture

> **Status**: Current | **Last Updated**: 2026-02-19

The Model Context Protocol (MCP) integration exposes ONEX nodes as callable tools that AI agents (such as Claude) can discover and invoke. This document covers the full stack: the handler that owns the server lifecycle, the adapter that translates ONEX contracts into MCP tool definitions, the streamable HTTP transport layer, and how the pieces wire together at runtime.

---

## Table of Contents

1. Purpose and Scope
2. Component Inventory
3. Request and Response Flow
4. HandlerMCP — Server Lifecycle
5. ONEXToMCPAdapter — Contract Translation
6. TransportMCPStreamableHttp — ASGI Layer
7. MCPServerLifecycle — Service Composition Root
8. Security Model
9. Configuration
10. Operations: Supported Envelope Operations
11. Current Limitations and Roadmap
12. See Also

---

## Purpose and Scope

ONEX nodes are internal infrastructure primitives. The MCP integration bridges these nodes to the external world of AI agents. An AI agent that speaks MCP (such as an Anthropic Claude tool-use session) can query which ONEX operations are available, obtain their JSON Schema parameter definitions, and invoke them — without knowing anything about ONEX envelopes, contracts, or the Kafka event bus.

The integration is currently in MVP state. Tool discovery is manual (via `register_node_as_tool()`). Automatic discovery from the node registry via a `mcp_enabled: true` contract flag is planned.

---

## Component Inventory

| Component | Location | Role |
|-----------|----------|------|
| `HandlerMCP` | `handlers/handler_mcp.py` | Top-level handler; owns uvicorn lifecycle, circuit breaker, and operation routing |
| `ONEXToMCPAdapter` | `handlers/mcp/adapter_onex_to_mcp.py` | Converts ONEX contracts/Pydantic models to `MCPToolDefinition` structs |
| `TransportMCPStreamableHttp` | `handlers/mcp/transport_streamable_http.py` | Wraps `FastMCP` + Starlette; creates the ASGI application |
| `ProtocolToolExecutor` | `handlers/mcp/protocols.py` | Protocol for pluggable tool execution backends |
| `MCPServerLifecycle` | `services/mcp/mcp_server_lifecycle.py` | Composition root: wires registry, discovery, sync, and executor |
| `ServiceMCPToolRegistry` | `services/mcp/service_mcp_tool_registry.py` | In-memory cache of active tool definitions |
| `ServiceMCPToolDiscovery` | `services/mcp/service_mcp_tool_discovery.py` | Consul scanner that finds MCP-enabled orchestrators on cold start |
| `ServiceMCPToolSync` | `services/mcp/service_mcp_tool_sync.py` | Kafka listener for hot-reload of tool definitions at runtime |
| `AdapterONEXToolExecution` | `adapters/adapter_onex_tool_execution.py` | Bridges MCP tool calls to the ONEX dispatcher |
| `ModelMcpHandlerConfig` | `handlers/models/mcp/model_mcp_handler_config.py` | Pydantic config for host, port, path, timeouts, and max tools |

---

## Request and Response Flow

```text
AI Agent (MCP client)
        |
        | HTTP POST /mcp   (Streamable HTTP, MCP wire format)
        v
+--------------------+
|  uvicorn server    |  <-- started inside HandlerMCP.initialize()
|  (Starlette ASGI)  |
+--------------------+
        |
        | Route: GET /health   -> JSON health status
        | Route: GET /mcp/tools -> JSON tool list
        | Route: POST /mcp     -> FastMCP handler
        v
+--------------------+
|    FastMCP         |  <-- from mcp.server.fastmcp (official MCP SDK)
|  (MCP protocol)   |
+--------------------+
        |
        | per-tool handler (onex_tool_{name})
        v
+------------------------+
|  ProtocolToolExecutor  |  <-- AdapterONEXToolExecution in integrated mode
+------------------------+
        |
        | async execute(tool, arguments, correlation_id)
        v
+---------------------------+
|  ONEX Orchestrator Node   |  <-- via ONEX dispatcher/envelope system
|  (local or via Kafka)     |
+---------------------------+
        |
        | ModelHandlerOutput
        v
+------------------+
|  MCP response    |  <-- JSON, returned to AI agent
+------------------+
```

### Envelope-based invocation (HandlerMCP.execute)

When `HandlerMCP` is invoked through the ONEX envelope system (rather than directly via HTTP), the flow is:

```text
ONEX runtime envelope
        |
        v
HandlerMCP.execute(envelope: dict)
        |
        +-- mcp.list_tools  --> _handle_list_tools()  --> ModelHandlerOutput.for_compute()
        |
        +-- mcp.call_tool   --> _handle_call_tool()
        |       |
        |       +-- circuit breaker check
        |       +-- ServiceMCPToolRegistry.get_tool(name)
        |       +-- AdapterONEXToolExecution.execute(tool, args, cid)
        |       +-- ModelMcpToolResult
        |       --> ModelHandlerOutput.for_compute()
        |
        +-- mcp.describe    --> _handle_describe() --> metadata dict
```

---

## HandlerMCP — Server Lifecycle

`HandlerMCP` is an INFRA_HANDLER/EFFECT handler that manages the full uvicorn server lifecycle from within the ONEX handler pattern. It mixes in `MixinAsyncCircuitBreaker` and `MixinEnvelopeExtraction`.

### Initialization sequence

```text
HandlerMCP.initialize(config: dict) is called
        |
        1. Parse config via ModelMcpHandlerConfig (Pydantic, strict — no fallbacks)
        2. _init_circuit_breaker(threshold=5, reset_timeout=60.0, transport=MCP)
        3. If skip_server=False (production mode):
           a. Validate required keys: consul_host, consul_port, kafka_enabled, dev_mode
           b. Create ModelMCPServerConfig
           c. Create MCPServerLifecycle(container, config, bus=None)
           d. await lifecycle.start()           -- cold-start Consul discovery
           e. Build Starlette app with /health and /mcp/tools routes
           f. Create uvicorn.Config + uvicorn.Server
           g. asyncio.create_task(server.serve())  -- server runs in background
           h. _wait_for_server_ready() via TCP polling (default 2s timeout)
        4. self._initialized = True
```

### Shutdown

Shutdown is bounded — it never hangs indefinitely:

```text
HandlerMCP.shutdown()
        |
        1. Signal uvicorn: server.should_exit = True
        2. asyncio.wait_for(server_task, timeout=5.0s)  -- graceful
        3. If timeout: server_task.cancel()
                       asyncio.wait_for(cancel, timeout=1.0s)  -- forced
        4. lifecycle.shutdown()   -- cleans registry, discovery, sync
        5. Clear all state
```

### Health check

`HandlerMCP.health_check()` returns:
- `not_initialized` — handler was never initialized
- `server_task_missing` — server task reference lost
- `server_cancelled` / `server_crashed` / `server_exited` — task ended unexpectedly
- `healthy: true` — task still running, includes `tool_count` and `uptime_seconds`

---

## ONEXToMCPAdapter — Contract Translation

`ONEXToMCPAdapter` translates between the ONEX world and the MCP tool representation. Its two main jobs:

**1. Tool registration (manual, current MVP)**

```python
adapter = ONEXToMCPAdapter(node_executor=executor, container=container)

tool = await adapter.register_node_as_tool(
    node_name="node_compute_hash",
    description="Compute a SHA-256 hash of input data",
    parameters=[
        MCPToolParameter(
            name="input",
            parameter_type="string",
            description="Data to hash",
            required=True,
        )
    ],
    version="1.0.0",
    tags=["compute", "crypto"],
)
```

Tools are stored in `_tool_cache: dict[str, MCPToolDefinition]`. Tag-based filtering is available via `discover_tools(tags=["compute"])`.

**2. Schema generation from Pydantic models**

```python
schema = ONEXToMCPAdapter.pydantic_to_json_schema(MyInputModel)
params = ONEXToMCPAdapter.extract_parameters_from_schema(schema)
```

`pydantic_to_json_schema` calls `model_json_schema()` on any Pydantic `BaseModel` subclass. If the class is not a Pydantic model, it returns `{"type": "object"}` (soft failure) unless `raise_on_error=True` is passed.

`extract_parameters_from_schema` converts the JSON Schema `properties` dict into `MCPToolParameter` instances, honoring the `required` list and handling union types by taking the first non-null type.

**3. Tool invocation**

`invoke_tool(tool_name, arguments, correlation_id)` dispatches through `AdapterONEXToolExecution.execute()` — full envelope building, correlation ID threading, per-tool timeout enforcement, and circuit breaker protection. It is not a placeholder.

---

## TransportMCPStreamableHttp — ASGI Layer

`TransportMCPStreamableHttp` wraps the official MCP Python SDK's `FastMCP` to create a Starlette ASGI application.

```python
config = ModelMcpHandlerConfig(host="0.0.0.0", port=8090, path="/mcp")
transport = TransportMCPStreamableHttp(config)

# Create app (usable standalone or mounted into existing app)
app = transport.create_app(tools, tool_executor)

# Or start full server
await transport.start(tools, tool_executor)

# Graceful shutdown (non-blocking signal; await start() to confirm done)
await transport.stop()
```

### Tool registration with FastMCP

For each `ProtocolMCPToolDefinition`, a uniquely-named handler function is generated:

```python
def _make_tool_handler(name: str) -> Callable:
    def handler(**kwargs: object) -> object:
        return tool_executor(name, kwargs)
    handler.__name__ = f"onex_tool_{name}"
    handler.__qualname__ = f"TransportMCPStreamableHttp.onex_tool_{name}"
    return handler
```

Unique function names prevent naming collisions in FastMCP's internal registry across MCP SDK versions.

### Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `host` | `"0.0.0.0"` | Bind address |
| `port` | `8090` | Bind port |
| `path` | `"/mcp"` | URL path where MCP server is mounted |
| `stateless` | `True` | Enables stateless HTTP mode for horizontal scaling |
| `json_response` | `True` | Returns JSON (not SSE) for broader client compatibility |
| `timeout_seconds` | `30` | Per-tool execution timeout |
| `max_tools` | `100` | Maximum registered tools before rejecting new registrations |

---

## MCPServerLifecycle — Service Composition Root

`MCPServerLifecycle` is the composition root for all MCP services, called by `HandlerMCP.initialize()`.

```
MCPServerLifecycle.start()
        |
        1. Create ServiceMCPToolRegistry  (in-memory tool cache)
        2. Create ServiceMCPToolDiscovery (Consul scanner)
        3. Create AdapterONEXToolExecution (dispatch bridge)
        4. Cold start: scan Consul for MCP-enabled orchestrators
           --> ServiceMCPToolDiscovery.discover()
           --> populate ServiceMCPToolRegistry
        5. If kafka_enabled=True:
           --> Create ServiceMCPToolSync (Kafka listener)
           --> Start Kafka subscription for hot-reload events
        6. Store references: .registry, .executor, .discovery, .sync
```

After `start()`, `HandlerMCP` retrieves `lifecycle.registry` and `lifecycle.executor` to wire into integrated execution mode.

---

## Security Model

### Authentication (MVP limitation)

Authentication is NOT implemented in the current release. The MCP HTTP endpoint is open. For production deployments:

- Deploy behind an API gateway with authentication enforcement
- Use VPC/firewall rules to restrict which clients can reach the MCP port
- Restrict to trusted internal services only

Authentication via Bearer token is planned.

### Circuit breaker

`HandlerMCP` uses `MixinAsyncCircuitBreaker` configured for the MCP transport:

- **Threshold**: 5 consecutive failures open the circuit
- **Reset timeout**: 60 seconds before transitioning to HALF_OPEN
- **Scope**: Applied to tool execution (`_execute_tool`), not to server startup

### Tool registry limits

`HandlerMCP.register_tool()` enforces `max_tools` (default 100). When the limit is reached, the method returns `False` without raising. Callers must check the return value.

### Error sanitization

`ProtocolToolExecutor` implementations must never include raw argument values in error messages (arguments may contain secrets). Only tool names, operation names, correlation IDs, and error codes are safe to include.

---

## Configuration

All configuration is required with no hardcoded defaults (per the `.env` is the single source of truth rule). The handler will raise `ProtocolConfigurationError` if any required key is absent.

```python
# Passed to HandlerMCP.initialize(config=...)
config = {
    "host": "0.0.0.0",           # MCP server bind address
    "port": 8090,                 # MCP server port
    "path": "/mcp",               # MCP mount path
    "stateless": True,            # Stateless HTTP mode
    "json_response": True,        # JSON response format
    "timeout_seconds": 30.0,      # Tool execution timeout
    "max_tools": 100,             # Maximum registered tools
    "consul_host": "...",         # REQUIRED: Consul hostname
    "consul_port": 8500,          # REQUIRED: Consul port (int)
    "kafka_enabled": True,        # REQUIRED: Enable Kafka hot-reload
    "dev_mode": False,            # REQUIRED: Dev mode (contract scanning)
    "contracts_dir": None,        # Optional: path to contracts for dev_mode
    "skip_server": False,         # Testing only: skip uvicorn startup
}
```

The `ModelMcpHandlerConfig` Pydantic model handles type coercion (e.g., `"8090"` → `8090`) and strict validation (`extra="forbid"`).

### Environment variables (the secrets manager path)

When the secrets manager is active, MCP transport config is stored at:
```
/shared/mcp/MCP_SERVER_HOST
/shared/mcp/MCP_SERVER_PORT
```

---

## Operations: Supported Envelope Operations

When `HandlerMCP.execute(envelope)` is called via the ONEX runtime:

| Operation | Key | Description |
|-----------|-----|-------------|
| `mcp.list_tools` | `EnumMcpOperationType.LIST_TOOLS` | Returns all registered tools with JSON Schema |
| `mcp.call_tool` | `EnumMcpOperationType.CALL_TOOL` | Invokes a named tool; payload requires `tool_name` and `arguments` |
| `mcp.describe` | `EnumMcpOperationType.DESCRIBE` | Returns handler metadata: type, category, tool count, config, server state |

All operations return `ModelHandlerOutput.for_compute(result=...)`.

---

## Current Limitations and Roadmap

| Limitation | Notes |
|------------|-------|
| Manual tool registration only | Auto-discovery from contract `mcp_enabled: true` planned |
| No authentication | Bearer token, API key, or identity service integration planned |
| `mcp.call_tool` placeholder mode | Integrated mode requires registry + executor |

---

## See Also

- `docs/architecture/LLM_INFRASTRUCTURE.md` — LLM HTTP transport patterns used by inference/embedding nodes
- `docs/patterns/circuit_breaker_implementation.md` — Circuit breaker mechanics used by HandlerMCP
- `docs/patterns/error_handling_patterns.md` — Error context and sanitization requirements
- `docs/patterns/handler_plugin_loader.md` — How handlers are loaded from contracts
- `src/omnibase_infra/handlers/mcp/` — MCP module source files
- `src/omnibase_infra/services/mcp/` — MCP service implementations
