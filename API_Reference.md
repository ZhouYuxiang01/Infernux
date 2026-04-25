# Infernux Core API Reference

## Overview

The Infernux Core runtime surface is exported by the `Infernux.ai_runtime` Python package, with frame-timing primitives provided by `Infernux.timing` (re-exported as `Infernux.Time`). Core is defined as the semantics-free runtime substrate used by adapters and agents to observe the active scene, drive input, mutate a bounded set of component fields, control play-mode lifecycle, and read frame timing. Domain semantics (action vocabularies, role names, gameplay heuristics) belong to adapters and are out of scope for this document, except where legacy Core APIs still embed them and are explicitly marked as such.

This reference documents only the symbols re-exported from [python/Infernux/ai_runtime/__init__.py](python/Infernux/ai_runtime/__init__.py) and the `Time` class in [python/Infernux/timing.py](python/Infernux/timing.py). Engine-internal modules (`Infernux.engine.*`), the C++ binding layer (`Infernux.lib`), and adapter packages (`Infernux.ai_adapters.*`) are not part of this surface.

---

## Observation

### EntityRecord

- **Module:** [Infernux.ai_runtime.types](python/Infernux/ai_runtime/types.py)
- **Signature:** `@dataclass(frozen=True, slots=True) class EntityRecord(id: int|str, name: str, parent_id: int|str|None, children_ids: list[int|str], component_types: list[str])`
- **Status:** Stable
- **Summary:** Immutable projection of a scene entity at observation time.
- **Behavior:** `to_dict()` returns the record as a plain dictionary via `dataclasses.asdict`. `component_types` is normalized through `world_state.normalize_type_name`; `"Transform"` is unconditionally included as the first entry.
- **Constraints / Notes:** Construction will raise `ValueError` (via `_build_entity_record`) if the underlying GameObject lacks a non-`None` `id`.

---

### list_entities

- **Module:** [Infernux.ai_runtime.world_state](python/Infernux/ai_runtime/world_state.py)
- **Signature:** `list_entities() -> list[EntityRecord]`
- **Status:** Stable
- **Summary:** Returns all entities in the active scene as `EntityRecord` projections.
- **Parameters:** None.
- **Returns:** A list of `EntityRecord`. Empty list when no active scene is bound or when `scene.get_all_objects()` raises.
- **Behavior:** Iterates the scene returned by `SceneManager.instance().get_active_scene()`. Per-object failures during record construction are silently skipped.
- **Related APIs:** `get_entity`, `find_by_component`, `WorldStateProjection`.

---

### get_entity

- **Module:** [Infernux.ai_runtime.world_state](python/Infernux/ai_runtime/world_state.py)
- **Signature:** `get_entity(entity_id: int|str) -> EntityRecord | None`
- **Status:** Stable
- **Summary:** Look up a single entity by id.
- **Parameters:** `entity_id` — scene entity identifier accepted by `scene.find_by_id`.
- **Returns:** The `EntityRecord` or `None` if the scene is unbound, the lookup raises, or the object is missing.
- **Related APIs:** `list_entities`, `find_by_component`.

---

### find_by_component

- **Module:** [Infernux.ai_runtime.query_api](python/Infernux/ai_runtime/query_api.py)
- **Signature:** `find_by_component(component_type: Any) -> list[EntityRecord]`
- **Status:** Stable
- **Summary:** Return entities whose `component_types` contain the normalized name of the requested type.
- **Parameters:** `component_type` — class object or string. Normalized via `world_state.normalize_type_name` (strips namespaces, `<class '...'>` wrappers, and `module.qualified.path` prefixes).
- **Returns:** Matching `EntityRecord` list. Empty when the normalized type name is empty.
- **Behavior:** Implemented as a linear scan over `list_entities()`; complexity is O(n × m) over scene size and average component count.
- **Related APIs:** `list_entities`, `find_in_radius`.

---

### find_in_radius

- **Module:** [Infernux.ai_runtime.query_api](python/Infernux/ai_runtime/query_api.py)
- **Signature:** `find_in_radius(position, radius: float) -> list[EntityRecord]`
- **Status:** Stable
- **Summary:** Returns entities whose colliders overlap the given sphere.
- **Parameters:** `position` — accepted by `Physics.overlap_sphere`. `radius` — sphere radius in world units.
- **Returns:** Deduplicated list of `EntityRecord`. Empty list when `Physics.overlap_sphere` raises.
- **Behavior:** Each collider is unwrapped through `.game_object` / `get_game_object()` / `.collider.game_object` / `.collider.get_game_object()` to recover an entity id, then re-projected via `get_entity`. Entities without an id, or whose `get_entity` projection fails, are skipped.
- **Constraints / Notes:** Depends on the native `Infernux.physics.Physics` binding being present.

