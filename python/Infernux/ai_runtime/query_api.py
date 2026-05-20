from __future__ import annotations

from typing import Any

from .types import EntityRecord
from . import event_stream as _event_stream
from . import world_state as _world_state


def list_entities() -> list[EntityRecord]:
    return _world_state.list_entities()


def get_entity(entity_id: int | str) -> EntityRecord | None:
    return _world_state.get_entity(entity_id)


def find_by_component(component_type: Any) -> list[EntityRecord]:
    target_type = _world_state.normalize_type_name(component_type)
    if not target_type:
        return []

    matches: list[EntityRecord] = []
    for entity in list_entities():
        if any(_world_state.normalize_type_name(name) == target_type for name in entity.component_types):
            matches.append(entity)
    return matches


def _extract_game_object(candidate: Any) -> Any:
    if candidate is None:
        return None

    direct_game_object = getattr(candidate, "game_object", None)
    if direct_game_object is not None:
        return direct_game_object

    getter = getattr(candidate, "get_game_object", None)
    if callable(getter):
        try:
            resolved = getter()
            if resolved is not None:
                return resolved
        except Exception:
            pass

    collider = getattr(candidate, "collider", None)
    if collider is not None:
        nested_game_object = getattr(collider, "game_object", None)
        if nested_game_object is not None:
            return nested_game_object
        nested_getter = getattr(collider, "get_game_object", None)
        if callable(nested_getter):
            try:
                resolved = nested_getter()
                if resolved is not None:
                    return resolved
            except Exception:
                pass

    return None


def _extract_entity_id(candidate: Any) -> int | str | None:
    game_object = _extract_game_object(candidate)
    if game_object is None:
        return None
    return getattr(game_object, "id", None)


def find_in_radius(position, radius: float) -> list[EntityRecord]:
    try:
        from Infernux.physics import Physics
    except Exception:
        return []

    try:
        colliders = Physics.overlap_sphere(position, radius)
    except Exception:
        return []

    found: list[EntityRecord] = []
    seen_ids: set[int | str] = set()

    for result in colliders or []:
        entity_id = _extract_entity_id(result)
        if entity_id is None:
            continue

        if entity_id in seen_ids:
            continue

        entity = get_entity(entity_id)
        if entity is None:
            continue

        seen_ids.add(entity_id)
        found.append(entity)

    return found


def get_recent_events(ms: int | float) -> list[Any]:
    return _event_stream.get_recent_events(ms)


__all__ = [
    "find_by_component",
    "find_in_radius",
    "get_entity",
    "get_recent_events",
    "list_entities",
]
