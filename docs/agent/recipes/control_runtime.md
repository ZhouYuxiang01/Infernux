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
3. `runtime_experiment_begin(mode="run")`
4. `runtime_experiment_mark_health_check()`
5. `runtime_get_object_state` or `runtime_get_world_snapshot`
6. `runtime_submit_control(channel_id=0, axes={...}, duration_ms=<short>, agent_id=0)`
7. `runtime_run_for(seconds=<small>, stop_on_error=true)`
8. `runtime_clear_control(channel_id=0)`
9. `runtime_get_object_state` or `runtime_get_world_snapshot`
10. `runtime_assert`
11. `runtime_read_errors(include_warnings=false)`
12. `runtime_experiment_end()`

## Success Criteria

- Runtime state changed in the intended direction.
- The experiment guard allowed exactly one control path.
- The control channel was cleared.
- `runtime_read_errors` reports no blocking errors.

## Recovery

- If nothing moved, check whether the scene script reads the same axes you
  submitted.
- If Play Mode does not start, call `runtime_read_errors` and inspect script
  loader errors.
- If the object ID becomes invalid after reload, reacquire it with
  `scene_query_objects`.
- If the guard rejects control, call `runtime_experiment_status` and either
  mark the health check or end/restart the experiment.
