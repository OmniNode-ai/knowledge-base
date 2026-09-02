---
type: guide
status: current
date: "2026-09-02"
title: "Contributor Local Setup"
topics: [omnibase-infra, contributor, local, setup]
refs: []
---

<!-- Migrated from omnibase_infra:docs/getting-started/contributor-local.md on 2026-09-02. -->

<!-- GENERATED FROM canonical.yaml -- DO NOT EDIT MANUALLY -->

# Contributor Local Setup

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

## Start Docker Infrastructure

Start PostgreSQL, Redpanda, and Valkey via Docker Compose

- [ ] **Start Docker Infrastructure**
  - Verify: `localhost:5436` (tcp_probe)
  - Estimated time: 2m 0s

## Start Event Bus

Verify Redpanda/Kafka event bus is running

- [ ] **Start Event Bus**
  - Verify: `localhost:19092` (tcp_probe)
  - Estimated time: 30s

## Connect Node to Event Bus

Configure node to publish/consume events via Kafka

- [ ] **Connect Node to Event Bus**
  - Verify: `uv run python -c "from omnibase_infra.event_bus import get_bus; print('ok')"` (command_exit_0)
  - Estimated time: 1m 0s
