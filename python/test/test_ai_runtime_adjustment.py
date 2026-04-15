from __future__ import annotations

import Infernux.ai_runtime.adjustment as adjustment
from Infernux.ai_runtime import EvaluationResult, adjust_input, record_action


def _reset_state():
    adjustment._STATE = adjustment._AdjustmentState()


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
    assert adjustment._STATE.intensity_scale <= 5.0
    assert adjustment._STATE.intensity_scale == 5.0


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
