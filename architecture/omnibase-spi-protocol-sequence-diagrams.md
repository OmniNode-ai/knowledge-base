---
type: architecture
status: accepted
date: "2026-09-01"
title: "omnibase_spi Protocol Sequence Diagrams"
topics:
  - omnibase_spi
  - architecture
  - protocols
  - sequence-diagrams
refs: []
---

<!-- Migrated from omnibase_spi:docs/PROTOCOL_SEQUENCE_DIAGRAMS.md on 2026-09-01 -->

# Protocol Interaction Patterns

This document provides sequence diagrams showing the interaction patterns for key ONEX SPI protocols. These diagrams help developers understand the expected lifecycle and communication flows when implementing or using these protocols.

## Handler Protocol Patterns

The `ProtocolHandler` interface defines the contract for protocol-specific handlers (HTTP, Kafka, PostgreSQL, etc.) used in effect nodes for request-response I/O operations.

### Handler Lifecycle Flow

```mermaid
sequenceDiagram
    participant Client
    participant Handler as ProtocolHandler
    participant Backend as Backend Service

    Note over Client,Backend: Initialization Phase
    Client->>Handler: initialize(config)
    Handler->>Backend: establish connection
    Backend-->>Handler: connection established
    Handler-->>Client: ready

    Note over Client,Backend: Execution Phase
    Client->>Handler: execute(request, operation_config)
    Handler->>Backend: perform operation
    Backend-->>Handler: result
    Handler-->>Client: ModelProtocolResponse

    Note over Client,Backend: Health Check (periodic)
    Client->>Handler: health_check()
    Handler->>Backend: ping/probe
    Backend-->>Handler: OK (latency_ms)
    Handler-->>Client: {healthy: true, latency_ms: 5}

    Note over Client,Backend: Shutdown Phase
    Client->>Handler: shutdown(timeout_seconds)
    Handler->>Backend: flush pending ops
    Handler->>Backend: close connection
    Backend-->>Handler: closed
    Handler-->>Client: shutdown complete
```

### Handler Error Handling Flow

```mermaid
sequenceDiagram
    participant Client
    participant Handler as ProtocolHandler
    participant Backend as Backend Service

    Note over Client,Backend: Execution with Error
    Client->>Handler: execute(request, config)
    Handler->>Backend: perform operation
    Backend--xHandler: error response
    Handler-->>Client: raise ProtocolHandlerError

    Note over Client,Backend: Health Check Failure
    Client->>Handler: health_check()
    Handler->>Backend: ping/probe
    Backend--xHandler: timeout/connection refused
    Handler-->>Client: {healthy: false, last_error: "Connection timeout"}

    Note over Client,Backend: Initialization Failure
    Client->>Handler: initialize(config)
    Handler->>Backend: establish connection
    Backend--xHandler: connection refused
    Handler-->>Client: raise HandlerInitializationError
```

### Handler Introspection Flow

```mermaid
sequenceDiagram
    participant Client
    participant Handler as ProtocolHandler

    Note over Client,Handler: Metadata Discovery
    Client->>Handler: handler_type
    Handler-->>Client: "http"

    Client->>Handler: describe()
    Handler-->>Client: {handler_type: "http", capabilities: ["GET", "POST"], version: "1.0"}

    Note over Client,Handler: Capability Check Before Operation
    Client->>Handler: describe()
    Handler-->>Client: {capabilities: ["read", "write", "transactions"]}
    Client->>Client: verify required capability
    Client->>Handler: execute(request, config)
    Handler-->>Client: response
```

## EventBus Protocol Patterns

The EventBus protocols define contracts for distributed messaging with envelope-based communication, supporting both publishing and consuming patterns.

### Publisher Flow