---

### EntitySnapshot

- **Module:** [Infernux.ai_runtime.entity_observation](python/Infernux/ai_runtime/entity_observation.py)
- **Signature:** `@dataclass(frozen=True, slots=True) class EntitySnapshot(entity_id: int|str, name: str, position: tuple[float,float,float]|None, velocity: tuple[float,float,float]|None, component_types: list[str])`
- **Status:** Stable
- **Summary:** Immutable per-entity sample combining identity, transform position, and Rigidbody velocity.
- **Notes:** `position` / `velocity` are `None` when the underlying component or attribute is missing or fails coercion.

---

### EntityActivitySummary

- **Module:** [Infernux.ai_runtime.entity_observation](python/Infernux/ai_runtime/entity_observation.py)
- **Signature:** `@dataclass(frozen=True, slots=True) class EntityActivitySummary(entity_id: int|str, event_count: int, collision_count: int, moved: bool)`
- **Status:** Stable
- **Summary:** Aggregated activity statistics for one entity over a time window.

---

### get_entity_snapshot

- **Module:** [Infernux.ai_runtime.entity_observation](python/Infernux/ai_runtime/entity_observation.py)
- **Signature:** `get_entity_snapshot(entity_id: int|str) -> EntitySnapshot | None`
- **Status:** Stable
- **Summary:** Return a fresh `EntitySnapshot` for the given entity.
- **Returns:** `None` when no active scene is bound, the id is not found, or the world-state projection fails.
- **Behavior:** Resolves the GameObject via `scene.find_by_id`, then reads `transform.position` and `Rigidbody.velocity` via the shared vec3 coercion helper (accepts `(x,y,z)` objects, 3-element iterables; rejects strings/bytes).

---

### get_entity_snapshot_by_name

- **Module:** [Infernux.ai_runtime.entity_observation](python/Infernux/ai_runtime/entity_observation.py)
- **Signature:** `get_entity_snapshot_by_name(name: str) -> EntitySnapshot | None`
- **Status:** Stable
- **Summary:** Locate the first entity whose `name` matches exactly, then delegate to `get_entity_snapshot`.
- **Constraints / Notes:** Linear scan over `list_entities()`. First match by enumeration order is returned; ties are not disambiguated.

---

### get_entity_activity_summary

- **Module:** [Infernux.ai_runtime.entity_observation](python/Infernux/ai_runtime/entity_observation.py)
- **Signature:** `get_entity_activity_summary(entity_id: int, ms: int|float) -> EntityActivitySummary`
- **Status:** Stable
- **Summary:** Counts events whose `source_entity_id` or `target_entity_id` equals `entity_id` within the `ms` window. Collision count counts events whose `type` contains `"Collision"` or `"Trigger"`. `moved` is `True` when the current snapshot velocity magnitude exceeds `1e-6`.
- **Constraints / Notes:** A non-coercible `ms` defaults to `0.0`, which yields an empty event list. `moved` is sampled from the current snapshot, not integrated over the window.

---

### get_recent_events

- **Module:** [Infernux.ai_runtime.observation_api](python/Infernux/ai_runtime/observation_api.py) (re-exported); implementation in [Infernux.ai_runtime.event_stream](python/Infernux/ai_runtime/event_stream.py)
- **Signature:** `get_recent_events(ms: int|float) -> list[dict[str, Any]]`
- **Status:** Stable
- **Summary:** Return events from the native `RuntimeEventCollector` covering the last `ms` milliseconds.
- **Returns:** A list of event dicts with keys `frame`, `timestamp`, `sequence`, `type`, `source_entity_id`, `target_entity_id`, `agent_id`, `payload`. Empty list when `ms <= 0`, when `ms` is non-coercible, or when the native collector is unavailable.
- **Behavior:** `payload` is normalized — only `int` / `float` / `bool` / `str` / 3-tuple `vec3` values survive. Other types are dropped (not stringified). `source_entity_id`, `target_entity_id`, and `agent_id` are coerced via `_coerce_optional_int`. `timestamp` is the native collector timestamp in milliseconds.
- **Agent attribution:** Single-agent input injection events use `agent_id = 0`. System-level events such as play-mode lifecycle and contact events use `agent_id = None`.

