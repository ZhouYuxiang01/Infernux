"""Concrete platformer adapter.

Implements the minimum ``Adapter`` protocol and a handful of platformer-only
helpers. All game-specific tokens ("player", "jump", "attack", ...) are
confined to this module and its siblings; Core remains vocabulary-free.
"""

from __future__ import annotations

from typing import Any

from Infernux.ai_runtime.control_signal import ControlSignal

from ..protocol import AdapterProtocolError

__all__ = [
    "PlatformerAdapter",
]


class PlatformerAdapter:
    """Translates platformer-style semantics to the generic Core API.

    The adapter does not hold runtime state; it is a stateless translator. It
    is intentionally written without any dependency on ``observation_api`` or
    other legacy player-centric Core modules — those will be removed in
    Phase 3 (v1.4 后半). Entity resolution here uses only the generic Query
    surface.
    """

    # --- Adapter protocol -----------------------------------------------------

    def resolve_semantic_entity(self, scene: Any, role: str) -> int | None:
        normalized = role.strip().lower() if isinstance(role, str) else ""
        if normalized == "player":
            return self._resolve_player(scene)
        if normalized == "enemy":
            return self._resolve_first_with_component(scene, "EnemyTag")
        return None

    def translate_action(self, name: str, **kwargs: Any) -> ControlSignal:
        normalized = name.strip().lower() if isinstance(name, str) else ""
        channel_id = int(kwargs.get("channel_id", 0))
        duration_ms = kwargs.get("duration_ms")

        if normalized == "jump":
            return ControlSignal(
                channel_id=channel_id,
                buttons={"jump": True},
                duration_ms=duration_ms,
            )
        if normalized == "attack":
            return ControlSignal(
                channel_id=channel_id,
                buttons={"attack": True},
                duration_ms=duration_ms,
            )
        if normalized == "move":
            x = float(kwargs.get("x", 0.0))
            y = float(kwargs.get("y", 0.0))
            return ControlSignal(
                channel_id=channel_id,
                axes={"move_x": x, "move_y": y},
                duration_ms=duration_ms,
            )
        if normalized == "release":
            # Explicit "release all" gesture — emits a signal that zeroes every
            # platformer button / axis the adapter knows about.
            return ControlSignal(
                channel_id=channel_id,
                buttons={"jump": False, "attack": False},
                axes={"move_x": 0.0, "move_y": 0.0},
                duration_ms=duration_ms,
            )

        raise AdapterProtocolError(f"Unknown platformer action: {name!r}")

    # --- platformer-specific helpers (non-protocol) ---------------------------

    def _resolve_player(self, scene: Any) -> int | None:
        # Tag lookup first (if the scene supports it).
        for method_name in ("find_with_tag", "find_game_objects_with_tag"):
            getter = getattr(scene, method_name, None)
            if not callable(getter):
                continue
            try:
                result = getter("Player")
            except Exception:
                continue
            entity = self._first(result)
            entity_id = self._read_entity_id(entity)
            if entity_id is not None:
                return entity_id

        # Otherwise fall back to the first entity that carries a
        # CharacterController — platformer convention.
        return self._resolve_first_with_component(scene, "CharacterController")

    def _resolve_first_with_component(self, scene: Any, component_type: str) -> int | None:
        getter = getattr(scene, "get_all_objects", None)
        if not callable(getter):
            return None
        try:
            objects = list(getter() or [])
        except Exception:
            return None
        for obj in objects:
            has = getattr(obj, "get_component", None)
            if not callable(has):
                continue
            try:
                component = has(component_type)
            except Exception:
                continue
            if component is not None:
                return self._read_entity_id(obj)
        return None

    @staticmethod
    def _first(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return value[0] if value else None
        return value

    @staticmethod
    def _read_entity_id(entity: Any) -> int | None:
        if entity is None:
            return None
        try:
            raw = getattr(entity, "id", None)
            if raw is None:
                return None
            return int(raw)
        except Exception:
            return None
