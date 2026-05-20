# Infernux Agent Operating Guide

This repository contains an AI-native modification layer on top of the
open-source Infernux engine.

## Mental Model

Infernux is not the agent. Infernux is the world runtime that external agents
operate.

Use this boundary:

```text
External Agent -> Adapter Layer -> AI Runtime Core -> Python/C++ Engine Runtime
```

The AI Runtime Core is semantics-free. It may expose observation, control,
events, lifecycle, evaluation, and bounded editing. It must not hard-code game
roles, strategy, tasks, player/enemy semantics, or agent policy.

## First Contact Sequence

When you connect to a running editor through MCP, call these tools first:

1. `agent_bootstrap`
2. `mcp_health`
3. `runtime_explain_current_scene`
4. `runtime_get_world_snapshot`
5. `mcp_catalog_search` or `workflow_help`

Then choose the smallest recipe that matches the task:

- `docs/agent/recipes/observe_scene.md`
- `docs/agent/recipes/control_runtime.md`
- `docs/agent/recipes/safe_world_edit.md`
- `docs/agent/recipes/debug_runtime_errors.md`

## Operating Loop

Use this loop for almost every task:

```text
Observe -> Plan -> Act -> Advance -> Verify -> Recover
```

- Observe with `mcp_health`, `runtime_explain_current_scene`,
  `runtime_get_world_snapshot`, and scene query tools.
- Plan with exact object IDs, component schemas, and current Play/Edit Mode.
- Act with `runtime_submit_control` in Play Mode or bounded editor tools in
  Edit Mode.
- Advance with `runtime_run_for` or `editor_step`.
- Verify with fresh state reads, `runtime_diff_world_snapshots`,
  `runtime_assert`, and `runtime_read_errors`.
- Recover by clearing control channels, stopping Play Mode, and saving or
  reverting generated content as appropriate.

## Safety Rules

- Observe before mutating.
- Do not use editor-scene mutation tools while Play Mode is active unless the
  tool explicitly allows it.
- Use `component_describe_type` or `runtime_get_component_schema` before field
  edits.
- Use `api_search` / `api_get` before writing unfamiliar Infernux Python code.
- Use `runtime_clear_control` after runtime experiments.
- Scene object IDs are session-local; reacquire them after scene reload.
- Read `runtime_read_errors` after every run, script edit, or scene mutation.
- Save scenes with `scene_save`; do not edit `.scene` files through generic
  asset file tools while they are active.

## Useful Entry Points

- Project overview: `README.md`
- Runtime API reference: `API_Reference.md`
- Core spec: `AI_FIRST_ENGINE_v1_SPEC_PATCH.md`
- Agent quickstart: `docs/agent/quickstart.md`
- Agent docs index: `docs/agent/README.md`
- Runtime experiment rules: `RUNTIME_EXPERIMENT_RULES.md`
- Demo script: `scripts/agent_world_operation_demo.py`

## Local Verification

Contract tests that do not require a matching native Python build:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_mcp_agent_onboarding_tools.py -q --noconftest
.\venv\Scripts\python.exe -m pytest python\test\test_mcp_runtime_world_model_tools.py -q --noconftest
```

Native/editor demo, using the Python version that matches the built
`_Infernux.cp314-win_amd64.pyd`:

```powershell
$env:PYTHONPATH="C:\Users\zyx62\Documents\GitHub\Infernux\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_world_operation_demo.py --auto-close
```
