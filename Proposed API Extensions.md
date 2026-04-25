
---

# Infernux Proposed API Extensions (Draft)

## Status

This document defines **proposed API extensions** for Infernux.

* Status: Draft / For Review
* Scope: Editor integration, Planning layer, and Engine-resident capabilities
* These APIs are NOT yet implemented
* This document is for design validation only

---

## 1. Design Goals

The proposed APIs aim to extend Infernux from:

Runtime Operator

to:

Engine-Resident AI System

Specifically enabling:

* Editor state observation
* Scene construction and modification
* Play Mode ↔ Editor loop
* Task planning and execution
* Persistent agent workflows

---

## 2. Separation Principle

All proposed APIs must respect:

* Core remains **semantics-free**
* Adapter handles **domain meaning**
* Agent handles **decision-making**

These APIs extend capabilities, not responsibilities.

---

## 3. API Categories

Proposed APIs are grouped into:

1. Editor Observation
2. Editor World Editing
3. Asset System
4. Play Mode Bridge
5. Event System
6. Advanced Query
7. Debug & Feedback
8. Planning Layer (Task System)

---

## 4. Editor Observation APIs

### get_scene_graph()

Signature:
def get_scene_graph() -> dict

Summary:
Returns the full scene hierarchy.

Returns:

* Tree structure of GameObjects
* Parent-child relationships
* Entity identifiers

---

### get_object_components(entity_id)

Signature:
def get_object_components(entity_id: int) -> list[str]

Summary:
Returns all components attached to an entity.

---

### get_component_fields(entity_id, component_name)

Signature:
def get_component_fields(entity_id: int, component_name: str) -> dict

Summary:
Returns serialized field values of a component.

---

## 5. Editor World Edit APIs

### create_entity()

Signature:
def create_entity(name: str, parent_id: int | None = None) -> int

---

### delete_entity()

Signature:
def delete_entity(entity_id: int) -> None

---

### add_component()

Signature:
def add_component(entity_id: int, component_type: str) -> None

---

### remove_component()

Signature:
def remove_component(entity_id: int, component_type: str) -> None

---

### set_component_field()

Signature:
def set_component_field(entity_id: int, component: str, field: str, value: object) -> None

---

## 6. Asset System APIs

### list_assets()

Signature:
def list_assets(path: str | None = None) -> list[str]

---

### load_asset()

Signature:
def load_asset(path: str) -> object

---

### instantiate_prefab()

Signature:
def instantiate_prefab(path: str, position: tuple) -> int

---

### save_prefab()

Signature:
def save_prefab(entity_id: int, path: str) -> None

---

## 7. Play Mode Bridge APIs

### enter_play_mode()

Signature:
def enter_play_mode() -> None

---

### exit_play_mode()

Signature:
def exit_play_mode() -> None

---

### is_play_mode()

Signature:
def is_play_mode() -> bool

---

### reacquire_entity()

Signature:
def reacquire_entity(name: str) -> int

Notes:
Required after entering play mode.

---

## 8. Event System APIs

### subscribe_event()

Signature:
def subscribe_event(event_type: str) -> None

---

### wait_for_event()

Signature:
def wait_for_event(event_type: str, timeout_ms: int) -> dict

---

### poll_events()

Signature:
def poll_events() -> list[dict]

---

## 9. Advanced Query APIs

### find_by_tag()

Signature:
def find_by_tag(tag: str) -> list[int]

---

### find_nearest()

Signature:
def find_nearest(entity_id: int, tag: str) -> int | None

---

### query_entities()

Signature:
def query_entities(filter_expr: dict) -> list[int]

Example filter:

{"component": "Rigidbody", "velocity_gt": 5.0}

---

## 10. Debug & Feedback APIs

### get_logs()

Signature:
def get_logs(level: str | None = None) -> list[str]

---

### get_errors()

Signature:
def get_errors() -> list[str]

---

### trace_last_action()

Signature:
def trace_last_action() -> dict

---

## 11. Planning Layer APIs

### create_task()

Signature:
def create_task(name: str, description: str) -> str

---

### add_step()

Signature:
def add_step(task_id: str, step: dict) -> None

---

### run_task()

Signature:
def run_task(task_id: str) -> dict

---

### get_task_status()

Signature:
def get_task_status(task_id: str) -> dict

---

### cancel_task()

Signature:
def cancel_task(task_id: str) -> None

---

## 12. Non-Goals

These APIs MUST NOT:

* Encode gameplay semantics
* Contain AI decision logic
* Replace Adapter layer
* Replace Agent logic

---

## 13. Risk Areas

High Risk:

* Mixing World Edit and Control
* Direct state mutation bypassing runtime
* Cross-mode entity identity mismatch

Medium Risk:

* Event ordering consistency
* Query performance

Low Risk:

* Debug/log APIs

---

## 14. Implementation Priority

Phase 1 (High Value):

* Editor Observation
* Basic World Edit
* Play Mode Bridge

Phase 2:

* Asset APIs
* Query APIs

Phase 3:

* Event system
* Planning layer

---

## 15. Summary

These APIs extend Infernux toward:

AI that can build, test, and iterate inside the engine

They are not required for current runtime demos,
but are necessary for the "AI Resident in Engine" vision.

---

