# Recipe: Observe Scene

## Goal

Build a compact, accurate model of the active scene before changing anything.

## Preconditions

- MCP server is reachable.
- Editor main thread queue is ready.

## Tool Sequence

1. `agent_bootstrap`
2. `mcp_health`
3. `runtime_explain_current_scene`
4. `runtime_get_world_snapshot(include_components=true, include_fields=true)`
5. `scene_query_summary`
6. `scene_query_objects` for exact targets

## Success Criteria

- You know the active scene name and play state.
- You have exact object IDs for targets.
- You know relevant component types and writable fields.
- You have not mutated the scene.

## Recovery

- If the scene is loading, call `runtime_wait`.
- If no scene is active, use `scene_open` or ask the user which scene to open.
- If a target is ambiguous, query by exact name, path, tag, or component.