---

### set_event_filter

- **Module:** [Infernux.ai_runtime.event_stream](python/Infernux/ai_runtime/event_stream.py)
- **Signature:** `set_event_filter(event_types: list[str]|None = None, source_entity_ids: list[int]|None = None, target_entity_ids: list[int]|None = None, agent_id: int|None = None) -> None`
- **Status:** Stable
- **Summary:** Install a server-side filter on the native event collector.
- **Behavior:** When `agent_id` is provided, the call is attempted against the native binding using the spec-§3.10 keyword form `set_event_filter(types, sources, targets, agent_id=…)`. Current native bindings support this parameter. For compatibility with stale native builds, a `TypeError` falls back to the legacy 3-argument positional form, silently dropping the agent constraint. Returns silently when the collector is unavailable. Coercion failures on `source_entity_ids` / `target_entity_ids` cause the call to be dropped silently.
- **Related APIs:** `clear_event_filter`, `get_recent_events`.

---

### clear_event_filter

- **Module:** [Infernux.ai_runtime.event_stream](python/Infernux/ai_runtime/event_stream.py)
- **Signature:** `clear_event_filter() -> None`
- **Status:** Stable
- **Summary:** Remove any active filter installed via `set_event_filter`. No-op when the native collector is unavailable.

---

### Recorder

- **Module:** [Infernux.ai_runtime.recorder](python/Infernux/ai_runtime/recorder.py)
- **Signature:** `class Recorder` with `get_recent_events(ms: int|float) -> list[dict[str, Any]]` and `clear() -> None`
- **Status:** Stable
- **Summary:** Thin object wrapper over the event stream. `get_recent_events` delegates to the module-level function; `clear()` calls `event_stream.clear_events()` on the native collector.
- **Constraints / Notes:** Holds no per-instance state; multiple instances are interchangeable.

---

### WorldStateProjection

- **Module:** [Infernux.ai_runtime.world_state](python/Infernux/ai_runtime/world_state.py)
- **Signature:** `class WorldStateProjection` with `@staticmethod list_entities() -> list[EntityRecord]` and `@staticmethod get_entity(entity_id: int|str) -> EntityRecord | None`
- **Status:** Stable
- **Summary:** Static-method facade over `list_entities` / `get_entity`. Provided as a stable namespace handle for callers that prefer object-style access.

---

## Control

### ControlSignal

- **Module:** [Infernux.ai_runtime.control_signal](python/Infernux/ai_runtime/control_signal.py)
- **Signature:** `@dataclass class ControlSignal(channel_id: int = 0, axes: dict[str, float] = {}, buttons: dict[str, bool] = {}, duration_ms: int|None = None, timestamp_ms: int|None = None)`
- **Status:** Stable
- **Summary:** Generic, semantics-free input carrier on a logical channel.
- **Constraints / Notes:** `channel_id = 0` is reserved for the default / single-agent case. `axes` are clamped to `[-1.0, 1.0]` on submission; NaN axis values are coerced to `0.0`. `buttons` are level-triggered (`True` means "held"), not edge-triggered. `duration_ms` is a hint that backends may use to auto-clear; `None` persists until overwritten or cleared. Multi-channel arbitration is out of scope for v1.

---

### submit_control

- **Module:** [Infernux.ai_runtime.control_signal](python/Infernux/ai_runtime/control_signal.py)
- **Signature:** `submit_control(signal: ControlSignal) -> None`
- **Status:** Stable
- **Summary:** Normalize and submit a control signal under last-write-wins semantics for its `channel_id`.
- **Behavior:** Axis values are coerced to float and clamped; non-coercible axes are dropped. Buttons are coerced to `bool`. `duration_ms` is coerced to a non-negative int or `None`. `timestamp_ms` is filled with `time.monotonic() * 1000` if `None` or non-coercible. The normalized signal is stored in the per-process `_channel_state` map and dispatched to the native `InputManager.submit_channel_signal` if available; otherwise it is lowered through `_legacy_input_bridge.apply_signal`.
- **Raises:** `TypeError` when `signal` is not a `ControlSignal` instance.
- **Related APIs:** `clear_control`, `get_control_state`.

