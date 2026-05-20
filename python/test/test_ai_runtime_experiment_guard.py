from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AI_RUNTIME_DIR = ROOT / "Infernux" / "ai_runtime"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = [str(AI_RUNTIME_DIR)] if name == "Infernux.ai_runtime" else []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_experiment_guard(monkeypatch):
    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")
    spec = importlib.util.spec_from_file_location(
        "Infernux.ai_runtime.experiment_guard",
        AI_RUNTIME_DIR / "experiment_guard.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.experiment_guard", module)
    spec.loader.exec_module(module)
    return module


def test_begin_status_end_experiment_guard(monkeypatch):
    guard = _load_experiment_guard(monkeypatch)

    state = guard.begin_experiment(mode="step", require_health_check=True)

    assert state.active is True
    assert state.mode == "step"
    assert state.require_health_check is True
    assert guard.experiment_status().active is True
    assert state.to_dict()["mode"] == "step"

    ended = guard.end_experiment()

    assert ended.active is False
    assert guard.experiment_status().active is False


def test_guard_requires_health_check_before_control(monkeypatch):
    guard = _load_experiment_guard(monkeypatch)
    guard.begin_experiment(mode="run", require_health_check=True)

    with pytest.raises(guard.ExperimentGuardViolation, match="requires mcp_health"):
        guard.assert_can_use_control_path("control_signal")

    status = guard.experiment_status()
    assert status.violations == ("runtime experiment requires mcp_health before control",)


def test_guard_allows_one_control_path_after_health_check(monkeypatch):
    guard = _load_experiment_guard(monkeypatch)
    guard.begin_experiment(mode="run", require_health_check=True)

    guard.mark_health_check()
    state = guard.assert_can_use_control_path("control_signal")

    assert state.control_paths == ("control_signal",)


def test_guard_blocks_mixed_control_paths(monkeypatch):
    guard = _load_experiment_guard(monkeypatch)
    guard.begin_experiment(mode="run", require_health_check=False)

    guard.assert_can_use_control_path("control_signal")

    with pytest.raises(guard.ExperimentGuardViolation, match="mixed control paths"):
        guard.assert_can_use_control_path("transform_mutation")


def test_guard_blocks_wrong_advance_mode(monkeypatch):
    guard = _load_experiment_guard(monkeypatch)
    guard.begin_experiment(mode="step", require_health_check=False)

    with pytest.raises(guard.ExperimentGuardViolation, match="advance mode"):
        guard.assert_can_advance_mode("run")


def test_inactive_guard_does_not_block_control(monkeypatch):
    guard = _load_experiment_guard(monkeypatch)

    state = guard.assert_can_use_control_path("control_signal")

    assert state.active is False
    assert state.control_paths == ()
