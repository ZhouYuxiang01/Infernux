from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ExperimentGuardViolation(RuntimeError):
    """Raised when an active runtime experiment violates its guard rules."""


@dataclass(frozen=True, slots=True)
class ExperimentGuardState:
    active: bool = False
    mode: str = "step"
    require_health_check: bool = True
    health_checked: bool = False
    control_paths: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "mode": self.mode,
            "require_health_check": self.require_health_check,
            "health_checked": self.health_checked,
            "control_paths": list(self.control_paths),
            "violations": list(self.violations),
        }


@dataclass(slots=True)
class _MutableGuardState:
    active: bool = False
    mode: str = "step"
    require_health_check: bool = True
    health_checked: bool = False
    control_paths: set[str] = field(default_factory=set)
    violations: list[str] = field(default_factory=list)


_STATE = _MutableGuardState()
_VALID_MODES = {"step", "run"}


def _snapshot() -> ExperimentGuardState:
    return ExperimentGuardState(
        active=_STATE.active,
        mode=_STATE.mode,
        require_health_check=_STATE.require_health_check,
        health_checked=_STATE.health_checked,
        control_paths=tuple(sorted(_STATE.control_paths)),
        violations=tuple(_STATE.violations),
    )


def _violate(message: str) -> None:
    _STATE.violations.append(message)
    raise ExperimentGuardViolation(message)


def begin_experiment(mode: str = "step", require_health_check: bool = True) -> ExperimentGuardState:
    normalized = str(mode or "step").strip().lower()
    if normalized not in _VALID_MODES:
        raise ValueError("mode must be 'step' or 'run'")
    _STATE.active = True
    _STATE.mode = normalized
    _STATE.require_health_check = bool(require_health_check)
    _STATE.health_checked = False
    _STATE.control_paths.clear()
    _STATE.violations.clear()
    return _snapshot()


def experiment_status() -> ExperimentGuardState:
    return _snapshot()


def end_experiment() -> ExperimentGuardState:
    _STATE.active = False
    _STATE.control_paths.clear()
    return _snapshot()


def mark_health_check() -> ExperimentGuardState:
    _STATE.health_checked = True
    return _snapshot()


def assert_can_use_control_path(path: str) -> ExperimentGuardState:
    normalized = str(path or "").strip()
    if not normalized:
        _violate("control path is required")
    if not _STATE.active:
        return _snapshot()
    if _STATE.require_health_check and not _STATE.health_checked:
        _violate("runtime experiment requires mcp_health before control")
    if _STATE.control_paths and normalized not in _STATE.control_paths:
        existing = ", ".join(sorted(_STATE.control_paths))
        _violate(f"mixed control paths are not allowed: existing={existing}, requested={normalized}")
    _STATE.control_paths.add(normalized)
    return _snapshot()


def assert_can_advance_mode(mode: str) -> ExperimentGuardState:
    normalized = str(mode or "").strip().lower()
    if normalized not in _VALID_MODES:
        _violate("advance mode must be 'step' or 'run'")
    if not _STATE.active:
        return _snapshot()
    if normalized != _STATE.mode:
        _violate(f"runtime experiment advance mode mismatch: expected={_STATE.mode}, requested={normalized}")
    return _snapshot()


__all__ = [
    "ExperimentGuardState",
    "ExperimentGuardViolation",
    "assert_can_advance_mode",
    "assert_can_use_control_path",
    "begin_experiment",
    "end_experiment",
    "experiment_status",
    "mark_health_check",
]