---

### clear_control

- **Module:** [Infernux.ai_runtime.control_signal](python/Infernux/ai_runtime/control_signal.py)
- **Signature:** `clear_control(channel_id: int|None = None) -> None`
- **Status:** Stable
- **Summary:** Clear one or all channels.
- **Behavior:** `channel_id=None` clears the entire `_channel_state` map and either clears all native channels (`InputManager.clear_channel(-1)`) or, if the native binding is unavailable, calls `_legacy_input_bridge.clear()`. With an integer `channel_id`, only that entry is removed; the legacy bridge is invoked only when the native call fails and the channel is the default channel (`0`).

---

### get_control_state

- **Module:** [Infernux.ai_runtime.control_signal](python/Infernux/ai_runtime/control_signal.py)
- **Signature:** `get_control_state(channel_id: int = 0) -> ControlSignal | None`
- **Status:** Stable
- **Summary:** Return the last submitted control signal for a channel.
- **Behavior:** Prefers the native `InputManager.get_channel_state(cid)` when available. Native `InputChannel` objects are projected back into Python `ControlSignal` instances before being returned, so callers always receive `ControlSignal | None`. If no native state is available, falls back to the Python-side `_channel_state` cache. Non-coercible `channel_id` defaults to `0`.
- **Constraints / Notes:** Canonical reader for submitted control signals; pairs with `submit_control` and `clear_control`.

---

### EvaluationResult

- **Module:** [Infernux.ai_runtime.evaluation](python/Infernux/ai_runtime/evaluation.py)
- **Signature:** `@dataclass(frozen=True) class EvaluationResult(success: bool, score: float, failures: list[str], metrics: dict[str, Any])`
- **Status:** Stable
- **Summary:** Immutable result of an `evaluate(...)` call.

---

### evaluate

- **Module:** [Infernux.ai_runtime.evaluation](python/Infernux/ai_runtime/evaluation.py)
- **Signature:** `evaluate(metrics: dict[str, Any]) -> EvaluationResult`
- **Status:** Stable
- **Summary:** Reduce a metrics dict to a pass/fail evaluation.
- **Behavior:** Only entries whose value is a `bool` participate in scoring; each `False` bool is appended to `failures`. `score` is `(boolean_count - failure_count) / boolean_count`, or `1.0` when no boolean keys exist. `success` is `True` iff `failures` is empty. The original metrics dict is shallow-copied into `EvaluationResult.metrics`.

---

### record_action

- **Module:** [Infernux.ai_runtime.adjustment](python/Infernux/ai_runtime/adjustment.py)
- **Signature:** `record_action(action: dict[str, Any], *, agent_id: int|None = None) -> None`
- **Status:** Stable
- **Summary:** Store the most recent action under the given agent's adjustment bucket for use by a subsequent `adjust_input(...)` call.
- **Behavior:** Action is `deepcopy`'d. `agent_id=None` targets the default bucket (`0`). Non-coercible `agent_id` also coerces to `0`.
- **Related APIs:** `adjust_input`, `reset_adjustment`.

---

### adjust_input

- **Module:** [Infernux.ai_runtime.adjustment](python/Infernux/ai_runtime/adjustment.py)
- **Signature:** `adjust_input(result: EvaluationResult, *, agent_id: int|None = None) -> dict[str, Any] | None`
- **Status:** Stable
- **Summary:** When evaluation reports failure, return a scaled-up retry suggestion derived from the last `record_action(...)` for that agent.
- **Behavior:** Returns `None` when `result.success` is `True`, when no prior action is recorded, or when the bucket's `retry_count` has reached `_MAX_RETRY_COUNT` (5). On a successful step, `retry_count` increments by 1 and `intensity_scale` is multiplied by `_INTENSITY_MULTIPLIER` (1.5), capped at `_MAX_INTENSITY_SCALE` (5.0). Numeric (non-bool) entries inside `params` are scaled by the new `intensity_scale`; non-numeric entries are deep-copied unchanged. The returned dict has shape `{"type": …, "params": {...}}`.
- **Constraints / Notes:** State is per-agent and persists across calls until cleared by `reset_adjustment`. There is no automatic reset on play-mode exit; callers are responsible for invoking `reset_adjustment` at session boundaries.

---

### reset_adjustment

