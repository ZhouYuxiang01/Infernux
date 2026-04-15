from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import event_stream as _event_stream
from .world_state import get_active_scene as _get_active_scene


@dataclass(frozen=True)
class PlayerSnapshot:
    entity_id: int | str
    position: Any | None
    velocity: Any | None
    grounded: Any | None


@dataclass(frozen=True)
class ActivitySummary:
    event_count: int
    jumped: bool
    attacked: bool


def _get_component(game_object: Any, component_type: str) -> Any:
    getter = getattr(game_object, "get_component", None)
    if not callable(getter):
        return None
    try:
        return getter(component_type)
    except Exception:
        return None


def _iter_scene_objects(scene: Any) -> list[Any]:
    getter = getattr(scene, "get_all_objects", None)
    if not callable(getter):
        return []
    try:
        return list(getter() or [])
    except Exception:
        return []


def _first_non_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _find_player_by_tag(scene: Any) -> Any:
    for method_name in ("find_with_tag", "find_game_objects_with_tag"):
        getter = getattr(scene, method_name, None)
        if not callable(getter):
            continue
        try:
            result = getter("Player")
        except Exception:
            continue
        result = _first_non_none(result)
        if result is not None:
            return result
    return None


def _find_player_by_component(scene: Any, component_type: str) -> Any:
    for game_object in _iter_scene_objects(scene):
        if _get_component(game_object, component_type) is not None:
            return game_object
    return None


def _read_transform_position(game_object: Any) -> Any | None:
    transform = getattr(game_object, "transform", None)
    if transform is None:
        return None
    try:
        return getattr(transform, "position", None)
    except Exception:
        return None


def _read_rigidbody_velocity(game_object: Any) -> Any | None:
    rigidbody = _get_component(game_object, "Rigidbody")
    if rigidbody is None:
        return None
    try:
        return getattr(rigidbody, "velocity", None)
    except Exception:
        return None


def _read_grounded(game_object: Any) -> Any | None:
    controller = _get_component(game_object, "CharacterController")
    if controller is None:
        return None

    for attr_name in ("grounded", "is_grounded"):
        try:
            value = getattr(controller, attr_name)
        except Exception:
            continue
        if callable(value):
            try:
                return value()
            except Exception:
                continue
        return value
    return None


def get_player_snapshot() -> PlayerSnapshot | None:
    scene = _get_active_scene()
    if scene is None:
        return None

    player = _find_player_by_tag(scene)
    if player is None:
        player = _find_player_by_component(scene, "CharacterController")
    if player is None:
        player = _find_player_by_component(scene, "Rigidbody")
    if player is None:
        return None

    try:
        entity_id = getattr(player, "id", None)
    except Exception:
        entity_id = None
    if entity_id is None:
        return None

    position = _read_transform_position(player)
    velocity = _read_rigidbody_velocity(player)
    grounded = _read_grounded(player)

    return PlayerSnapshot(
        entity_id=entity_id,
        position=position,
        velocity=velocity,
        grounded=grounded,
    )


def get_recent_events(ms: int | float) -> list[dict[str, Any]]:
    return _event_stream.get_recent_events(ms)


def _normalize_action_name(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip().lower()
    except Exception:
        return ""


def _event_type_name(event: Any) -> str:
    if isinstance(event, dict):
        return _normalize_action_name(event.get("type"))
    return _normalize_action_name(getattr(event, "type", None))


def _event_payload(event: Any) -> dict[str, Any]:
    payload = None
    if isinstance(event, dict):
        payload = event.get("payload")
    else:
        payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        return payload
    try:
        return dict(payload or {})
    except Exception:
        return {}


def _event_has_action(event: Any, action_name: str) -> bool:
    type_name = _event_type_name(event)
    if type_name in {f"{action_name}triggered", f"{action_name}trigger"}:
        return True

    if type_name != "inputinjected":
        return False

    payload = _event_payload(event)
    return _normalize_action_name(payload.get("action")) == action_name


def get_activity_summary(ms: int | float) -> ActivitySummary:
    recent_events = get_recent_events(ms)
    jumped = any(_event_has_action(event, "jump") for event in recent_events)
    attacked = any(_event_has_action(event, "attack") for event in recent_events)
    return ActivitySummary(event_count=len(recent_events), jumped=jumped, attacked=attacked)


__all__ = [
    "ActivitySummary",
    "PlayerSnapshot",
    "get_activity_summary",
    "get_recent_events",
    "get_player_snapshot",
]
