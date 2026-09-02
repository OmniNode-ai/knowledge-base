---
type: guide
status: current
date: "2026-09-02"
title: "Node Building Guide"
topics:
  - omnibase-core
  - node
  - building
  - overview
refs: []
---

<!-- Migrated from omnibase_core:docs/guides/node-building/README.md on 2026-09-02 -->

> **Note**: For authoritative coding standards, see CLAUDE.md.

# Node Building Guide

**Status**: Active
**Version**: v0.4.0
**Target Audience**: Developers building ONEX nodes
**Prerequisites**: Python 3.12+, Poetry, Basic async/await understanding

## Overview

This comprehensive guide teaches you how to build production-ready nodes for the ONEX framework. Whether you're a human developer or an AI agent, you'll learn the patterns, practices, and principles for creating robust, scalable nodes.

### v0.4.0 Architecture Update

As of v0.4.0, the ONEX node architecture has been streamlined:

- **`NodeReducer`** and **`NodeOrchestrator`** are now the PRIMARY implementations (FSM/workflow-driven)
- The "Declarative" suffix has been removed - these ARE the standard
- Legacy imperative implementations have been **removed** (no deprecation period)

**Import paths**:
```python
# Primary implementations (recommended)
from omnibase_core.nodes import NodeCompute, NodeEffect, NodeReducer, NodeOrchestrator

# Note: Legacy implementations have been removed in v0.4.0
# All nodes must use the FSM/workflow-driven implementations above
```

> **Terminology Reference**: For canonical definitions of ONEX concepts (Event, Intent, Action, Reducer, Orchestrator, Effect, Handler, Projection, Runtime), see ONEX Terminology Guide.

## Fundamental Concept: Nodes Are Thin Shells

Before diving into tutorials, understand this core principle:

**Nodes are coordination shells. Handlers own the business logic.**

A node receives input, delegates to a handler, and returns the handler's output. The node itself should contain no business logic -- it is a thin wrapper that provides lifecycle management, dependency injection, and contract enforcement. All domain logic lives in **handlers**, which are defined and selected by **YAML contracts**.

```
Node (thin shell)
  |
  +-- receives input
  +-- resolves handler from YAML contract
  +-- delegates to handler
  +-- returns handler output
```

For a deep dive into this architecture, see the Handler Architecture Guide.

### Handler Output Constraints

Each node type enforces strict output constraints on what its handler may return:

| Node Kind | Allowed Output | Forbidden Output |
|-----------|---------------|-----------------|
| **EFFECT** | `events[]` | `intents[]`, `projections[]`, `result` |
| **COMPUTE** | `result` (required) | `events[]`, `intents[]`, `projections[]` |
| **REDUCER** | `projections[]` | `events[]`, `intents[]`, `result` |
| **ORCHESTRATOR** | `events[]`, `intents[]` | `projections[]`, `result` |

These constraints are enforced at the `ModelHandlerOutput` constructor via Pydantic validators and at runtime.

## What You'll Learn

- **Fundamentals**: What nodes are and their role in the ONEX ecosystem
- **Handler Architecture**: How nodes delegate to handlers via YAML contracts
- **Node Types**: When to use EFFECT, COMPUTE, REDUCER, or ORCHESTRATOR
- **Step-by-Step Tutorials**: Build each node type from scratch
- **Patterns Library**: Reusable patterns for common scenarios
- **Testing Strategies**: How to test nodes thoroughly
- **Common Pitfalls**: What to avoid and how to fix issues

## Guide Structure

### 1. Fundamentals

- 01. What is a Node? - Definition, purpose, and role in ONEX
- 02. Node Types - EFFECT, COMPUTE, REDUCER, ORCHESTRATOR explained
- Handler Architecture - How nodes delegate to handlers via YAML contracts

### 2. Step-by-Step Tutorials

Each tutorial takes you from zero to a working, tested node:

- 03. COMPUTE Node Tutorial - Build a data transformation node
- 04. EFFECT Node Tutorial - Build a database interaction node
- 05. REDUCER Node Tutorial - Build a data aggregation node
- 06. ORCHESTRATOR Node Tutorial - Build a workflow coordination node

### 3. Advanced Topics

- 07. Patterns Catalog - Common patterns with code
- 08. Common Pitfalls - What to avoid
- 10. Agent Templates - Agent-friendly structured templates

## Quick Start

**Never built a node before?** Start here:

1. Read What is a Node? (5 min)
2. Read Node Types (10 min)
3. Follow the COMPUTE Node Tutorial (30 min)
4. Test your node and celebrate! 🎉

**Built nodes before?** Jump to:

- Patterns Catalog for reusable patterns
- Agent Templates for structured templates