```mermaid
sequenceDiagram
    participant Service
    participant Publisher as ProtocolEventPublisher
    participant Kafka as Kafka/Redpanda
    participant DLQ as Dead Letter Queue

    Note over Service,DLQ: Successful Publish
    Service->>Publisher: publish(event_type, payload, correlation_id)
    Publisher->>Publisher: validate event
    Publisher->>Kafka: produce message
    Kafka-->>Publisher: ack
    Publisher-->>Service: true

    Note over Service,DLQ: Publish with Retry
    Service->>Publisher: publish(event_type, payload)
    Publisher->>Kafka: produce message
    Kafka--xPublisher: temporary failure
    Publisher->>Publisher: exponential backoff
    Publisher->>Kafka: retry produce
    Kafka-->>Publisher: ack
    Publisher-->>Service: true

    Note over Service,DLQ: Publish Failure (DLQ Route)
    Service->>Publisher: publish(event_type, payload)
    loop Max Retries Exceeded
        Publisher->>Kafka: produce message
        Kafka--xPublisher: failure
        Publisher->>Publisher: backoff + retry
    end
    Publisher->>DLQ: route to {topic}.dlq
    DLQ-->>Publisher: ack
    Publisher-->>Service: false (sent to DLQ)

    Note over Service,DLQ: Circuit Breaker Open
    Service->>Publisher: publish(event_type, payload)
    Publisher-->>Service: raise RuntimeError (circuit open)
```

### Consumer Flow (Envelope-Based)

```mermaid
sequenceDiagram
    participant Service
    participant EventBus as ProtocolEventBusBase
    participant Kafka as Kafka/Redpanda
    participant Handler as Event Handler

    Note over Service,Handler: Subscription Setup
    Service->>EventBus: subscribe(topic, handler)
    EventBus->>EventBus: register handler
    EventBus-->>Service: subscribed

    Service->>EventBus: subscribe(topic2, handler2)
    EventBus->>EventBus: register handler2
    EventBus-->>Service: subscribed

    Note over Service,Handler: Start Consuming
    Service->>EventBus: start_consuming()
    EventBus->>Kafka: join consumer group
    Kafka-->>EventBus: partitions assigned

    loop Message Processing
        Kafka->>EventBus: poll messages
        EventBus->>EventBus: deserialize to ModelEventEnvelope
        EventBus->>Handler: handler(envelope)
        Handler->>Handler: process envelope.payload
        Handler-->>EventBus: complete
        EventBus->>Kafka: commit offset
    end

    Note over Service,Handler: Shutdown
    Service->>EventBus: shutdown
    EventBus->>Kafka: leave consumer group
    Kafka-->>EventBus: left
    EventBus-->>Service: shutdown complete
```

### EventBus Service Lifecycle

```mermaid
sequenceDiagram
    participant App as Application
    participant Service as ProtocolEventBusService
    participant EventBus as ProtocolEventBusBase
    participant Cluster as Kafka Cluster

    Note over App,Cluster: Service Initialization
    App->>Service: create_event_bus_service(config)
    Service->>Cluster: connect to brokers
    Cluster-->>Service: connected
    Service-->>App: service ready

    Note over App,Cluster: Get Event Bus
    App->>Service: get_event_bus()
    Service-->>App: ProtocolEventBusBase instance

    App->>EventBus: publish_envelope(envelope, topic)
    EventBus->>Cluster: produce
    Cluster-->>EventBus: ack
    EventBus-->>App: published

    Note over App,Cluster: Cluster Monitoring
    App->>Service: is_running
    Service-->>App: true

    App->>Service: get_node_count()
    Service->>Cluster: query metadata
    Cluster-->>Service: 3 brokers
    Service-->>App: 3

    App->>Service: list_nodes()
    Service->>Cluster: query metadata
    Cluster-->>Service: [broker-1, broker-2, broker-3]
    Service-->>App: ["broker-1", "broker-2", "broker-3"]

    Note over App,Cluster: Graceful Shutdown
    App->>Service: shutdown()
    Service->>EventBus: flush pending
    Service->>Cluster: close connections
    Cluster-->>Service: closed
    Service-->>App: shutdown complete
```

