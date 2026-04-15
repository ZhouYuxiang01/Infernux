from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Optional

from .evaluation import EvaluationResult

_MAX_INTENSITY_SCALE = 5.0
_MAX_RETRY_COUNT = 5
_INTENSITY_MULTIPLIER = 1.5


@dataclass
class _AdjustmentState:
    last_action: Optional[dict[str, Any]] = None
    intensity_scale: float = 1.0
    retry_count: int = 0


_STATE = _AdjustmentState()


def record_action(action: dict[str, Any]) -> None:
    """Remember the most recent action for the next adjustment step."""
    _STATE.last_action = deepcopy(action)


def adjust_input(result: EvaluationResult) -> Optional[dict[str, Any]]:
    """Return a scaled follow-up action suggestion when evaluation fails."""
    if result.success:
        return None

    if _STATE.last_action is None:
        return None

    if _STATE.retry_count >= _MAX_RETRY_COUNT:
        return None

    _STATE.retry_count += 1
    _STATE.intensity_scale = min(_MAX_INTENSITY_SCALE, _STATE.intensity_scale * _INTENSITY_MULTIPLIER)

    last_action = _STATE.last_action
    if not isinstance(last_action, dict):
        return None

    action_type = last_action.get("type")
    params = last_action.get("params", {})
    if not isinstance(params, dict):
        params = {}

    adjusted_params: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            adjusted_params[key] = value * _STATE.intensity_scale
        else:
            adjusted_params[key] = deepcopy(value)

    return {
        "type": action_type,
        "params": adjusted_params,
    }