- **Module:** [Infernux.ai_runtime.adjustment](python/Infernux/ai_runtime/adjustment.py)
- **Signature:** `reset_adjustment(agent_id: int|None = None) -> None`
- **Status:** Stable
- **Summary:** Clear adjustment bookkeeping. `agent_id=None` clears every bucket; otherwise only the named bucket is removed.

---

## World Edit

### EditResult

- **Module:** [Infernux.ai_runtime.world_edit](python/Infernux/ai_runtime/world_edit.py)
- **Signature:** `@dataclass(frozen=True, slots=True) class EditResult(ok: bool, preview: bool, changes: list[FieldChange], message: str|None = None)`
- **Status:** Stable
- **Summary:** Outcome of a world-edit call. Implements `__bool__` returning `self.ok`.

---

### FieldChange

- **Module:** [Infernux.ai_runtime.world_edit](python/Infernux/ai_runtime/world_edit.py)
- **Signature:** `@dataclass(frozen=True, slots=True) class FieldChange(field_path: str, old_value: Any, new_value: Any)`
- **Status:** Stable
- **Summary:** Describes a single field mutation produced or previewed by a world-edit call. `field_path` follows the `Component.field` convention (e.g. `"Transform.position"`).

---

### move_entity

- **Module:** [Infernux.ai_runtime.world_edit](python/Infernux/ai_runtime/world_edit.py)
- **Signature:** `move_entity(entity_id: int, position: tuple[float, float, float], preview: bool = False, mode: str = "auto") -> EditResult`
- **Status:** Stable
- **Summary:** Set `Transform.position` on the named entity.
- **Behavior:** Resolves the GameObject via `scene.find_by_id`, fetches its `Transform` via `get_component("Transform")`, and coerces `position` to `Vector3` through the shared vec3 coercion helper (accepts `(x,y,z)` objects or 3-element iterables; rejects strings/bytes and any other arity). When `preview=True`, the resulting `EditResult` describes the intended change without writing it.
- **Mode policy:** `mode="auto"` uses editor undo when in Edit Mode and direct mutation when in Play Mode. `mode="edit"` requires an available `UndoManager`; if undo cannot be recorded, the call returns `ok=False, message="undo unavailable in edit mode"` instead of silently mutating. `mode="runtime"` is only valid during Play Mode. Invalid mode strings normalize to `"auto"`.
- **Failure messages:** `ok=False` and `message` may be one of `"entity not found"`, `"transform unavailable"`, `"invalid position"`, `"failed to set position"`, `"undo unavailable in edit mode"`, `"edit mode mutation requested while play mode is active"`, or `"runtime mutation requested outside play mode"`.

---

### set_component

- **Module:** [Infernux.ai_runtime.world_edit](python/Infernux/ai_runtime/world_edit.py)
- **Signature:** `set_component(entity_id: int, key: str, value: Any, preview: bool = False, mode: str = "auto") -> EditResult`
- **Status:** Stable
- **Summary:** Mutate one of the allowlisted component fields.
- **Behavior:** The allowlist (`_ALLOWED_COMPONENT_FIELDS`) is `{"Transform": {"position"}, "Rigidbody": {"velocity", "mass"}}`. The component name is derived from `key`: `"position"` → `Transform`; `"velocity"` / `"mass"` → `Rigidbody`. Any other `key` returns `ok=False, message="field not allowed"`. `position` and `velocity` are coerced via `_coerce_vec3`, which wraps the shared vec3 tuple coercion helper. `mass` requires a non-bool int or float; bools and other types yield `"invalid numeric value"`. `preview=True` returns the planned change without writing.
- **Mode policy:** Same as `move_entity`: `mode="auto"` uses undo in Edit Mode and direct mutation in Play Mode; `mode="edit"` fails visibly when undo is unavailable; `mode="runtime"` is only valid during Play Mode.
- **Failure messages:** `"entity not found"`, `"component unavailable"`, `"field not allowed"`, `"invalid vec3"`, `"invalid numeric value"`, `"failed to set field"`, `"undo unavailable in edit mode"`, `"edit mode mutation requested while play mode is active"`, or `"runtime mutation requested outside play mode"`.
- **Constraints / Notes:** No mutation paths exist beyond this allowlist; arbitrary component fields cannot be edited through Core.

---

## Lifecycle

### clear_runtime_control_state

