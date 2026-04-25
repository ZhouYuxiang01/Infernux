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

_VALID_MODES = {"auto", "edit", "runtime"}


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


def _normalize_mode(mode: str | None) -> str:
    value = str(mode or "auto").strip().lower()
    return value if value in _VALID_MODES else "auto"


def _is_play_mode() -> bool:
    try:
        from Infernux.engine.play_mode import PlayModeManager, PlayModeState
        manager = PlayModeManager.instance()
        return bool(manager and manager.state != PlayModeState.EDIT)
    except Exception:
        return False


def _validate_mode(mode: str) -> str | None:
    if mode == "edit" and _is_play_mode():
        return "edit mode mutation requested while play mode is active"
    if mode == "runtime" and not _is_play_mode():
        return "runtime mutation requested outside play mode"
    return None


def _should_use_undo(mode: str) -> bool:
    if mode == "runtime":
        return False
    if mode == "edit":
        return True
    return not _is_play_mode()


def _mark_scene_dirty() -> None:
    try:
        from Infernux.engine.scene_manager import SceneFileManager
        manager = SceneFileManager.instance()
        if manager is not None:
            manager.mark_dirty()
    except Exception:
        pass


def _sync_physics_after_transform_edit() -> None:
    try:
        from Infernux.lib import SceneManager
        manager = SceneManager.instance()
        sync = getattr(manager, "sync_transforms", None)
        if callable(sync):
            sync()
    except Exception:
        pass


def _apply_with_undo(component: Any, key: str, old_value: Any, new_value: Any, label: str) -> bool:
    try:
        from Infernux.engine.undo import UndoManager, SetPropertyCommand
        manager = UndoManager.instance()
        if manager is None:
            return False
        if getattr(manager, "is_executing", False):
            return False
        if not getattr(manager, "enabled", True):
            return False

        manager.execute(SetPropertyCommand(component, key, old_value, new_value, label))
        return True
    except Exception:
        return False


def _apply_field(component: Any, key: str, value: Any, mode: str, label: str) -> bool:
    old_value = getattr(component, key, None)

    if _should_use_undo(mode):
        if _apply_with_undo(component, key, old_value, value, label):
            if key == "position":
                _sync_physics_after_transform_edit()
            return True

    setattr(component, key, value)

    if _should_use_undo(mode):
        _mark_scene_dirty()

    if key == "position":
        _sync_physics_after_transform_edit()

    return True


def move_entity(
    entity_id: int,
    position: tuple[float, float, float],
    preview: bool = False,
    mode: str = "auto",
) -> EditResult:
    mode = _normalize_mode(mode)
    mode_error = _validate_mode(mode)
    if mode_error:
        return EditResult(ok=False, preview=bool(preview), changes=[], message=mode_error)

    scene_object = _get_scene_object(entity_id)
    if scene_object is None:
        return EditResult(ok=False, preview=bool(preview), changes=[], message="entity not found")

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
        _apply_field(transform, "position", vec, mode, "Move Entity")
    except Exception:
        return EditResult(ok=False, preview=False, changes=[], message="failed to set position")

    return EditResult(ok=True, preview=False, changes=[change])


def set_component(
    entity_id: int,
    key: str,
    value: Any,
    preview: bool = False,
    mode: str = "auto",
) -> EditResult:
    mode = _normalize_mode(mode)
    mode_error = _validate_mode(mode)
    if mode_error:
        return EditResult(ok=False, preview=bool(preview), changes=[], message=mode_error)

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
        _apply_field(component, key, coerced_value, mode, f"Set {component_name}.{key}")
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
