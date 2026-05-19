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