- **Module:** [Infernux.ai_runtime.lifecycle](python/Infernux/ai_runtime/lifecycle.py)
- **Signature:** `clear_runtime_control_state() -> None`
- **Status:** Stable
- **Summary:** Clear all AI-injected control state across both the generic channel path and the legacy action path.
- **Behavior:** Calls `control_signal.clear_control()` and then attempts to clear legacy action state through `input_api.clear_actions()`. Exceptions are suppressed through the lifecycle safety wrapper so Play Mode transitions are not interrupted.
- **Related APIs:** `clear_control`, `on_enter_play_mode`, `on_exit_play_mode`.

---

### enter_play_mode

- **Module:** [Infernux.ai_runtime.control_api](python/Infernux/ai_runtime/control_api.py)
- **Signature:** `enter_play_mode() -> bool`
- **Status:** Stable
- **Summary:** Transition the engine into play mode and drain the deferred-task queue until idle.
- **Behavior:** Acquires (or constructs) the `PlayModeManager` singleton via `PlayModeManager.instance()`. Returns `True` immediately if `is_playing` is already true. Otherwise calls `manager.enter_play_mode()`; on `False` or exception, returns `False`. After a successful transition, calls `_drain_deferred_task_runner()` which ticks `DeferredTaskRunner.instance()` up to 64 times waiting for `is_busy` to clear. Final return value is `bool(manager.is_playing)`.
- **Constraints / Notes:** Returns `False` rather than raising on any internal failure. Safe to call when already in play mode.

---

### exit_play_mode

- **Module:** [Infernux.ai_runtime.control_api](python/Infernux/ai_runtime/control_api.py)
- **Signature:** `exit_play_mode() -> bool`
- **Status:** Stable
- **Summary:** Transition the engine out of play mode and drain the deferred-task queue until idle.
- **Behavior:** Returns `True` immediately if `is_playing` is already false. Otherwise calls `manager.exit_play_mode()`; on `False` or exception, returns `False`. After the call, drains `DeferredTaskRunner.instance()` for up to 64 ticks. Final return value is `not manager.is_playing`.
- **Constraints / Notes:** Returns `False` rather than raising on any internal failure. Safe to call when already out of play mode.

---

### pause

- **Module:** [Infernux.ai_runtime.control_api](python/Infernux/ai_runtime/control_api.py)
- **Signature:** `pause() -> bool`
- **Status:** Stable
- **Summary:** Pause the active play session.
- **Behavior:** Returns `True` if already paused. Returns `False` if not currently playing. Otherwise delegates to `manager.pause()`; exceptions surface as `False`.

---

### resume

- **Module:** [Infernux.ai_runtime.control_api](python/Infernux/ai_runtime/control_api.py)
- **Signature:** `resume() -> bool`
- **Status:** Stable
- **Summary:** Resume a paused play session.
- **Behavior:** Returns `True` if already playing and not paused. Returns `False` if not in a paused state. Otherwise delegates to `manager.resume()`; exceptions surface as `False`.

---

### step

- **Module:** [Infernux.ai_runtime.control_api](python/Infernux/ai_runtime/control_api.py)
- **Signature:** `step(n: int) -> int`
- **Status:** Stable
- **Summary:** Advance `n` frames while the manager is paused.
- **Returns:** The number of frames actually stepped.
- **Behavior:** Returns `0` for non-coercible or non-positive `n`. Returns `0` when the manager is unavailable or not paused. Each iteration calls `manager.step_frame()`; on the first exception, the loop terminates and returns the count completed so far. Does not implicitly clear control signals (consistent with `submit_control` semantics).

---

## Runtime / Timing

### Time

- **Module:** [Infernux.timing](python/Infernux/timing.py) (also exposed as `Infernux.Time`)
- **Signature:** `class Time` (metaclass `_TimeMeta`); access members on the class object directly. Never instantiate.
- **Status:** Stable

#### Class properties

