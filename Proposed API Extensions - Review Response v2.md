# Infernux Proposed API Extensions — Review Response (v2)

## Status

- **Type:** Architecture Review Response
- **Based on:** *Proposed API Extensions* (Draft) + Review Response v1
- **Supersedes:** Review Response v1
- **Goal:** Converge proposal into a Core-aligned, semantics-safe API set with a definitive, implementable API list
- **Intended consumer:** Author of the next `AI_FIRST_ENGINE_v1_SPEC_PATCH` revision

---

## 1. Summary

The overall direction of the proposed API extensions is valid and aligned with the long-term goal:

> Enable AI to operate across runtime and editor environments.

The original Draft, however, contains three categories of issues that must be resolved before adoption:

1. Duplication or contract mismatch with existing Core APIs
2. Violations of the semantic boundary (Core vs Adapter)
3. Layer violations (Engine / Adapter / Agent responsibilities mixed into Core)

This v2 response reduces the Draft to **exactly 8 new Core APIs**, names every rejected API explicitly, defines the multi-agent contract, and clarifies the error-handling rule so downstream implementers have no remaining design decisions to make.

---

## 2. Category A — Redundant or Inconsistent APIs

These APIs MUST NOT be introduced as new Core APIs.

| Proposed API | Existing Implementation | Issue | Resolution |
|---|---|---|---|
| `get_scene_graph()` | `list_entities()` → `EntityRecord` (`parent_id`, `children_ids`) | Duplicate abstraction | Implement as utility `scene_graph_from_entities(records)` outside `ai_runtime`. |
| `get_object_components(entity_id)` | `EntityRecord.component_types` | Redundant | Remove. |
| `enter_play_mode() -> None` | `control_api.enter_play_mode() -> bool` (drains `DeferredTaskRunner`) | Contract mismatch — loses return value and drain semantics | Preserve existing signature; do not redefine. |
| `set_component_field(...) -> None` | `world_edit.set_component(...) -> EditResult` (with allowlist + `preview`) | Loss of preview, allowlist, and structured failure | Reuse `set_component`. |
| `find_nearest()` | Three-line composition over `find_in_radius` | Not a primitive | Document as a recipe in user docs; do not add code. |

---

## 3. Category B — Semantic Boundary Violations

These APIs introduce domain semantics into Core and MUST be rejected.

### Problematic APIs

- `find_by_tag(tag)`
- `reacquire_entity(name)`
- `query_entities({...})`

### Issues

- Reintroduce string-based gameplay semantics (`tag`, `name`) that the v1.3 semantic-boundary guard is actively removing.
- Conflict with the planned removal of grandfathered modules (`get_player_snapshot`, `ActionType`).
- Embed a filter-expression DSL inside Core, which becomes a permanent maintenance and validation burden.

### Correct Placement

These belong in the **Adapter layer** via the existing protocol:

```
Adapter.resolve_semantic_entity(scene, role) -> int | None
```

Core MUST NOT:

- interpret tags
- understand roles
- execute semantic queries

---

## 4. Category C — Layer Violations

### 4.1 Asset APIs

**Proposed:** `list_assets`, `load_asset`, `instantiate_prefab`, `save_prefab`

**Problem:** These are Engine / Editor responsibilities. Equivalent functionality already exists in `Infernux.engine.prefab_manager` and `Infernux.engine.resources_manager`.

**Resolution:** Expose any AI-facing surface as a thin wrapper inside the **existing `Infernux.engine` package** (no new top-level package required). Do NOT add to `Infernux.ai_runtime`.

### 4.2 Planning APIs

**Proposed:** `create_task`, `add_step`, `run_task`, `get_task_status`, `cancel_task`

**Problem:** This is Agent decision logic. The Draft itself states *"Agent handles decision-making"* in §2 yet places task management inside Core in §11.

**Resolution:** Ship as a **separate package**, either:

- out-of-repo: `infernux-planner`, or
- in-repo but distinct: `Infernux.ai_planner` (sibling of `Infernux.ai_adapters`)

Core MUST NOT know tasks, manage execution plans, or track workflows.

### 4.3 Debug APIs

**Proposed:** `get_logs`, `get_errors`, `trace_last_action`

**Problem:** `Infernux.debug.Debug` already exists. Adding parallel entrypoints in `ai_runtime` creates two competing debug surfaces. `trace_last_action` additionally encodes Adapter semantics ("action") that Core does not own — `get_control_state(channel_id)` already returns the last submitted `ControlSignal` snapshot.

**Resolution:** Reuse `Infernux.debug`; do not expose via Core runtime API.

---

## 5. Category D — Approved New Core APIs (Final List)

The following **8 APIs** are the complete set of approved Core additions. No others.

