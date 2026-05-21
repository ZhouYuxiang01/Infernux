from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TOOLS_PATH = ROOT / "Infernux" / "mcp" / "tools" / "runtime.py"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_runtime_tools(monkeypatch, world_model):
    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.mcp")
    _ensure_package(monkeypatch, "Infernux.mcp.tools")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")

    class _Queue:
        @staticmethod
        def instance():
            return _Queue()

        def run_sync(self, name, fn, timeout_ms=30000):
            return fn()

    common = types.ModuleType("Infernux.mcp.tools.common")
    common.fail = lambda code, message, **kwargs: {"ok": False, "error": {"code": code, "message": message}}
    common.find_game_object = lambda object_id: None
    common.ok = lambda data=None, **kwargs: {"ok": True, "data": data if data is not None else {}}
    common.register_tool_metadata = lambda *args, **kwargs: None
    common.serialize_component = lambda comp: {}
    common.serialize_value = lambda value: value

    threading = types.ModuleType("Infernux.mcp.threading")
    threading.MainThreadCommandQueue = _Queue

    monkeypatch.setitem(sys.modules, "Infernux.mcp.threading", threading)
    monkeypatch.setitem(sys.modules, "Infernux.mcp.tools.common", common)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.world_model", world_model)

    spec = importlib.util.spec_from_file_location("Infernux.mcp.tools.runtime", RUNTIME_TOOLS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.mcp.tools.runtime", module)
    spec.loader.exec_module(module)
    return module


class _FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


class _Payload:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


def test_runtime_registers_world_model_tools(monkeypatch):
    calls = []
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: calls.append(("snapshot", kwargs)) or _Payload({"entities": []})
    world_model.get_component_schema = lambda name: _Payload({"type": name}) if name == "Transform" else None
    world_model.diff_world_snapshots = lambda before, after: calls.append(("diff", before, after)) or _Payload({"fields_changed": []})

    module = _load_runtime_tools(monkeypatch, world_model)
    mcp = _FakeMcp()

    module.register_runtime_tools(mcp)

    assert "runtime_get_world_snapshot" in mcp.tools
    assert "runtime_get_component_schema" in mcp.tools
    assert "runtime_diff_world_snapshots" in mcp.tools

    snapshot = mcp.tools["runtime_get_world_snapshot"](include_components=False, include_fields=False)
    assert snapshot == {"ok": True, "data": {"entities": []}}
    assert calls[0] == ("snapshot", {"include_components": False, "include_fields": False})

    schema = mcp.tools["runtime_get_component_schema"]("Transform")
    assert schema == {"ok": True, "data": {"type": "Transform"}}

    missing = mcp.tools["runtime_get_component_schema"]("Missing")
    assert missing["ok"] is False
    assert missing["error"]["code"] == "error.not_found"

    diff = mcp.tools["runtime_diff_world_snapshots"]({"entities": []}, {"entities": []})
    assert diff == {"ok": True, "data": {"fields_changed": []}}
    assert calls[-1] == ("diff", {"entities": []}, {"entities": []})


def test_runtime_submit_and_clear_control_tools(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]
    submitted = []
    cleared = []

    class _Signal:
        def __init__(
            self,
            channel_id=0,
            axes=None,
            buttons=None,
            duration_ms=None,
            timestamp_ms=None,
            agent_id=None,
        ):
            self.channel_id = channel_id
            self.axes = axes or {}
            self.buttons = buttons or {}
            self.duration_ms = duration_ms
            self.timestamp_ms = timestamp_ms
            self.agent_id = agent_id

    ai_runtime.ControlSignal = _Signal
    ai_runtime.submit_control = lambda signal: submitted.append(signal)
    ai_runtime.clear_control = lambda channel_id=None: cleared.append(channel_id)
    ai_runtime.get_control_state = lambda channel_id=0: submitted[-1] if submitted else None
    ai_runtime.assert_can_use_control_path = lambda path: None

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    assert "runtime_submit_control" in mcp.tools
    assert "runtime_clear_control" in mcp.tools

    result = mcp.tools["runtime_submit_control"](
        channel_id=2,
        axes={"move_x": 1.5},
        buttons={"jump": True},
        duration_ms=250,
        agent_id=7,
    )

    assert result["ok"] is True
    assert submitted
    assert submitted[0].channel_id == 2
    assert submitted[0].axes == {"move_x": 1.5}
    assert submitted[0].buttons == {"jump": True}
    assert submitted[0].duration_ms == 250
    assert submitted[0].agent_id == 7
    assert result["data"]["signal"]["channel_id"] == 2
    assert result["data"]["signal"]["axes"] == {"move_x": 1.5}

    clear_result = mcp.tools["runtime_clear_control"](channel_id=2)

    assert clear_result == {"ok": True, "data": {"cleared_channel_id": 2}}
    assert cleared == [2]


def test_runtime_submit_control_uses_experiment_guard(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]
    guard_calls = []

    class _Signal:
        def __init__(self, channel_id=0, axes=None, buttons=None, duration_ms=None, timestamp_ms=None, agent_id=None):
            self.channel_id = channel_id
            self.axes = axes or {}
            self.buttons = buttons or {}
            self.duration_ms = duration_ms
            self.timestamp_ms = timestamp_ms
            self.agent_id = agent_id

    ai_runtime.ControlSignal = _Signal
    ai_runtime.assert_can_use_control_path = lambda path: guard_calls.append(path)
    ai_runtime.submit_control = lambda signal: None
    ai_runtime.get_control_state = lambda channel_id=0: None

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    result = mcp.tools["runtime_submit_control"](axes={"move_x": 1.0})

    assert result["ok"] is True
    assert guard_calls == ["control_signal"]


def test_runtime_submit_control_reports_experiment_guard_violation(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]

    class _Violation(RuntimeError):
        pass

    _Violation.__name__ = "ExperimentGuardViolation"

    class _Signal:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    ai_runtime.ControlSignal = _Signal
    ai_runtime.assert_can_use_control_path = lambda path: (_ for _ in ()).throw(_Violation("requires mcp_health"))
    ai_runtime.submit_control = lambda signal: None
    ai_runtime.get_control_state = lambda channel_id=0: None

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    result = mcp.tools["runtime_submit_control"](axes={"move_x": 1.0})

    assert result["ok"] is False
    assert result["error"]["code"] == "error.experiment_guard"


def test_runtime_run_for_reports_experiment_guard_violation(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]

    class _Violation(RuntimeError):
        pass

    _Violation.__name__ = "ExperimentGuardViolation"
    ai_runtime.assert_can_advance_mode = lambda mode: (_ for _ in ()).throw(_Violation("advance mode mismatch"))

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    result = mcp.tools["runtime_run_for"](seconds=0.0)

    assert result["ok"] is False
    assert result["error"]["code"] == "error.experiment_guard"


def test_runtime_experiment_guard_tools(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]
    marked = []

    ai_runtime.begin_experiment = lambda mode="step", require_health_check=True: _Payload({
        "active": True,
        "mode": mode,
        "require_health_check": require_health_check,
    })
    ai_runtime.experiment_status = lambda: _Payload({"active": True, "mode": "run"})
    ai_runtime.end_experiment = lambda: _Payload({"active": False, "mode": "run"})
    ai_runtime.mark_health_check = lambda: marked.append("health") or _Payload({"health_checked": True})

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    assert mcp.tools["runtime_experiment_begin"](mode="run") == {
        "ok": True,
        "data": {"active": True, "mode": "run", "require_health_check": True},
    }
    assert mcp.tools["runtime_experiment_mark_health_check"]()["data"] == {"health_checked": True}
    assert marked == ["health"]
    assert mcp.tools["runtime_experiment_status"]()["data"] == {"active": True, "mode": "run"}
    assert mcp.tools["runtime_experiment_end"]()["data"] == {"active": False, "mode": "run"}


def test_runtime_edit_transaction_tools(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]
    calls = []

    class _Tx:
        def move_entity(self, entity_id, position):
            calls.append(("move", entity_id, position))
            return self

        def set_component(self, entity_id, key, value):
            calls.append(("set", entity_id, key, value))
            return self

        def preview(self):
            return _Payload({"ok": True, "preview": True})

        def commit(self):
            return _Payload({"ok": True, "committed": True})

    ai_runtime.edit_transaction = lambda mode="auto": calls.append(("mode", mode)) or _Tx()

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)
    operations = [
        {"op": "move_entity", "entity_id": 7, "position": [1, 2, 3]},
        {"op": "set_component", "entity_id": 7, "key": "mass", "value": 2.0},
    ]

    preview = mcp.tools["runtime_edit_transaction_preview"](operations=operations, mode="edit")
    commit = mcp.tools["runtime_edit_transaction_commit"](operations=operations, mode="runtime")

    assert preview == {"ok": True, "data": {"ok": True, "preview": True}}
    assert commit == {"ok": True, "data": {"ok": True, "committed": True}}
    assert calls == [
        ("mode", "edit"),
        ("move", 7, [1, 2, 3]),
        ("set", 7, "mass", 2.0),
        ("mode", "runtime"),
        ("move", 7, [1, 2, 3]),
        ("set", 7, "mass", 2.0),
    ]


def test_runtime_capture_game_view_tool(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})

    visual_observation = types.ModuleType("Infernux.ai_runtime.visual_observation")
    visual_observation.capture_game_view = lambda output_path="": {
        "available": True,
        "source": "window_capture",
        "image_path": output_path or "C:/Temp/game_view.png",
    }
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.visual_observation", visual_observation)

    module = _load_runtime_tools(monkeypatch, world_model)
    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    assert "runtime_capture_game_view" in mcp.tools
    result = mcp.tools["runtime_capture_game_view"](output_path="C:/Temp/custom.png")

    assert result == {
        "ok": True,
        "data": {
            "available": True,
            "source": "window_capture",
            "image_path": "C:/Temp/custom.png",
        },
    }
