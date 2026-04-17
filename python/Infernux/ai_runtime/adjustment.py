"""Adjustment state (spec §3.8).

Adjustment is intentionally **not** world editing: it only shapes the next
input attempt when an evaluation failure is observed. The module keeps
bounded retry / intensity state per ``agent_id`` so that multiple agents (or
multiple sessions of the same agent) do not cross-pollute each other's
back-off behaviour.

Session boundary (spec §3.8):

- A session is one ``enter_play_mode()`` → ``exit_play_mode()`` span.
- Adjustment state must be resettable at session boundaries.
- For v1 we honour this by exposing ``reset_adjustment(agent_id=None)``;
  callers (``control_api.exit_play_mode`` once it lands, or the test harness
  today) invoke it on shutdown.

The v1.1 API (``record_action(action)``/``adjust_input(result)`` with no
``agent_id``) is preserved by routing to a default agent bucket
(``_DEFAULT_AGENT_ID``). This matches spec §3.6 where "single agent ⇒
agent_id = 0".
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional

from .evaluation import EvaluationResult

_MAX_INTENSITY_SCALE = 5.0
_MAX_RETRY_COUNT = 5
_INTENSITY_MULTIPLIER = 1.5

# Bucket used when the caller does not name an agent. Matches spec §3.6.
_DEFAULT_AGENT_ID = 0


@dataclass
class _AdjustmentState:
    last_action: Optional[dict[str, Any]] = None
    intensity_scale: float = 1.0
    retry_count: int = 0


# Per-agent state. Keyed by ``agent_id`` so agents do not interfere with each
# other's back-off state (spec §3.8: "Adjustment 状态必须按 agent_id 隔离").
_STATES: dict[int, _AdjustmentState] = {}


def _coerce_agent_id(agent_id: Any) -> int:
    if agent_id is None:
        return _DEFAULT_AGENT_ID
    try:
        return int(agent_id)
    except (TypeError, ValueError):
        return _DEFAULT_AGENT_ID


def _get_state(agent_id: int) -> _AdjustmentState:
    state = _STATES.get(agent_id)
    if state is None:
        state = _AdjustmentState()
        _STATES[agent_id] = state
    return state


def record_action(action: dict[str, Any], *, agent_id: Optional[int] = None) -> None:
    """Remember the most recent action for the next adjustment step.

    ``agent_id`` keeps separate bookkeeping per agent. Omitting it targets the
    default agent bucket (``0``) — preserving the pre-refactor single-agent
    behaviour.
    """
    state = _get_state(_coerce_agent_id(agent_id))
    state.last_action = deepcopy(action)


def adjust_input(
    result: EvaluationResult, *, agent_id: Optional[int] = None
) -> Optional[dict[str, Any]]:
    """Return a scaled follow-up action suggestion when evaluation fails."""
    if result.success:
        return None

    state = _get_state(_coerce_agent_id(agent_id))
    if state.last_action is None:
        return None

    if state.retry_count >= _MAX_RETRY_COUNT:
        return None

    state.retry_count += 1
    state.intensity_scale = min(
        _MAX_INTENSITY_SCALE, state.intensity_scale * _INTENSITY_MULTIPLIER
    )

    last_action = state.last_action
    if not isinstance(last_action, dict):
        return None

    action_type = last_action.get("type")
    params = last_action.get("params", {})
    if not isinstance(params, dict):
        params = {}

    adjusted_params: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            adjusted_params[key] = value * state.intensity_scale
        else:
            adjusted_params[key] = deepcopy(value)

    return {
        "type": action_type,
        "params": adjusted_params,
    }


def reset_adjustment(agent_id: Optional[int] = None) -> None:
    """Reset adjustment bookkeeping (spec §3.8).

    ``agent_id=None`` clears state for every agent; otherwise only the named
    bucket is reset. Call this on ``exit_play_mode()`` or between test
    scenarios to avoid cross-session retry/intensity leakage.
    """
    if agent_id is None:
        _STATES.clear()
        return

    _STATES.pop(_coerce_agent_id(agent_id), None)


__all__ = [
    "adjust_input",
    "record_action",
    "reset_adjustment",
]
