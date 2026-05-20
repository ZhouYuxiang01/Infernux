# Recipe: Safe World Edit

## Goal

Make a bounded editor-mode world change and verify the exact diff.

## Preconditions

- The editor is in Edit Mode.
- The active scene is not loading.
- You have exact target IDs.

## Tool Sequence

1. `runtime_get_world_snapshot(include_components=true, include_fields=true)`
2. `runtime_get_component_schema(component_type=...)`
3. Apply one small edit, such as:
   - `transform_set`
   - `component_set_field`
   - `hierarchy_create_object`
4. `runtime_get_world_snapshot(include_components=true, include_fields=true)`
5. `runtime_diff_world_snapshots`
6. `runtime_read_errors`
7. `scene_save` only if the edit should persist

## Success Criteria

- The diff shows the intended object/component/field change.
- No unrelated objects changed.
- Runtime errors remain clear.

## Recovery

- If Play Mode is active, call `editor_stop` and wait for Edit Mode.
- If a component field is unknown, call `component_describe_type` or
  `runtime_get_component_schema`.
- If the diff is larger than expected, stop and report the extra changes.
