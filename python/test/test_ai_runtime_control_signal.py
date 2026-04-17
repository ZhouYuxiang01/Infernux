from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_control_signal():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "Infernux"
        / "ai_runtime"
        / "control_signal.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_control_signal_module", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeInputManager:
    def __init__(self):
        self.calls = []
        self.cleared = 0

    def set_virtual_action(self, action, active=True, x=0.0, y=0.0):
        self.calls.append((action, bool(active), float(x), float(y)))

    def clear_virtual_actions(self):
        self.cleared += 1


def _install_fake_manager(module, monkeypatch):
    manager = _FakeInputManager()
    monkeypatch.setattr(module, "_get_input_manager", lambda: manager)
    return manager


def test_submit_control_caches_last_write_per_channel(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    signal_a = cs.ControlSignal(channel_id=0, buttons={"jump": True})
    signal_b = cs.ControlSignal(channel_id=0, buttons={"attack": True})
    cs.submit_control(signal_a)
    cs.submit_control(signal_b)

    stored = cs._get_channel_state(0)
    assert stored is not None
    # last-write-wins: channel 0 now reflects signal_b, not signal_a.
    assert stored.buttons == {"attack": True}


def test_submit_control_clamps_axes_to_unit_range(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    signal = cs.ControlSignal(
        channel_id=0,
        axes={"move_x": 2.5, "move_y": -9.0, "aim_x": 0.25},
    )
    cs.submit_control(signal)

    stored = cs._get_channel_state(0)
    assert stored is not None
    assert stored.axes["move_x"] == 1.0
    assert stored.axes["move_y"] == -1.0
    assert stored.axes["aim_x"] == 0.25


def test_submit_control_stamps_timestamp_when_missing(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    signal = cs.ControlSignal(channel_id=3)
    cs.submit_control(signal)
    stored = cs._get_channel_state(3)
    assert stored is not None
    assert stored.timestamp_ms is not None
    assert isinstance(stored.timestamp_ms, int)


def test_submit_control_preserves_caller_timestamp(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    signal = cs.ControlSignal(channel_id=0, timestamp_ms=42)
    cs.submit_control(signal)
    stored = cs._get_channel_state(0)
    assert stored is not None
    assert stored.timestamp_ms == 42


def test_submit_control_forwards_known_buttons_to_legacy_backend(monkeypatch):
    cs = _load_control_signal()
    manager = _install_fake_manager(cs, monkeypatch)

    cs.submit_control(
        cs.ControlSignal(channel_id=0, buttons={"jump": True, "attack": False})
    )
    # Both recognised buttons are forwarded; "jump" as True, "attack" as False.
    actions = [(a, active) for a, active, _, _ in manager.calls]
    assert ("jump", True) in actions
    assert ("attack", False) in actions


def test_submit_control_prefers_native_channel_when_available(monkeypatch):
    cs = _load_control_signal()
    native_calls = []

    monkeypatch.setattr(cs, "_submit_native_signal", lambda signal: native_calls.append(signal) or True)
    monkeypatch.setattr(cs._legacy_input_bridge, "apply_signal", lambda signal: (_ for _ in ()).throw(AssertionError("legacy bridge should not be used")))

    cs.submit_control(cs.ControlSignal(channel_id=2, buttons={"jump": True}))

    assert native_calls
    assert native_calls[0].channel_id == 2
    assert cs.get_control_state(2) is not None


def test_submit_control_forwards_move_axes_only_when_addressed(monkeypatch):
    cs = _load_control_signal()
    manager = _install_fake_manager(cs, monkeypatch)

    # No axes keys → no "move" call should happen.
    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"jump": True}))
    assert all(call[0] != "move" for call in manager.calls)

    # Addressing move_x triggers a move call; move_y defaults to 0.
    manager.calls.clear()
    cs.submit_control(cs.ControlSignal(channel_id=0, axes={"move_x": 0.5}))
    move_calls = [c for c in manager.calls if c[0] == "move"]
    assert move_calls, "move axis submission should reach the backend"
    _, active, x, y = move_calls[-1]
    assert active is True
    assert x == 0.5
    assert y == 0.0


def test_submit_control_zeroed_move_deactivates(monkeypatch):
    cs = _load_control_signal()
    manager = _install_fake_manager(cs, monkeypatch)

    cs.submit_control(cs.ControlSignal(channel_id=0, axes={"move_x": 0.0, "move_y": 0.0}))
    move_calls = [c for c in manager.calls if c[0] == "move"]
    assert move_calls
    _, active, x, y = move_calls[-1]
    assert active is False
    assert x == 0.0
    assert y == 0.0


def test_clear_control_scoped_to_channel(monkeypatch):
    cs = _load_control_signal()
    manager = _install_fake_manager(cs, monkeypatch)

    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"jump": True}))
    cs.submit_control(cs.ControlSignal(channel_id=7, buttons={"jump": True}))

    cs.clear_control(channel_id=7)
    # Channel 7 state is gone; channel 0 still present.
    assert cs._get_channel_state(7) is None
    assert cs._get_channel_state(0) is not None
    # Clearing a non-default channel must NOT touch the legacy backend.
    assert manager.cleared == 0


def test_clear_control_without_channel_clears_everything(monkeypatch):
    cs = _load_control_signal()
    manager = _install_fake_manager(cs, monkeypatch)

    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"jump": True}))
    cs.submit_control(cs.ControlSignal(channel_id=1, buttons={"attack": True}))

    cs.clear_control()
    assert cs._get_channel_state(0) is None
    assert cs._get_channel_state(1) is None
    # clear_control(None) also flushes the legacy backend.
    assert manager.cleared == 1


def test_clear_control_prefers_native_channel_when_available(monkeypatch):
    cs = _load_control_signal()
    native_calls = []

    monkeypatch.setattr(cs, "_clear_native_channel", lambda channel_id: native_calls.append(channel_id) or True)
    monkeypatch.setattr(cs._legacy_input_bridge, "clear", lambda: (_ for _ in ()).throw(AssertionError("legacy clear should not be used")))

    cs.submit_control(cs.ControlSignal(channel_id=7, buttons={"jump": True}))
    cs.clear_control(channel_id=7)

    assert native_calls == [7]
    assert cs._get_channel_state(7) is None


def test_submit_control_rejects_non_controlsignal(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    try:
        cs.submit_control({"channel_id": 0, "buttons": {"jump": True}})  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("submit_control must reject non-ControlSignal input")


def test_submit_control_handles_nan_axis(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    nan = float("nan")
    cs.submit_control(cs.ControlSignal(channel_id=0, axes={"move_x": nan}))
    stored = cs._get_channel_state(0)
    assert stored is not None
    assert stored.axes["move_x"] == 0.0
