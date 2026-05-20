from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace


AI_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "Infernux" / "ai_runtime"


def _ensure_package(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = module
    return module


def _load_module(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, AI_RUNTIME_DIR / file_name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_control_signal():
    _ensure_package("Infernux")
    _ensure_package("Infernux.ai_runtime")
    _load_module("Infernux.ai_runtime._legacy_input_bridge", "_legacy_input_bridge.py")
    return _load_module("Infernux.ai_runtime.control_signal", "control_signal.py")


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
    monkeypatch.setattr(module._legacy_input_bridge, "_get_input_manager", lambda: manager)
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


def test_get_control_state_projects_native_channel_to_control_signal(monkeypatch):
    cs = _load_control_signal()

    # Native InputChannel encodes "absent" as -1 for duration_ms / timestamp_ms.
    native_channel = SimpleNamespace(
        channel_id=2,
        axes={"move_x": 0.5},
        buttons={"jump": True},
        duration_ms=-1,
        timestamp_ms=12345,
    )
    manager = SimpleNamespace(get_channel_state=lambda cid: native_channel if cid == 2 else None)
    monkeypatch.setattr(cs, "_get_input_manager", lambda: manager)

    result = cs.get_control_state(2)
    assert isinstance(result, cs.ControlSignal)
    assert result.channel_id == 2
    assert result.axes == {"move_x": 0.5}
    assert result.buttons == {"jump": True}
    assert result.duration_ms is None  # -1 sentinel projected to None
    assert result.timestamp_ms == 12345


def test_get_control_state_falls_back_to_python_cache_when_native_returns_none(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    # Submit one signal so the Python-side cache has an entry on channel 0.
    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"jump": True}))

    # Native manager returns None (channel never seen by native side).
    manager = SimpleNamespace(get_channel_state=lambda cid: None)
    monkeypatch.setattr(cs, "_get_input_manager", lambda: manager)

    result = cs.get_control_state(0)
    assert isinstance(result, cs.ControlSignal)
    assert result.buttons == {"jump": True}


def test_duration_ms_expires_python_cache_and_backend(monkeypatch):
    cs = _load_control_signal()
    manager = _install_fake_manager(cs, monkeypatch)
    now = [100.0]
    monkeypatch.setattr(cs.time, "monotonic", lambda: now[0])

    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"jump": True}, duration_ms=50))

    now[0] = 100.049
    assert cs.get_control_state(0) is not None
    assert manager.cleared == 0

    now[0] = 100.051
    assert cs.get_control_state(0) is None
    assert manager.cleared == 1


def test_expire_control_signals_clears_only_expired_channels(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)
    now = [200.0]
    monkeypatch.setattr(cs.time, "monotonic", lambda: now[0])

    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"hold": True}, duration_ms=10))
    cs.submit_control(cs.ControlSignal(channel_id=1, buttons={"keep": True}, duration_ms=100))

    now[0] = 200.02
    expired = cs.expire_control_signals()

    assert expired == 1
    assert cs.get_control_state(0) is None
    assert cs.get_control_state(1) is not None


def test_control_signal_agent_id_default_is_none(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    cs.submit_control(cs.ControlSignal(channel_id=0, buttons={"jump": True}))
    stored = cs._get_channel_state(0)
    assert stored is not None
    # Default agent_id stays None on the Python side; the native backend is
    # responsible for stamping 0 onto recorded events for single-agent
    # compatibility.
    assert stored.agent_id is None


def test_control_signal_agent_id_preserved_through_normalization(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    # Two agents share channel 0 (last-write-wins); we only check the
    # second submission's agent_id survives normalization.
    cs.submit_control(cs.ControlSignal(channel_id=0, agent_id=7, buttons={"jump": True}))
    stored = cs._get_channel_state(0)
    assert stored is not None
    assert stored.agent_id == 7


def test_control_signal_agent_id_independent_from_channel_id(monkeypatch):
    cs = _load_control_signal()
    _install_fake_manager(cs, monkeypatch)

    # One agent driving two distinct channels.
    cs.submit_control(cs.ControlSignal(channel_id=2, agent_id=42, buttons={"jump": True}))
    cs.submit_control(cs.ControlSignal(channel_id=3, agent_id=42, buttons={"attack": True}))

    a = cs._get_channel_state(2)
    b = cs._get_channel_state(3)
    assert a is not None and b is not None
    assert a.channel_id == 2 and b.channel_id == 3
    assert a.agent_id == 42 and b.agent_id == 42


def test_control_signal_native_channel_carries_agent_id(monkeypatch):
    cs = _load_control_signal()

    captured = []

    class _NativeChannelStub:
        # Mimics pybind11-bound InputChannel: settable attributes only.
        def __init__(self):
            self.channel_id = 0
            self.axes = {}
            self.buttons = {}
            self.duration_ms = -1
            self.timestamp_ms = -1
            self.agent_id = None

    def fake_input_channel():
        return _NativeChannelStub()

    fake_lib = SimpleNamespace(InputChannel=fake_input_channel)
    import sys
    monkeypatch.setitem(sys.modules, "Infernux.lib", fake_lib)

    class _Manager:
        def submit_channel_signal(self, native):
            captured.append(native)

    monkeypatch.setattr(cs, "_get_input_manager", lambda: _Manager())

    cs.submit_control(cs.ControlSignal(channel_id=1, agent_id=9, buttons={"jump": True}))
    assert captured
    assert captured[0].agent_id == 9
    assert captured[0].channel_id == 1