| # | API | Module | Signature | Phase |
|---|---|---|---|---|
| 1 | `exit_play_mode` | `Infernux.ai_runtime.control_api` | `() -> bool` | 1 |
| 2 | `is_play_mode` | `Infernux.ai_runtime.control_api` | `() -> bool` | 1 |
| 3 | `get_component_fields` | `Infernux.ai_runtime.world_edit` | `(entity_id: int \| str, component_name: str) -> dict[str, Any] \| None` | 1 |
| 4 | `wait_for_event` | `Infernux.ai_runtime.event_stream` | `(event_type: str, timeout_ms: int, *, agent_id: int \| None = None) -> Awaitable[dict \| None]` | 2 |
| 5 | `create_entity` | `Infernux.ai_runtime.world_edit` | `(name: str, parent_id: int \| None = None, *, preview: bool = False) -> EditResult` | 2 |
| 6 | `delete_entity` | `Infernux.ai_runtime.world_edit` | `(entity_id: int \| str, *, preview: bool = False) -> EditResult` | 2 |
| 7 | `add_component` | `Infernux.ai_runtime.world_edit` | `(entity_id: int \| str, component_type: str, *, preview: bool = False) -> EditResult` | 2 |
| 8 | `remove_component` | `Infernux.ai_runtime.world_edit` | `(entity_id: int \| str, component_type: str, *, preview: bool = False) -> EditResult` | 2 |

### 5.1 `exit_play_mode`

- Returns `True` when the play session has been torn down successfully (or was already in Edit Mode), `False` otherwise.
- MUST internally:
  1. Call `PlayModeManager.exit_play_mode()`.
  2. Drain the `DeferredTaskRunner` (symmetric to `enter_play_mode`, bounded by 64 ticks).
  3. Call `clear_control(None)` to flush every input channel.
  4. Call `reset_adjustment(None)` to clear adjustment state for **all** agents (see §5.9).
- Failures in any step result in `False`; never raises into the caller.

### 5.2 `is_play_mode`

- Read-only mirror of `PlayModeManager.is_playing`.
- Returns `False` when the manager is unavailable.
- Never raises.

### 5.3 `get_component_fields`

- Read-side counterpart of `set_component`.
- MUST reuse the same allowlist (`_ALLOWED_COMPONENT_FIELDS` in `world_edit`); requesting a field outside the allowlist returns `None`.
- Returned dict values follow the same coercion rules as `event_stream` payloads (§3.6 of the spec):
  - `vec3`-shaped values → 3-tuple of floats
  - scalars → preserved as `int` / `float` / `bool` / `str`
  - any other type → key omitted (no silent string coercion)
- Returns `None` when the entity or the component cannot be resolved.

### 5.4 `wait_for_event`

- Coroutine form. Built on the existing `Infernux.coroutine` machinery.
- Implementation MUST poll `RuntimeEventCollector.get_recent_events(...)` between yields. **No new native callback channel** is introduced — this preserves the current "native is source of truth, Python adapts" boundary.
- Returns the matching event dict on first match.
- Returns `None` on timeout. **Does not raise.**
- `agent_id=None` matches any agent; an explicit integer narrows to events whose `agent_id` field equals the value.
- Concurrent waits on the same `event_type` are independent (no shared subscription state).

### 5.5 `create_entity`

- Creates an empty GameObject under `parent_id` (root when `parent_id is None`).
- `EditResult.changes` contains a single `FieldChange` with `field_path = "Scene.entity"`, `old_value = None`, `new_value = <new entity_id>`.
- `preview=True` validates the parent exists but does not create the object.
- Failure messages: `"parent not found"`, `"failed to create entity"`.

### 5.6 `delete_entity`

- Detaches and destroys the entity.
- `preview=True` returns the planned `FieldChange` without mutation.
- Failure messages: `"entity not found"`, `"failed to delete entity"`.

### 5.7 `add_component` / `remove_component`

- **`component_type` MUST be one of the allowlisted names** (initially `{"Transform", "Rigidbody"}`, mirroring `_ALLOWED_COMPONENT_FIELDS`). Any other value returns `EditResult(ok=False, message="component type not allowed")`.
- Adding a component that already exists is a no-op success (`changes` empty, `ok=True`).
- Removing `Transform` is rejected (`"transform is required"`).
- Failure messages: `"entity not found"`, `"component type not allowed"`, `"transform is required"`, `"failed to add component"`, `"failed to remove component"`.
- **Open question deliberately deferred to Spec Patch:** whether `add_component` should later accept a Python-side factory `Callable[[], Component]` for non-allowlisted types. v1 ships with the static allowlist only.

### 5.8 Edit Mode vs Play Mode

All four CRUD APIs (`create_entity`, `delete_entity`, `add_component`, `remove_component`) are valid in **both** Edit Mode and Play Mode. In Play Mode they take effect on the live scene; in Edit Mode they mutate the authoring scene. Implementations MUST NOT special-case the mode at the API surface — the underlying scene resolution path is identical.

