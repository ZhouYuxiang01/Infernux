from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from Infernux.lib import Vector3

from . import world_state

_ALLOWED_COMPONENT_FIELDS = {
    "Transform": {"position"},
    "Rigidbody": {"velocity", "mass"},
}


@dataclass(frozen=True, slots=True)
class FieldChange:
    field_path: str
    old_value: Any
    new_value: Any


@dataclass(frozen=True, slots=True)
class EditResult:
    ok: bool
    preview: bool
    changes: list[FieldChange]
    message: str | None = None

    def __bool__(self) -> bool:
        return self.ok


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


def move_entity(entity_id: int, position: tuple[float, float, float], preview: bool = False) -> EditResult:
    scene_object = _get_scene_object(entity_id)
    if scene_object is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="entity not found")

    transform = None
    try:
        transform = scene_object.get_component("Transform")
    except Exception:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="transform unavailable")

    if transform is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="transform unavailable")

    vec = _coerce_vec3(position)
    if vec is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="invalid position")

    old_value = getattr(transform, "position", None)
    change = FieldChange(field_path="Transform.position", old_value=old_value, new_value=vec)
    if preview:
        return EditResult(ok=True, preview=True, changes=[change])

    try:
        transform.position = vec
    except Exception:
        return EditResult(ok=False, preview=False, changes=[], message="failed to set position")
    return EditResult(ok=True, preview=False, changes=[change])


def set_component(entity_id: int, key: str, value: Any, preview: bool = False) -> EditResult:
    component_name = _get_allowed_component_name(key)
    if component_name is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="field not allowed")

    scene_object = _get_scene_object(entity_id)
    if scene_object is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="entity not found")

    try:
        component = scene_object.get_component(component_name)
    except Exception:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="component unavailable")

    if component is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="component unavailable")

    allowed_fields = _ALLOWED_COMPONENT_FIELDS.get(component_name, set())
    if key not in allowed_fields:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="field not allowed")

    coerced_value = value
    if key in {"position", "velocity"}:
        coerced_value = _coerce_vec3(value)
        if coerced_value is None:
            return EditResult(ok=False, preview=bool(preview), changes=[], message="invalid vec3")
    elif key == "mass":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return EditResult(ok=False, preview=bool(preview), changes=[], message="invalid numeric value")
        coerced_value = float(value)

    old_value = getattr(component, key, None)
    change = FieldChange(field_path=f"{component_name}.{key}", old_value=old_value, new_value=coerced_value)
    if preview:
        return EditResult(ok=True, preview=True, changes=[change])

    try:
        setattr(component, key, coerced_value)
    except Exception:
        return EditResult(ok=False, preview=False, changes=[], message="failed to set field")
    return EditResult(ok=True, preview=False, changes=[change])


__all__ = [
    "_ALLOWED_COMPONENT_FIELDS",
    "EditResult",
    "FieldChange",
    "move_entity",
    "set_component",
]