| Member | Type | Access | Description |
|---|---|---|---|
| `Time.time` | `float` | read | Scaled elapsed seconds since play mode started. |
| `Time.delta_time` | `float` | read | Scaled duration of the last frame. |
| `Time.unscaled_time` | `float` | read | Unscaled (wall-clock) elapsed seconds since play mode started. |
| `Time.unscaled_delta_time` | `float` | read | Unscaled duration of the last frame. |
| `Time.game_delta_time` | `float` | read | Game-only frame cost in seconds, excluding editor panel overhead. `0` before the first rendered frame. |
| `Time.fixed_delta_time` | `float` | read/write | Physics step interval. Default `0.02` (50 Hz). Setter clamps to `>= 0.001`. |
| `Time.fixed_time` | `float` | read | Scaled time accumulated across fixed steps. |
| `Time.fixed_unscaled_time` | `float` | read | Unscaled time accumulated across fixed steps. |
| `Time.time_scale` | `float` | read/write | Global time multiplier. Setter clamps to `>= 0.0` and synchronises into `PlayModeManager._time_scale` if available. |
| `Time.frame_count` | `int` | read | Frames elapsed since play mode started. |
| `Time.realtime_since_startup` | `float` | read | Wall-clock seconds since the engine process launched. |
| `Time.maximum_delta_time` | `float` | read/write | Upper clamp for `delta_time` to prevent spiral-of-death. Default `0.1`. Setter clamps to `>= 0.01`. |

#### Engine hooks

- **`Time._reset()`** — Resets `_time`, `_delta_time`, `_unscaled_delta_time`, `_game_delta_time`, `_time_scale`, `_frame_count`, `_unscaled_time`, `_fixed_time`, `_fixed_unscaled_time`. Called when entering play mode.
- **`Time._tick(raw_delta_time: float)`** — Clamps `raw_delta_time` to `[0.0, maximum_delta_time]`, then advances `_unscaled_delta_time`, `_delta_time = clamped * _time_scale`, `_time`, `_unscaled_time`, and `_frame_count`. Called from `PlayModeManager.tick`.
- **`Time._tick_fixed(fixed_dt: float)`** — Advances `_fixed_time` by `fixed_dt * _time_scale` and `_fixed_unscaled_time` by `fixed_dt`.

#### Constraints / Notes

- Member access is class-level only; do not instantiate `Time()`.
- The `time_scale` setter swallows `ImportError` from the `PlayModeManager` import (logged via `Debug.log`) and prints other exceptions to `stderr`. The setter therefore never raises into the caller.
- `Time` state is process-global; there is no per-channel or per-agent timing.

---

## Legacy / Transitional APIs

The following symbols are still re-exported from `Infernux.ai_runtime` and remain functional, but are explicitly marked as legacy or transitional in the source. New Core-level callers should not depend on them.

### get_player_snapshot

- **Module:** [Infernux.ai_runtime.observation_api](python/Infernux/ai_runtime/observation_api.py)
- **Signature:** `get_player_snapshot() -> PlayerSnapshot | None`
- **Status:** Legacy / Deprecated (emits `DeprecationWarning`; removal target v2.0)
- **Summary:** Heuristic player lookup. Searches the active scene by tag `"Player"`, then by `CharacterController` component, then by `Rigidbody`. Returns a `PlayerSnapshot` capturing `entity_id`, `transform.position`, `Rigidbody.velocity`, and a grounded probe (`grounded` or `is_grounded` on `CharacterController`, called if callable).
- **Notes:** Lives inside Core for backwards compatibility but encodes platformer-shaped semantics that are forbidden under the v1.3+ semantic boundary (the module is grandfathered).

### PlayerSnapshot

- **Module:** [Infernux.ai_runtime.observation_api](python/Infernux/ai_runtime/observation_api.py)
- **Signature:** `@dataclass(frozen=True) class PlayerSnapshot(entity_id: int|str, position: Any|None, velocity: Any|None, grounded: Any|None)`
- **Status:** Legacy

### get_activity_summary

- **Module:** [Infernux.ai_runtime.observation_api](python/Infernux/ai_runtime/observation_api.py)
- **Signature:** `get_activity_summary(ms: int|float) -> ActivitySummary`
- **Status:** Legacy
- **Summary:** Convenience aggregate that returns `event_count`, `jumped`, `attacked` over the window. `jumped`/`attacked` are decided by string-matching event types (`<action>triggered`, `<action>trigger`) and by the `inputinjected` event's `action` payload field.

### ActivitySummary

- **Module:** [Infernux.ai_runtime.observation_api](python/Infernux/ai_runtime/observation_api.py)
- **Signature:** `@dataclass(frozen=True) class ActivitySummary(event_count: int, jumped: bool, attacked: bool)`
- **Status:** Legacy

### ActionType

