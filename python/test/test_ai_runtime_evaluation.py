from __future__ import annotations

from Infernux.ai_runtime import EvaluationResult, evaluate


def test_evaluate_all_boolean_pass():
    result = evaluate({"a": True, "b": True})

    assert isinstance(result, EvaluationResult)
    assert result.success is True
    assert result.score == 1.0
    assert result.failures == []
    assert result.metrics == {"a": True, "b": True}


def test_evaluate_partial_boolean_failures():
    result = evaluate({"a": True, "b": False, "c": False})

    assert result.success is False
    assert result.score == 1 / 3
    assert result.failures == ["b", "c"]
    assert result.metrics == {"a": True, "b": False, "c": False}


def test_evaluate_numeric_metrics_only():
    result = evaluate({"distance": 0.75, "count": 3})

    assert result.success is True
    assert result.score == 1.0
    assert result.failures == []
    assert result.metrics == {"distance": 0.75, "count": 3}


def test_evaluate_mixed_types():
    metrics = {"a": True, "distance": 0.3, "tag": "ok", "b": False}
    result = evaluate(metrics)

    assert result.success is False
    assert result.score == 0.5
    assert result.failures == ["b"]
    assert result.metrics == metrics


def test_evaluate_empty_metrics():
    result = evaluate({})

    assert result.success is True
    assert result.score == 1.0
    assert result.failures == []
    assert result.metrics == {}
