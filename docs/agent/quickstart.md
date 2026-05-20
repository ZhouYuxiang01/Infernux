# Agent Quickstart

This guide is for external coding agents and AI agents that have never seen
Infernux before.

## What You Are Operating

Infernux is an agent-operable game runtime. It exposes a live world through
structured tools. Your job is not to guess engine internals; your job is to
observe, choose the smallest valid operation, act through the runtime surface,
and verify the result.

The engine is not an agent. It does not decide strategy. It provides:

- world observation
- generic runtime control
- editor lifecycle
- bounded scene edits
- events and errors
- world snapshots and diffs

## First MCP Calls

Call these in order:

1. `agent_bootstrap`
2. `mcp_health`
3. `runtime_explain_current_scene`
4. `runtime_get_world_snapshot`
5. `runtime_read_errors`

This gives you the runtime boundary, current editor state, active scene,
available objects, and current error status.

## Core Loop

Use this loop:

```text
Observe -> Plan -> Act -> Advance -> Verify -> Recover
```

Typical tool chain:

```text
mcp_health
runtime_explain_current_scene
runtime_get_world_snapshot
scene_query_objects
runtime_submit_control or transform_set
runtime_run_for or runtime_diff_world_snapshots
runtime_assert
runtime_read_errors
runtime_clear_control
```

## Mode Rules

Edit Mode:

- create/delete objects
- set transform/component fields
- frame cameras
- save scenes

Play Mode:

- submit runtime control
- run for short durations
- read runtime state
- read errors

Do not mix these unless a tool explicitly allows it.

## Recipes

- Observe a scene: `docs/agent/recipes/observe_scene.md`
- Drive runtime behavior: `docs/agent/recipes/control_runtime.md`
- Edit and verify the world: `docs/agent/recipes/safe_world_edit.md`
- Debug runtime errors: `docs/agent/recipes/debug_runtime_errors.md`