## Development Notes

This guide is designed to be developer-friendly with:

- ✅ **Structured formats**: Clear, parseable patterns
- ✅ **Complete code examples**: Copy-paste ready
- ✅ **Step-by-step instructions**: Actionable numbered steps
- ✅ **Validation checkpoints**: Verify success at each stage
- ✅ **Template library**: Reusable structured templates

See Agent Templates for specialized agent-focused content.

## Prerequisites

Before building nodes, ensure you have:

### Required

- **Python 3.12+**: `python --version`
- **Poetry**: `uv --version`
- **omnibase_core installed**: `uv add omnibase_core` (or local editable install)
- **Basic async/await knowledge**: Understanding of Python async patterns

### Recommended

- **Git**: For version control
- **pytest**: For testing (`uv add --group dev pytest`)
- **mypy**: For type checking (`uv add --group dev mypy`)
- **IDE with Python support**: VSCode, PyCharm, or similar

### Verification

Verify your environment:

```bash
# Check Python version
python --version  # Should be 3.12+

# Check Poetry
uv --version  # Should be 1.0+

# Install omnibase_core (if not already installed)
uv add omnibase_core

# Verify installation (v0.4.0+ with primary node implementations)
uv run python -c "from omnibase_core.nodes import NodeCompute, NodeReducer, NodeOrchestrator; print('✓ omnibase_core ready!')"
```

## Learning Path

### Beginner Path (First Time Building Nodes)

1. **Foundations** (30 min)
   - Read: What is a Node?
   - Read: Node Types

2. **First Node** (1-2 hours)
   - Tutorial: COMPUTE Node
   - Practice: Build a simple calculator node

3. **Testing** (30 min)
   - Read: Testing Guide
   - Practice: Test your calculator node

4. **Second Node** (1-2 hours)
   - Tutorial: Choose EFFECT or REDUCER based on your needs
   - Practice: Build and test

### Intermediate Path (Some Experience)

1. **Review Patterns** (30 min)
   - Read: Patterns Catalog
   - Identify patterns for your use case

2. **Build Complex Node** (2-4 hours)
   - Tutorial: ORCHESTRATOR Node
   - Practice: Build workflow coordinator

3. **Avoid Pitfalls** (30 min)
   - Read: Common Pitfalls
   - Review your code for anti-patterns

### Advanced Path (Experienced Developer)

1. **Deep Dive**
   - Review: ONEX_FOUR_NODE_ARCHITECTURE.md
   - Study: Real implementations in `src/omnibase_core/nodes/`

2. **Custom Patterns**
   - Extend: Base node classes
   - Create: Domain-specific patterns

3. **Contribute**
   - Share: Your patterns back to the community
   - Document: Your discoveries

## Project Integration

### Adding Nodes to Your Project

```
# In your project directory
uv add omnibase_core

# Create node structure
mkdir -p src/your_project/nodes
touch src/your_project/nodes/__init__.py

# Follow tutorials to create nodes
# Example: src/your_project/nodes/node_data_processor_compute.py
```

### Project Structure

```
your_project/
├── pyproject.toml                    # Poetry configuration
├── src/
│   └── your_project/
│       ├── __init__.py
│       ├── nodes/                    # Your nodes here
│       │   ├── __init__.py
│       │   ├── node_data_processor_compute.py
│       │   ├── node_api_client_effect.py
│       │   ├── node_aggregator_reducer.py      # Uses NodeReducer (FSM-driven)
│       │   └── node_workflow_orchestrator.py   # Uses NodeOrchestrator (workflow-driven)
│       ├── models/                   # Your models
│       └── enums/                    # Your enums
└── tests/
    └── nodes/                        # Node tests
        ├── test_node_data_processor.py
        └── test_node_api_client.py
```

> **Note**: As of v0.4.0, `NodeReducer` and `NodeOrchestrator` are the primary FSM/workflow-driven implementations. Use these for new nodes.

## Getting Help

- **Documentation Issues**: File an issue in the repository
- **Pattern Questions**: Check Patterns Catalog
- **Code Examples**: See `src/omnibase_core/nodes/` for real implementations
- **Testing Help**: See Testing Guide

## Contributing

Found a better pattern? Want to share a tutorial? Contributions welcome!

1. Follow existing structure and formatting
2. Include working code examples
3. Test all code before submitting
4. Update this README if adding new content

## What's Next?

Ready to start building? Choose your path:

- **New to nodes?** → What is a Node?
- **Know the basics?** → COMPUTE Node Tutorial
- **Need patterns?** → Patterns Catalog
- **Ready to test?** → Testing Guide

Happy node building! 🚀
