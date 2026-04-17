from __future__ import annotations

import Infernux.ai_runtime.adjustment as adjustment
from Infernux.ai_runtime import (
    EvaluationResult,
    adjust_input,
    record_action,
    reset_adjustment,
)


def _reset_state():
    # Public entry point; drops every agent's bookkeeping.
    reset_adjustment()


def test_adjust_input_returns_none_on_success():
    _reset_state()
    record_action({"type": "move", "params": {"x": 1.0}})

    assert adjust_input(EvaluationResult(True, 1.0, [], {})) is None


def test_adjust_input_scales_numeric_params():
    _reset_state()
    record_action({"type": "move", "params": {"x": 1.0, "label": "keep"}})

    result = adjust_input(EvaluationResult(False, 0.0, ["x"], {}))

    assert result == {"type": "move", "params": {"x": 1.5, "label": "keep"}}


def test_adjust_input_scales_across_multiple_failures():
    _reset_state()
    record_action({"type": "move", "params": {"x": 1.0}})

    first = adjust_input(EvaluationResult(False, 0.0, ["x"], {}))
    assert first == {"type": "move", "params": {"x": 1.5}}

    record_action(first)
    second = adjust_input(EvaluationResult(False, 0.0, ["x"], {}))
    assert second == {"type": "move", "params": {"x": 3.375}}


def test_adjust_input_caps_intensity_scale():
    _reset_state()
    record_action({"type": "move", "params": {"x": 1.0}})

    result = None
    for _ in range(5):
        result = adjust_input(EvaluationResult(False, 0.0, ["x"], {}))
        if result is not None:
            record_action(result)

    assert result is not None
    default_state = adjustment._STATES[adjustment._DEFAULT_AGENT_ID]
    assert default_state.intensity_scale <= 5.0
    assert default_state.intensity_scale == 5.0


def test_adjust_input_stops_after_retry_limit():
    _reset_state()
    record_action({"type": "move", "params": {"x": 1.0}})

    last = None
    for _ in range(5):
        last = adjust_input(EvaluationResult(False, 0.0, ["x"], {}))
        if last is not None:
            record_action(last)

    assert last is not None
    assert adjust_input(EvaluationResult(False, 0.0, ["x"], {})) is None


def test_adjust_input_returns_none_without_last_action():
    _reset_state()

    assert adjust_input(EvaluationResult(False, 0.0, ["x"], {})) is None


def test_adjustment_state_is_isolated_per_agent():
    _reset_state()

    record_action({"type": "move", "params": {"x": 1.0}}, agent_id=1)
    record_action({"type": "move", "params": {"x": 4.0}}, agent_id=2)

    result_agent_1 = adjust_input(
        EvaluationResult(False, 0.0, ["x"], {}), agent_id=1
    )
    assert result_agent_1 == {"type": "move", "params": {"x": 1.5}}

    # Agent 2's state is untouched by agent 1's retry/intensity bookkeeping.
    state_agent_2 = adjustment._STATES[2]
    assert state_agent_2.retry_count == 0
    assert state_agent_2.intensity_scale == 1.0


def test_reset_adjustment_targets_single_agent():
    _reset_state()

    record_action({"type": "move", "params": {"x": 1.0}}, agent_id=1)
    record_action({"type": "move", "params": {"x": 1.0}}, agent_id=2)
    adjust_input(EvaluationResult(False, 0.0, ["x"], {}), agent_id=1)
    adjust_input(EvaluationResult(False, 0.0, ["x"], {}), agent_id=2)

    reset_adjustment(agent_id=1)

    assert 1 not in adjustment._STATES
    assert 2 in adjustment._STATES
    assert adjustment._STATES[2].retry_count == 1


def test_reset_adjustment_without_agent_clears_everything():
    _reset_state()

    record_action({"type": "move", "params": {"x": 1.0}}, agent_id=1)
    record_action({"type": "move", "params": {"x": 1.0}}, agent_id=2)

    reset_adjustment()

    assert adjustment._STATES == {}
