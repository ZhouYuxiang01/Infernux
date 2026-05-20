from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_TOOLS_PATH = ROOT / "Infernux" / "mcp" / "tools" / "docs.py"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_docs_tools(monkeypatch):
    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.mcp")
    _ensure_package(monkeypatch, "Infernux.mcp.tools")

    capabilities = types.ModuleType("Infernux.mcp.capabilities")
    capabilities.current_config = lambda: {"enabled": True}
    capabilities.tool_enabled = lambda name: True
    capabilities.feature_enabled = lambda name: False
    capabilities.limit = lambda name, default=None: default

    server = types.ModuleType("Infernux.mcp.server")
    server.endpoint_url = lambda: "http://127.0.0.1:9713/mcp"
    server.is_running = lambda: True
    server.connection_info = lambda: {"clients": {}, "url": "http://127.0.0.1:9713/mcp"}

    class _Queue:
        @staticmethod
        def instance():
            return _Queue()

        def wait_until_ready(self, timeout):
            return True

    threading = types.ModuleType("Infernux.mcp.threading")
    threading.MainThreadCommandQueue = _Queue

    common = types.ModuleType("Infernux.mcp.tools.common")
    metadata = {}
    common.MCP_PROTOCOL_VERSION = "2025-03-26"
    common.MCP_SERVER_VERSION = "0.2.0"
    common.get_asset_database = lambda: object()
    common.get_tool_metadata = lambda name: metadata.get(name, {"name": name})
    common.list_tool_metadata = lambda: list(metadata.values())
    common.main_thread = lambda name, fn, **kwargs: {"ok": True, "data": fn()}
    common.ok = lambda data=None, **kwargs: {"ok": True, "data": data if data is not None else {}}

    def _register_tool_metadata(name, **kwargs):
        metadata[name] = {"name": name, **kwargs}

    common.register_tool_metadata = _register_tool_metadata
    common.scene_status = lambda: {
        "scene": "DemoScene",
        "path": "Assets/Scenes/DemoScene.scene",
        "absolute_path": "C:/Project/Assets/Scenes/DemoScene.scene",
        "dirty": False,
        "loading": False,
        "play_state": "edit",
        "saved_to_file": True,
        "suggested_save_path": "",
        "requires_save_before_mcp_mutation": False,
    }

    monkeypatch.setitem(sys.modules, "Infernux.mcp.capabilities", capabilities)
    monkeypatch.setitem(sys.modules, "Infernux.mcp.server", server)
    monkeypatch.setitem(sys.modules, "Infernux.mcp.threading", threading)
    monkeypatch.setitem(sys.modules, "Infernux.mcp.tools.common", common)

    spec = importlib.util.spec_from_file_location("Infernux.mcp.tools.docs", DOCS_TOOLS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.mcp.tools.docs", module)
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


class _Vec:
    x = 1.0
    y = 2.0
    z = 3.0


class _Transform:
    position = _Vec()


class _Component:
    type_name = "MeshRenderer"


class _Object:
    id = 42
    name = "Player"
    tag = "Player"
    active = True
    transform = _Transform()

    def get_components(self):
        return [_Component()]

    def get_py_components(self):
        return []


class _Scene:
    name = "DemoScene"

    def get_all_objects(self):
        return [_Object()]


class _SceneManager:
    @staticmethod
    def instance():
        return _SceneManager()

    def get_active_scene(self):
        return _Scene()


def test_agent_bootstrap_returns_operating_manual(monkeypatch):
    module = _load_docs_tools(monkeypatch)
    mcp = _FakeMcp()

    module.register_docs_tools(mcp, "C:/Project", {})

    assert "agent_bootstrap" in mcp.tools
    payload = mcp.tools["agent_bootstrap"](agent_name="codex", task_intent="move a ball")

    assert payload["ok"] is True
    data = payload["data"]
    assert data["identity"]["engine_role"] == "agent-operable runtime operating system"
    assert data["core_boundary"]["engine_is_not_agent"] is True
    assert data["startup_sequence"][0]["tool"] == "agent_bootstrap"
    assert "runtime_explain_current_scene" in [step["tool"] for step in data["startup_sequence"]]
    assert any(rule["id"] == "observe_before_mutate" for rule in data["rules"])
    assert any(recipe["path"].endswith("docs/agent/recipes/control_runtime.md") for recipe in data["recipes"])


def test_runtime_explain_current_scene_summarizes_scene(monkeypatch):
    module = _load_docs_tools(monkeypatch)
    lib = types.ModuleType("Infernux.lib")
    lib.SceneManager = _SceneManager
    monkeypatch.setitem(sys.modules, "Infernux.lib", lib)
    mcp = _FakeMcp()

    module.register_docs_tools(mcp, "C:/Project", {})

    assert "runtime_explain_current_scene" in mcp.tools
    payload = mcp.tools["runtime_explain_current_scene"](include_objects=True, limit=5)

    assert payload["ok"] is True
    data = payload["data"]
    assert data["status"]["scene"] == "DemoScene"
    assert data["object_summary"]["object_count"] == 1
    assert data["object_summary"]["objects"][0]["name"] == "Player"
    assert data["object_summary"]["objects"][0]["components"] == ["MeshRenderer"]
    assert "runtime_get_world_snapshot" in data["recommended_next_tools"]
