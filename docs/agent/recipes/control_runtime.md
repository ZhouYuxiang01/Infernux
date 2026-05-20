# Recipe: Control Runtime

## Goal

Drive a live runtime object through generic AI Runtime control instead of
hard-coded gameplay actions.

## Preconditions

- The scene is saved and ready for Play Mode.
- You know which script/component consumes `Input.get_axis` or equivalent
  runtime input.
- You have a baseline world snapshot or object state.

## Tool Sequence

1. `editor_play`
2. `runtime_wait(play_state="playing")`
3. `runtime_get_object_state` or `runtime_get_world_snapshot`
4. `runtime_submit_control(channel_id=0, axes={...}, duration_ms=<short>, agent_id=0)`
5. `runtime_run_for(seconds=<small>, stop_on_error=true)`
6. `runtime_clear_control(channel_id=0)`
7. `runtime_get_object_state` or `runtime_get_world_snapshot`
8. `runtime_assert`
9. `runtime_read_errors(include_warnings=false)`

## Success Criteria

- Runtime state changed in the intended direction.
- The control channel was cleared.
- `runtime_read_errors` reports no blocking errors.

## Recovery

- If nothing moved, check whether the scene script reads the same axes you
  submitted.
- If Play Mode does not start, call `runtime_read_errors` and inspect script
  loader errors.
- If the object ID becomes invalid after reload, reacquire it with
  `scene_query_objects`.
