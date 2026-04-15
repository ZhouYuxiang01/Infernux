from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationResult:
    success: bool
    score: float
    failures: list[str]
    metrics: dict[str, Any]


def evaluate(metrics: dict[str, Any]) -> EvaluationResult:
    copied_metrics = dict(metrics)

    bool_keys: list[str] = []
    failures: list[str] = []

    for key, value in copied_metrics.items():
        if isinstance(value, bool):
            bool_keys.append(key)
            if not value:
                failures.append(key)

    if bool_keys:
        score = (len(bool_keys) - len(failures)) / len(bool_keys)
    else:
        score = 1.0

    return EvaluationResult(
        success=not failures,
        score=float(score),
        failures=failures,
        metrics=copied_metrics,
    )