- **Module:** [Infernux.ai_runtime.input_api](python/Infernux/ai_runtime/input_api.py)
- **Signature:** `class ActionType` with class attributes `Jump = "jump"`, `Attack = "attack"`, `Move = "move"`
- **Status:** Legacy (grandfathered semantic vocabulary; Phase 4 removal target v2.0)

### send_action

- **Module:** [Infernux.ai_runtime.input_api](python/Infernux/ai_runtime/input_api.py)
- **Signature:** `send_action(action: str, **kwargs) -> bool`
- **Status:** Legacy / Deprecated (emits `DeprecationWarning`)
- **Summary:** Lowers a named action to `InputManager.set_virtual_action`. Recognises only `"jump"`, `"attack"`, `"move"` (the latter accepting `x`, `y` floats). Returns `False` for unknown actions or if the manager is unavailable.

### clear_actions

- **Module:** [Infernux.ai_runtime.input_api](python/Infernux/ai_runtime/input_api.py)
- **Signature:** `clear_actions() -> None`
- **Status:** Legacy
- **Summary:** Calls `InputManager.clear_virtual_actions()`. Safe no-op when the manager is unavailable.

### `_legacy_input_bridge` (module)

- **Module:** [Infernux.ai_runtime._legacy_input_bridge](python/Infernux/ai_runtime/_legacy_input_bridge.py)
- **Status:** Transitional (private)
- **Summary:** Lowers a normalized `ControlSignal` to the platformer-shaped `VirtualInputState` (`jump`, `attack`, `move_x`, `move_y`) when the native `InputChannel` binding is unavailable. Buttons / axes outside this set are silently dropped.
- **Notes:** Quarantined private module. Listed in `GRANDFATHERED_MODULES` and scheduled to be replaced by direct native channel submission.

---

## Known Contract Gaps

- **`ai_runtime._coercion` is private.** The shared `coerce_vec3_tuple` helper backs Core modules such as event projection and world editing, but it is not part of the public Core API surface. External callers should not import it directly.
- **No automatic adjustment reset across sessions.** `enter_play_mode()` does not call `reset_adjustment()`. `_STATES` therefore persists across `enter_play_mode()` calls within the same Python process.
- **`set_event_filter(agent_id=…)` has a compatibility fallback.** Current native bindings support the `agent_id` keyword. If a stale native binary is loaded, the Python layer may fall back to the legacy 3-argument positional form, which does not propagate the agent constraint. The caller has no programmatic way to detect which path executed.
- **Native vs. legacy input dispatch is opaque.** `submit_control` and `clear_control` first attempt the native `InputManager.submit_channel_signal` / `clear_channel` path, then fall back to `_legacy_input_bridge`. The dispatch path actually taken is not surfaced to the caller. Under the legacy path, only the `jump` / `attack` buttons and `move_x` / `move_y` axes are addressable; other channel keys are dropped.
- **Allowlist mismatch in `set_component`.** `_get_allowed_component_name("position")` returns `"Transform"`, which then re-checks against `_ALLOWED_COMPONENT_FIELDS["Transform"] = {"position"}`. The allowlist is only meaningful for the `Rigidbody` keys. The check is consistent but redundant.
- **`PlayerSnapshot.position` / `velocity` / `grounded` are typed `Any`.** Unlike `EntitySnapshot`, the legacy snapshot does not coerce vectors to `tuple[float, float, float]`; consumers receive whatever object the underlying component exposes (typically a native `Vector3`).
- **`get_entity_activity_summary.entity_id` is annotated `int`** despite `_is_related_event` doing direct `==` comparison and the rest of the entity API accepting `int | str`. String ids will work at runtime but violate the declared signature.
- **`evaluate(...)` ignores non-boolean metric values for scoring.** A metrics dict containing only numeric values yields `success=True, score=1.0` regardless of the values, because only `bool` entries participate in the failure tally. This is by design but is not documented in the function body.
- **Event payload coercion is lossy.** `_coerce_payload_value` drops any non-(int/float/bool/str/vec3) payload value. There is no caller-visible signal indicating that values were dropped versus genuinely absent.
- **`Recorder.clear()` clears events globally.** It calls `event_stream.clear_events()`, which flushes the singleton native collector. Multiple `Recorder` instances therefore share clearing state.
- **`get_control_state` is omitted from the package `__all__`** of `Infernux.ai_runtime`, although it is a public symbol of `control_signal` and is the canonical reader for submitted signals. Callers must import it from the submodule.