### 5.9 Multi-agent contract

All APIs in §5 follow these rules consistently with existing Core (`set_event_filter`, `adjustment.*`):

- **Read APIs** that filter by agent accept `agent_id: int | None = None`. `None` means "do not filter".
- **Write APIs** produce events whose `agent_id` field defaults to `0` (single-agent convention, spec §3.6).
- **`exit_play_mode()` clears state for ALL agents** (`reset_adjustment(None)`, `clear_control(None)`). Per-agent teardown is not exposed in v1.

---

## 5.x Removed from Proposal (Explicit)

The following APIs from the original Draft are **rejected** and MUST NOT reappear in future revisions without first overturning the rationale in §2 / §3 / §4:

| API | Rejected Under | Rationale |
|---|---|---|
| `get_scene_graph` | §2 | Duplicate of `list_entities` |
| `get_object_components` | §2 | Duplicate of `EntityRecord.component_types` |
| `set_component_field` | §2 | Duplicate of `set_component` |
| `find_nearest` | §2 | Trivial composition over `find_in_radius` |
| `find_by_tag` | §3 | Reintroduces gameplay semantics |
| `reacquire_entity` | §3 | Reintroduces gameplay semantics |
| `query_entities` | §3 | DSL inside Core |
| `list_assets` | §4.1 | Engine / Editor concern |
| `load_asset` | §4.1 | Engine / Editor concern |
| `instantiate_prefab` | §4.1 | Engine / Editor concern |
| `save_prefab` | §4.1 | Engine / Editor concern |
| `subscribe_event` | §4.3 / §5.4 | Subsumed by `wait_for_event` (poll-based) |
| `poll_events` | §4.3 / §5.4 | Already provided by `get_recent_events` |
| `create_task` | §4.2 | Agent / Planner concern |
| `add_step` | §4.2 | Agent / Planner concern |
| `run_task` | §4.2 | Agent / Planner concern |
| `get_task_status` | §4.2 | Agent / Planner concern |
| `cancel_task` | §4.2 | Agent / Planner concern |
| `get_logs` | §4.3 | Duplicate of `Infernux.debug` |
| `get_errors` | §4.3 | Duplicate of `Infernux.debug` |
| `trace_last_action` | §4.3 | Adapter semantics + duplicate of `get_control_state` |

---

## 6. Required Refactor Before Spec Patch

### Step 1 — Apply §5 verbatim

The 8 APIs in §5 are the entire scope. Do not add, remove, or rename items at implementation time.

### Step 2 — Split the Draft into 3 documents

| Document | Contents |
|---|---|
| **Core Extensions Spec** | The 8 APIs in §5 (this document is the source) |
| **Editor SDK Spec** | Asset / Prefab APIs implemented in `Infernux.engine` |
| **Agent Framework Spec** | Planning / Task APIs in `Infernux.ai_planner` (or out-of-repo) |

Each document must stand alone with its own status, scope, and non-goals sections.

### Step 3 — Normalize error semantics

Adopt the following rule across all new Core APIs (consistent with current `submit_control`, `_build_entity_record`, and `Adapter.translate_action`):

| Failure class | Mechanism |
|---|---|
| **Input contract violation** (wrong type, malformed argument) | `raise TypeError` / `raise ValueError` |
| **Adapter contract violation** (unknown action / role) | `raise AdapterProtocolError` |
| **Runtime state failure** for write operations (entity missing, component unavailable, backend rejected) | Return `EditResult(ok=False, message=…)` |
| **Runtime state failure** for read operations | Return `None` or empty list |
| **Timeout** in `wait_for_event` | Return `None`, do NOT raise |

This is the **complete** error-semantics specification. Implementers MUST NOT introduce new exception types or new sentinel return values.

---

## 7. Final Outcome

After applying this v2:

- Core gains **exactly 8** new APIs (3 in Phase 1, 5 in Phase 2).
- All 8 are semantics-free and implementable on top of existing `PlayModeManager`, `RuntimeEventCollector`, `world_edit` allowlist, and `Infernux.coroutine` infrastructure.
- **21 originally proposed APIs are explicitly rejected** with a documented rationale (§5.x).
- Multi-agent behavior, edit/play-mode behavior, and error semantics are fully specified — no decisions are deferred to implementation.

---

## 8. Conclusion

The direction of the original Draft is correct. The scope, however, must be cut by ~72% (from 29 proposed APIs to 8 approved APIs) to preserve the Core invariant:

> **Core remains a minimal, semantics-free runtime primitive layer.**

This v2 is ready to be promoted to a Spec Patch as `AI_FIRST_ENGINE_v1_SPEC_PATCH_CORE_EXTENSIONS.md`. The two sibling specs (Editor SDK, Agent Framework) are out of scope for this document and tracked separately per §6 Step 2.
