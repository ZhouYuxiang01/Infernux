# Agent Documentation

This folder is the first-stop documentation for external agents operating the
Infernux AI Runtime through MCP or Python APIs.

For the full repository documentation map, see
[docs/README.md](../README.md). For the hand-written runtime API contract, see
[API_Reference.md](../../API_Reference.md).

Start here:

- `quickstart.md` - first-contact sequence, operating loop, mode rules, and
  recipe index.
- `recipes/observe_scene.md` - read the active scene before acting.
- `recipes/control_runtime.md` - drive Play Mode through guarded generic
  `ControlSignal` input.
- `recipes/safe_world_edit.md` - make bounded Edit Mode changes and verify
  them with transaction previews and world diffs.
- `recipes/debug_runtime_errors.md` - inspect runtime, script, scene, and MCP
  failures.

Reference demos:

- `scripts/agent_world_operation_demo.py` - world snapshot, bounded edit,
  runtime control, diff, and error-read smoke test.
- `scripts/agent_pellet_chase_demo.py` - top-down movement, collision, state
  reads, visual capture, and runtime guard validation.
- `scripts/agent_side_scroller_demo.py` - platformer movement, jumping,
  collectibles, finish-state checks, visual capture, and runtime guard
  validation.
- `scripts/agent_voxel_sandbox_demo.py` - Minecraft-like voxel layout
  generation, generic control, block selection, mining, placement, visual
  capture, and runtime guard validation.

The engine is not the agent. It exposes the world state, engine-internal Game
Render Target capture, lifecycle, control, events, bounded editing, and
verification surfaces that external agents use to operate the project.

Agent-facing docs intentionally describe how to operate the runtime. They do
not replace the API contract in [API_Reference.md](../../API_Reference.md),
and they should not define new gameplay semantics inside the AI Runtime Core.
