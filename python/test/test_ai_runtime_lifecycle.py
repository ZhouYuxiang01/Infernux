from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


AI_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "Infernux" / "ai_runtime"


def _load_lifecycle(monkeypatch, *, control_clear, actions_clear):
    """Load lifecycle.py in isolation, with stubbed clear_control / clear_actions.

    The module performs deferred imports of control_signal.clear_control and
    input_api.clear_actions inside its helpers, so we install fake modules
    under those names before executing it.
    """
    fake_control_signal = types.SimpleNamespace(clear_control=control_clear)
    fake_input_api = types.SimpleNamespace(clear_actions=actions_clear)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.control_signal", fake_control_signal)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.input_api", fake_input_api)

    spec = importlib.util.spec_from_file_location(
        "test_lifecycle_module", AI_RUNTIME_DIR / "lifecycle.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_recorder():
    calls: list[str] = []

    def control_clear():
        calls.append("clear_control")

    def actions_clear():
        calls.append("clear_actions")

    return calls, control_clear, actions_clear


def test_on_enter_play_mode_clears_control_and_legacy_actions(monkeypatch):
    calls, control_clear, actions_clear = _make_recorder()
    lifecycle = _load_lifecycle(monkeypatch, control_clear=control_clear, actions_clear=actions_clear)

    lifecycle.on_enter_play_mode()

    assert calls == ["clear_control", "clear_actions"]


def test_on_exit_play_mode_clears_control_and_legacy_actions(monkeypatch):
    calls, control_clear, actions_clear = _make_recorder()
    lifecycle = _load_lifecycle(monkeypatch, control_clear=control_clear, actions_clear=actions_clear)

    lifecycle.on_exit_play_mode()

    assert calls == ["clear_control", "clear_actions"]


def test_clear_runtime_control_state_is_resilient_to_legacy_failure(monkeypatch):
    calls, control_clear, _actions_clear = _make_recorder()

    def actions_clear_raises():
        raise RuntimeError("legacy backend disconnected")

    lifecycle = _load_lifecycle(
        monkeypatch, control_clear=control_clear, actions_clear=actions_clear_raises
    )

    # Must not raise even though the legacy clear_actions blew up.
    lifecycle.clear_runtime_control_state()

    # control_signal.clear_control still ran first.
    assert calls == ["clear_control"]


def test_on_scene_loaded_and_unloaded_clear_control_state(monkeypatch):
    calls, control_clear, actions_clear = _make_recorder()
    lifecycle = _load_lifecycle(monkeypatch, control_clear=control_clear, actions_clear=actions_clear)

    lifecycle.on_scene_loaded()
    lifecycle.on_scene_unloaded()

    assert calls == [
        "clear_control",
        "clear_actions",
        "clear_control",
        "clear_actions",
    ]
