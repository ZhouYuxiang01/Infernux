"""Transitional bridge: ControlSignal → legacy ``VirtualInputState``.

This module exists because the current C++ runtime only exposes the
platformer-shaped ``VirtualInputState`` struct (``jump`` / ``attack`` /
``move_x`` / ``move_y``). Spec §4 / REFACTOR §3 schedules that struct's
replacement with a generic ``std::vector<InputChannel>``. Until that native
refactor lands, this bridge is the only place that carries the legacy action
vocabulary across the Python ↔ C++ boundary.

When the C++ ``InputChannel`` binding ships:

1. Replace the bodies of ``apply_signal`` / ``clear`` with direct channel
   submission to the native ``InputManager``.
2. Delete this module's grandfather entry from
   ``Infernux.ai_runtime._semantic_boundary.GRANDFATHERED_MODULES``.
3. The public contract of ``submit_control`` / ``clear_control`` does not
   change; only this file is swapped.

The legacy vocabulary is deliberately quarantined here so that
``control_signal.py`` itself remains semantics-free and the semantic
boundary guard stays tight on Core's public surface.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "apply_signal",
    "clear",
]


def _get_input_manager() -> Any:
    try:
        from Infernux.lib import InputManager  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        return InputManager.instance()
    except Exception:
        return None


# Conventional button / axis names that the current C++ backend understands.
# These are an implementation detail of this bridge, not part of the Core
# contract — do not read them from Core code.
_LEGACY_BUTTON_JUMP = "jump"  # noqa: semantic-boundary
_LEGACY_BUTTON_ATTACK = "attack"  # noqa: semantic-boundary
_LEGACY_AXIS_X = "move_x"
_LEGACY_AXIS_Y = "move_y"
_LEGACY_ACTION_MOVE = "move"


def apply_signal(signal: Any) -> None:
    """Lower a normalized ``ControlSignal`` onto the legacy backend.

    Unknown buttons and axes are silently ignored — they will become
    addressable once the C++ ``InputChannel`` path is live.
    """
    manager = _get_input_manager()
    if manager is None:
        return

    jump_value = signal.buttons.get(_LEGACY_BUTTON_JUMP)
    if jump_value is not None:
        try:
            manager.set_virtual_action(_LEGACY_BUTTON_JUMP, bool(jump_value), 0.0, 0.0)
        except Exception:
            pass

    attack_value = signal.buttons.get(_LEGACY_BUTTON_ATTACK)
    if attack_value is not None:
        try:
            manager.set_virtual_action(_LEGACY_BUTTON_ATTACK, bool(attack_value), 0.0, 0.0)
        except Exception:
            pass

    move_x = signal.axes.get(_LEGACY_AXIS_X)
    move_y = signal.axes.get(_LEGACY_AXIS_Y)
    if move_x is not None or move_y is not None:
        x = float(move_x) if move_x is not None else 0.0
        y = float(move_y) if move_y is not None else 0.0
        active = bool(x != 0.0 or y != 0.0)
        try:
            manager.set_virtual_action(_LEGACY_ACTION_MOVE, active, x, y)
        except Exception:
            pass


def clear() -> None:
    manager = _get_input_manager()
    if manager is None:
        return
    try:
        manager.clear_virtual_actions()
    except Exception:
        return
