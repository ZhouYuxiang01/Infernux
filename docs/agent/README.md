# Agent Documentation

This folder is the first-stop documentation for external agents operating the
Infernux AI Runtime through MCP or Python APIs.

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

The engine is not the agent. It exposes the world state, visible Game View
capture, lifecycle, control, events, bounded editing, and verification surfaces
that external agents use to operate the project.