### EventBus Provider Pattern

```mermaid
sequenceDiagram
    participant App as Application
    participant Provider as ProtocolEventBusProvider
    participant Cache as Instance Cache
    participant EventBus as ProtocolEventBusBase

    Note over App,EventBus: Get Cached Instance
    App->>Provider: get_event_bus(environment="prod", group="svc")
    Provider->>Cache: lookup(prod, svc)
    Cache-->>Provider: cached instance
    Provider-->>App: ProtocolEventBusBase

    Note over App,EventBus: Create New Instance
    App->>Provider: get_event_bus(environment="dev", group="test")
    Provider->>Cache: lookup(dev, test)
    Cache-->>Provider: not found
    Provider->>EventBus: create new instance
    EventBus-->>Provider: instance
    Provider->>Cache: store(dev, test, instance)
    Provider-->>App: ProtocolEventBusBase

    Note over App,EventBus: Force New Instance
    App->>Provider: create_event_bus(env, group, config)
    Provider->>EventBus: create new instance
    EventBus-->>Provider: instance
    Provider-->>App: ProtocolEventBusBase (not cached)

    Note over App,EventBus: Cleanup All Instances
    App->>Provider: close_all(timeout_seconds=30)
    Provider->>Cache: get all instances
    loop For Each Instance
        Provider->>EventBus: close()
        EventBus-->>Provider: closed
    end
    Provider->>Cache: clear
    Provider-->>App: all closed
```

### HTTP EventBus Adapter Flow

```mermaid
sequenceDiagram
    participant Client
    participant Adapter as ProtocolHttpEventBusAdapter
    participant API as EventBus HTTP API

    Note over Client,API: Publish via HTTP
    Client->>Adapter: publish(event)
    Adapter->>API: POST /events
    API-->>Adapter: 200 OK
    Adapter-->>Client: true

    Note over Client,API: Subscribe via HTTP
    Client->>Adapter: subscribe(handler)
    Adapter->>API: POST /subscriptions
    API-->>Adapter: subscription_id
    Adapter-->>Client: true

    loop HTTP Polling
        Adapter->>API: GET /messages?subscription_id=xyz
        API-->>Adapter: [messages]
        Adapter->>Client: handler(message)
        Client-->>Adapter: ack (true)
        Adapter->>API: POST /ack
    end

    Note over Client,API: Health Check
    Client->>Adapter: is_healthy
    Adapter->>API: GET /health
    API-->>Adapter: 200 OK
    Adapter-->>Client: true

    Note over Client,API: Cleanup
    Client->>Adapter: unsubscribe(handler)
    Adapter->>API: DELETE /subscriptions/xyz
    API-->>Adapter: 200 OK
    Adapter-->>Client: true

    Client->>Adapter: close()
    Adapter->>API: close connections
    Adapter-->>Client: closed
```

## Key Protocol Differences

| Aspect | ProtocolHandler | ProtocolEventBus |
|--------|-----------------|------------------|
| **Pattern** | Request-Response | Publish-Subscribe |
| **Communication** | Synchronous (awaited) | Asynchronous (fire-and-forget) |
| **Use Case** | Direct I/O operations | Inter-service messaging |
| **Coupling** | Tight (direct response) | Loose (topic-based) |
| **Error Handling** | Exceptions | DLQ routing |
| **State** | Per-request | Consumer groups |

## See Also

- [Developer Guide](../guides/omnibase-spi-developer-guide.md) - Protocol implementation guidance
- `EventBus API Reference` (in the omnibase_spi repository) - EventBus protocol details
- [Protocol Selection Guide](../guides/omnibase-spi-protocol-selection-guide.md) - Choosing the right protocol
- [Protocol Composition Patterns](../guides/omnibase-spi-protocol-composition-patterns.md) - Composing protocols
- [Implementation Examples](../guides/omnibase-spi-implementation-examples.md) - Working code examples
