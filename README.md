# Infernux AI-Native Engine Layer

This document describes the AI-native modification layer built on top of the
open-source Infernux engine.

The original Infernux engine README is kept in
[`README-INFERNUX.md`](README-INFERNUX.md). This file focuses on the
AI-native direction: turning the engine into a runtime
surface that external AI agents can observe, control, edit, evaluate, and
replay.

## Positioning

The goal is not to build an AI agent inside the engine.

The goal is to make the engine agent-operable:

- The engine exposes the world.
- The engine accepts structured control.
- The engine reports events and outcomes.
- The engine allows bounded world edits.
- The engine keeps gameplay semantics out of the core runtime.
- External agents decide what to do.

In short:

```text
Infernux should not be the agent.
Infernux should be the world operating system for agents.
```

## Current Stage

The project is currently at the AI Runtime Core v1 stage, with the first
read-only World Model API and the first contract-hardening pass in place.

It already has a working minimum loop:

```text
observe world -> agent/adapter decides -> submit control or edit -> step runtime -> read events/evaluation
```

This is enough for controlled runtime experiments and simple AI-operated
scenes. It is not yet a complete production-grade agent-operable engine.
The Python Core API is also native-tolerant at import time: native bindings are
loaded lazily by operations that need the live engine, so pure contract tests
and documentation tooling can run without a matching local `_Infernux` binary.

## Implemented Capabilities

| Area | Current capability |
| --- | --- |
| Runtime core boundary | `Infernux.ai_runtime` defines a semantics-free runtime surface. |
| Entity observation | Entities can be listed, queried by component, sampled, and summarized. |
| Control | Agents can submit generic `ControlSignal` values from Python or MCP, inspect control state, and rely on `duration_ms` expiry. |
| Lifecycle | Play mode can be entered/exited, paused, resumed, and stepped. |
| Events | Runtime events can be collected, filtered, and read by agents. |
| Evaluation | Basic evaluation primitives exist for feedback loops. |
| World model | Agents can read scene snapshots, component schemas, allowlisted component fields, and snapshot diffs without importing edit/native mutation code. |
| World editing | Bounded component edits and entity movement are exposed through a shared native-free core-writable field allowlist. |
| Adapters | Gameplay semantics live in `Infernux.ai_adapters`, not in core. |
| MCP tools | The project exposes editor/project/runtime capabilities through MCP, including agent onboarding, world snapshots, schema/diff tools, and generic runtime control submission. |
| Experiment rules | Runtime experiment constraints are documented in `RUNTIME_EXPERIMENT_RULES.md`. |

## Core Principle

The AI Runtime Core must not understand gameplay semantics.

Allowed in core:

- query
- control
- observation
- event
- evaluation
- editing
- lifecycle

Not allowed in core:

- player-specific assumptions
- enemy-specific assumptions
- jump/attack/platform/goal semantics
- task strategy
- agent policy

Those concepts belong above the core, in adapters or external agents.

## Architecture

```text
External AI Agent
        |
        v
Adapter Layer
        |
        v
Infernux AI Runtime Core
        |
        v
Python facade / pybind11 bindings
        |
        v
C++ runtime source of truth
```

The C++ runtime owns the real world state. Python exposes a structured control
and observation surface. Adapters translate between game-specific concepts and
the semantics-free core API.

## Main Runtime Surfaces

### Observation

Observation APIs let an agent inspect the active world without relying on game
scripts or editor-only assumptions.

Key concepts:

- `EntityRecord`
- `EntitySnapshot`
- `EntityActivitySummary`
- `WorldStateProjection`
- `WorldSnapshot`
- `EntityWorldSnapshot`
- `ComponentSnapshot`
- `ComponentSchema`
- component queries
- component field reads
- world snapshot diffs
- radius queries
- recent events

Reference: [`API_Reference.md`](API_Reference.md)

### Control

Control APIs let an agent affect runtime execution through generic signals and
play-mode lifecycle controls.

Key concepts:

- `ControlSignal`
- `submit_control`
- `clear_control`
- `expire_control_signals`
- `get_control_state`
- `enter_play_mode`
- `exit_play_mode`
- `pause`
- `resume`
- `step`

### Events and Evaluation

Events and evaluation close the feedback loop. Agents need to know not only
what they did, but what changed and whether the world moved toward a desired
condition.

Current support includes:

- runtime event reads
- event filtering
- basic evaluation
- adjustment state

This area is still early and should become a first-class experiment framework.

### World Editing

World editing gives agents bounded authority to modify the world.

Current support includes:

- moving entities
- setting a small allowlisted set of component fields
- sharing the same native-free core-writable field allowlist with the World Model schema
- edit/runtime mode awareness
- undo-aware integration points

Future work should turn this into a transaction system with validation,
dry-run, commit, rollback, audit logs, and batch edits.

### Adapter Layer

Adapters are where gameplay semantics belong.

Examples:

- Tic-tac-toe adapter
- Platformer adapter
- Demo/runtime experiment adapters

