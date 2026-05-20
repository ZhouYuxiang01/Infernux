# Recipe: Debug Runtime Errors

## Goal

Find why a runtime operation, script, scene load, or Play Mode transition
failed.

## Tool Sequence

1. `runtime_read_errors(include_warnings=false, limit=50)`
2. `console_read`
3. `mcp_health`
4. `runtime_explain_current_scene`
5. `mcp_session_log_read` if session logging is enabled
6. `mcp_trace_current` if tracing is active

## Success Criteria

- You identify the failing subsystem: scene loading, script import, Play Mode,
  runtime control, component mutation, or MCP transport.
- You can name the failing file/tool/object where possible.
- You propose the smallest fix or recovery action.

## Recovery Patterns

- Script import error: fix the Python file, call `asset_refresh`, then retry
  Play Mode.
- Dirty scene blocks Play Mode: call `scene_save` if persistence is intended.
- Stale object ID: reacquire with `scene_query_objects`.
- Stuck control: call `runtime_clear_control`.
- Main thread timeout: wait, inspect modal/editor state, then retry one smaller
  operation.
