from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

from . import event_stream as _event_stream
from . import world_state as _world_state
from ._coercion import coerce_vec3_tuple


@dataclass(frozen=True, slots=True)
class EntitySnapshot:
    entity_id: int | str
    name: str
    position: tuple[float, float, float] | None
    velocity: tuple[float, float, float] | None
    component_types: list[str]


@dataclass(frozen=True, slots=True)
class EntityActivitySummary:
    entity_id: int | str
    event_count: int
    collision_count: int
    moved: bool


def _vector_is_nonzero(value: tuple[float, float, float] | None, epsilon: float = 1e-6) -> bool:
    if value is None:
        return False
    return sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]) > epsilon


def _get_scene_object(entity_id: int | str):
    scene = _world_state.get_active_scene()
    if scene is None:
        return None

    finder = getattr(scene, "find_by_id", None)
    if not callable(finder):
        return None

    try:
        return finder(entity_id)
    except Exception:
        return None


def _get_rigidbody_velocity(game_object: Any) -> tuple[float, float, float] | None:
    getter = getattr(game_object, "get_component", None)
    if not callable(getter):
        return None

    try:
        rigidbody = getter("Rigidbody")
    except Exception:
        return None

    if rigidbody is None:
        return None

    try:
        return coerce_vec3_tuple(getattr(rigidbody, "velocity", None))
    except Exception:
        return None


def _get_transform_position(game_object: Any) -> tuple[float, float, float] | None:
    transform = getattr(game_object, "transform", None)
    if transform is None:
        return None

    try:
        return coerce_vec3_tuple(getattr(transform, "position", None))
    except Exception:
        return None


def get_entity_snapshot(entity_id: int | str) -> EntitySnapshot | None:
    scene_object = _get_scene_object(entity_id)
    if scene_object is None:
        return None

    record = _world_state.get_entity(entity_id)
    if record is None:
        return None

    return EntitySnapshot(
        entity_id=record.id,
        name=record.name,
        position=_get_transform_position(scene_object),
        velocity=_get_rigidbody_velocity(scene_object),
        component_types=list(record.component_types),
    )


def get_entity_snapshot_by_name(name: str) -> EntitySnapshot | None:
    target = str(name)
    for record in _world_state.list_entities():
        if record.name == target:
            return get_entity_snapshot(record.id)
    return None


def _is_related_event(event: Any, entity_id: int | str) -> bool:
    if isinstance(event, dict):
        source_id = event.get("source_entity_id")
        target_id = event.get("target_entity_id")
    else:
        source_id = getattr(event, "source_entity_id", None)
        target_id = getattr(event, "target_entity_id", None)
    return source_id == entity_id or target_id == entity_id


def _event_type_name(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("type", "") or "")
    return str(getattr(event, "type", "") or "")


def get_entity_activity_summary(entity_id: int, ms: int | float) -> EntityActivitySummary:
    try:
        window_ms = float(ms)
    except Exception:
        window_ms = 0.0

    events = _event_stream.get_recent_events(window_ms)
    related_events = [event for event in events if _is_related_event(event, entity_id)]
    collision_events = [
        event
        for event in related_events
        if ("Collision" in _event_type_name(event)) or ("Trigger" in _event_type_name(event))
    ]
    snapshot = get_entity_snapshot(entity_id)
    moved = _vector_is_nonzero(snapshot.velocity if snapshot is not None else None)

    return EntityActivitySummary(
        entity_id=entity_id,
        event_count=len(related_events),
        collision_count=len(collision_events),
        moved=moved,
    )


__all__ = [
    "EntityActivitySummary",
    "EntitySnapshot",
    "get_entity_activity_summary",
    "get_entity_snapshot",
    "get_entity_snapshot_by_name",
]
