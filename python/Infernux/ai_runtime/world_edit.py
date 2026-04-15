from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from Infernux.lib import Vector3

from . import world_state

_ALLOWED_COMPONENT_FIELDS = {
    "Transform": {"position"},
    "Rigidbody": {"velocity", "mass"},
}


def _get_active_scene():
    return world_state.get_active_scene()


def _get_scene_object(entity_id: Any):
    scene = _get_active_scene()
    if scene is None:
        return None

    finder = getattr(scene, "find_by_id", None)
    if not callable(finder):
        return None

    try:
        return finder(entity_id)
    except Exception:
        return None


def _coerce_vec3(value: Any):
    if value is None:
        return None

    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        try:
            return Vector3(float(value.x), float(value.y), float(value.z))
        except Exception:
            return None

    if isinstance(value, (str, bytes)):
        return None

    try:
        values = list(value) if isinstance(value, Iterable) else None
    except Exception:
        return None

    if values is None or len(values) != 3:
        return None

    try:
        x, y, z = (float(values[0]), float(values[1]), float(values[2]))
    except Exception:
        return None
    return Vector3(x, y, z)


def _get_allowed_component_name(key: str) -> str | None:
    if key == "position":
        return "Transform"
    if key in {"velocity", "mass"}:
        return "Rigidbody"
    return None


def move_entity(entity_id: int, position: tuple[float, float, float]) -> bool:
    scene_object = _get_scene_object(entity_id)
    if scene_object is None:
        return False

    transform = None
    try:
        transform = scene_object.get_component("Transform")
    except Exception:
        return False

    if transform is None:
        return False

    vec = _coerce_vec3(position)
    if vec is None:
        return False

    try:
        transform.position = vec
    except Exception:
        return False
    return True


def set_component(entity_id: int, key: str, value: Any) -> bool:
    component_name = _get_allowed_component_name(key)
    if component_name is None:
        return False

    scene_object = _get_scene_object(entity_id)
    if scene_object is None:
        return False

    try:
        component = scene_object.get_component(component_name)
    except Exception:
        return False

    if component is None:
        return False

    allowed_fields = _ALLOWED_COMPONENT_FIELDS.get(component_name, set())
    if key not in allowed_fields:
        return False

    coerced_value = value
    if key in {"position", "velocity"}:
        coerced_value = _coerce_vec3(value)
        if coerced_value is None:
            return False
    elif key == "mass":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        coerced_value = float(value)

    try:
        setattr(component, key, coerced_value)
    except Exception:
        return False
    return True


__all__ = [
    "_ALLOWED_COMPONENT_FIELDS",
    "move_entity",
    "set_component",
]