Adapters may talk about game roles, actions, objectives, or rewards. The core
runtime should not.

## Documentation Map

| Document | Purpose |
| --- | --- |
| [`README.md`](README.md) | AI-native project overview. |
| [`README-INFERNUX.md`](README-INFERNUX.md) | Original Infernux engine README. |
| [`README-zh.md`](README-zh.md) | Original Chinese README. |
| [`API_Reference.md`](API_Reference.md) | Hand-written AI Runtime Core API reference. |
| [`AI_FIRST_ENGINE_v1_SPEC_PATCH.md`](AI_FIRST_ENGINE_v1_SPEC_PATCH.md) | AI Runtime Core v1 design boundary and spec. |
| [`AI_FIRST_ENGINE_FUTURE_GOALS.md`](AI_FIRST_ENGINE_FUTURE_GOALS.md) | Long-term AI-native engine direction. |
| [`RUNTIME_EXPERIMENT_RULES.md`](RUNTIME_EXPERIMENT_RULES.md) | Required rules for runtime AI experiments. |
| [`AGENTS.md`](AGENTS.md) | First-contact operating guide for external coding/AI agents. |
| [`docs/agent/`](docs/agent/README.md) | Agent onboarding quickstart and operation recipes. |
| [`Proposed API Extensions - Review Response v2.md`](Proposed%20API%20Extensions%20-%20Review%20Response%20v2.md) | Reviewed API extension decisions. |
| [`docs/wiki/`](docs/wiki/) | MkDocs scripting/API documentation source. |

Generated API pages under `docs/wiki/docs/*/api/` should not be hand-edited
unless the generation pipeline is also updated.

## Build and Test Entry Points

For complete engine prerequisites, use the original engine README:
[`README-INFERNUX.md`](README-INFERNUX.md).

Common build flow:

```powershell
cmake --preset release
cmake --build --preset release
```

Run Python tests:

```powershell
cd python
python -m pytest test/ -v
```

Run the external-agent operation demo:

```powershell
$env:PYTHONPATH="$PWD\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_world_operation_demo.py --auto-close
```

The demo starts the editor, connects as an external MCP client, opens
`Assets/Scenes/AIBilliard.scene`, reads the world model, creates visible
agent waypoints, frames the camera, enters Play Mode, submits generic
`runtime_submit_control` signals, reads runtime object state, and reports the
world edit diff plus runtime errors. Use the Python executable that matches the
built `_Infernux` extension; the path above matches the current local
`_Infernux.cp314-win_amd64.pyd` build.

Build wiki documentation:

```powershell
python docs/wiki/generate_api_docs.py
python -m mkdocs build --clean -f docs/wiki/mkdocs.yml
```

Build the Hub package:

```powershell
cmake --build --preset packaging
```

Build the graphical installer:

```powershell
cmake --build --preset packaging-installer
```

## Current Limitations

The current implementation is intentionally conservative. Known gaps include:

- world observation now has a first snapshot model, but not yet resource graph,
  history, or subscriptions
- command execution is not yet a formal command queue
- world editing is not yet transaction-based
- replay and deterministic experiment reporting are still early
- evaluation is not yet a complete benchmark/metrics framework
- native integration tests still depend on a matching Python/native binary and
  engine DLL set
- some legacy player-centric APIs still exist and should remain transitional

## Roadmap

### 1. Freeze the AI Runtime Core contract

- stabilize `Infernux.ai_runtime`
- separate stable, experimental, and legacy APIs
- add contract tests for each public primitive
- document error semantics
- keep semantic-boundary tests strict

### 2. Expand the World Model API

- keep stable entity identifiers and scene graph queries covered by contract tests
- expand component schema and field metadata coverage
- resource dependency graph
- state history
- richer state diffing
- event subscriptions

### 3. Upgrade control into a Command System

- command ids
- command results
- command status
- command queues
- high-level runtime commands
- deterministic step execution
- command replay

### 4. Upgrade editing into a Transaction System

- begin transaction
- dry-run
- validate
- commit
- rollback
- batch edit
- create/delete entity
- add/remove component
- audit log

### 5. Build an Experiment Framework

- scenario definitions
- objective metrics
- constraint checks
- run reports
- before/after comparison
- deterministic replay
- failure traces
- benchmark scenes

### 6. Promote MCP into the Agent Cockpit

- capability-gated tools
- transaction-aware editor tools
- structured tool responses
- read-only and destructive-operation modes
- unified project/scene/runtime context
- observation, command, event, and evaluation tools

## Non-Goals

This layer should not:

- embed a specific AI agent
- hard-code game strategy
- place gameplay semantics in the core runtime
- replace the engine's renderer, physics, scene, or editor systems
- treat a demo adapter as the engine API

## Summary

The current AI-native layer turns Infernux from a game engine that can run
scripts into a game engine that an external AI agent can start to operate.

The next step is to make that operation reliable:

```text
global observation
structured control
validated editing
event feedback
objective evaluation
deterministic replay
```

That is the path from an AI-enabled engine to an AI-native engine.
