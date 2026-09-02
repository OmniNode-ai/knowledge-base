---
type: guide
status: current
date: "2026-09-02"
title: "Standalone Quickstart"
topics: [omnibase-infra, standalone, quickstart]
refs: []
---

<!-- Migrated from omnibase_infra:docs/getting-started/standalone-quickstart.md on 2026-09-02. -->

<!-- GENERATED FROM canonical.yaml -- DO NOT EDIT MANUALLY -->

# Standalone Quickstart

## Check Python Installation

Verify Python 3.12+ is available

- [ ] **Check Python Installation**
  - Verify: `python3 --version` (command_exit_0)
  - Estimated time: 5s

## Install uv Package Manager

Install uv for dependency management

- [ ] **Install uv Package Manager**
  - Verify: `uv --version` (command_exit_0)
  - Estimated time: 30s

## Install omnibase_core

Install the core ONEX package with uv

- [ ] **Install omnibase_core**
  - Verify: `omnibase_core` (python_import)
  - Estimated time: 1m 0s

## Create First Node

Scaffold a minimal ONEX node using the CLI

- [ ] **Create First Node**
  - Verify: `my_first_node/node.py` (file_exists)
  - Estimated time: 30s

## Run Standalone Node

Execute the node in standalone mode (no infrastructure)

- [ ] **Run Standalone Node**
  - Verify: `uv run python -m my_first_node.node --dry-run` (command_exit_0)
  - Estimated time: 15s
