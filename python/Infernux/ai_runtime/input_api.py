from __future__ import annotations

import warnings
from typing import Any


class ActionType:
    Jump = "jump"
    Attack = "attack"
    Move = "move"


def _get_input_manager():
    from Infernux.lib import InputManager

    return InputManager.instance()


def _warn_deprecated(api_name: str) -> None:
    warnings.warn(
        f"{api_name} is deprecated; use Adapter + submit_control or "
        "entity-centric observation instead. Removal target: v2.0.",
        DeprecationWarning,
        stacklevel=2,
    )


def _submit_control_impl(action: str, **kwargs) -> bool:
    manager = _get_input_manager()
    if manager is None:
        return False

    action_name = str(action).strip().lower()
    try:
        if action_name == ActionType.Jump:
            manager.set_virtual_action(ActionType.Jump, True, 0.0, 0.0)
        elif action_name == ActionType.Attack:
            manager.set_virtual_action(ActionType.Attack, True, 0.0, 0.0)
        elif action_name == ActionType.Move:
            x = float(kwargs.get("x", 0.0))
            y = float(kwargs.get("y", 0.0))
            manager.set_virtual_action(ActionType.Move, True, x, y)
        else:
            return False
    except Exception:
        return False
    return True


def send_action(action: str, **kwargs) -> bool:
    _warn_deprecated("send_action(...)")
    return _submit_control_impl(action, **kwargs)


def clear_actions() -> None:
    manager = _get_input_manager()
    if manager is None:
        return
    try:
        manager.clear_virtual_actions()
    except Exception:
        return


__all__ = [
    "ActionType",
    "clear_actions",
    "send_action",
]
