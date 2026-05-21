from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "Infernux" / "mcp" / "tools"


class _FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self, name):
        def _decorator(fn):
            self.tools[name] = fn
            return fn

        return _decorator


def _install_module(monkeypatch, name: str, module: types.ModuleType) -> None:
    monkeypatch.setitem(sys.modules, name, module)


def _load_editor_tools(monkeypatch):
    for name in list(sys.modules):
        if name == "Infernux" or name.startswith("Infernux."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    infernux = types.ModuleType("Infernux")
    infernux.__path__ = []  # type: ignore[attr-defined]
    _install_module(monkeypatch, "Infernux", infernux)
    for package_name in ("Infernux.mcp", "Infernux.mcp.tools"):
        package = types.ModuleType(package_name)
        package.__path__ = []  # type: ignore[attr-defined]
        _install_module(monkeypatch, package_name, package)

    common = types.ModuleType("Infernux.mcp.tools.common")
    common.main_thread = lambda name, fn, **kwargs: fn()
    common.scene_status = lambda: {"play_state": "edit", "loading": False, "saved_to_file": True, "dirty": False}
    common.fail = lambda code, message, **kwargs: {"ok": False, "error": {"code": code, "message": message, **kwargs}}
    _install_module(monkeypatch, "Infernux.mcp.tools.common", common)

    ai_runtime = types.ModuleType("Infernux.ai_runtime")
    calls = []

    class ExperimentGuardViolation(RuntimeError):
        pass

    def _assert_can_advance_mode(mode):
        calls.append(mode)
        raise ExperimentGuardViolation("advance mode mismatch")

    ai_runtime.assert_can_advance_mode = _assert_can_advance_mode
    _install_module(monkeypatch, "Infernux.ai_runtime", ai_runtime)

    engine = types.ModuleType("Infernux.engine")
    engine.__path__ = []  # type: ignore[attr-defined]
    _install_module(monkeypatch, "Infernux.engine", engine)
    play_mode = types.ModuleType("Infernux.engine.play_mode")
    manager = SimpleNamespace(state=SimpleNamespace(name="paused"), step_frame=lambda: None)
    play_mode.PlayModeManager = SimpleNamespace(instance=lambda: manager)
    _install_module(monkeypatch, "Infernux.engine.play_mode", play_mode)

    spec = importlib.util.spec_from_file_location("Infernux.mcp.tools.editor", TOOLS_DIR / "editor.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    _install_module(monkeypatch, "Infernux.mcp.tools.editor", module)
    spec.loader.exec_module(module)
    return module, calls


def test_editor_step_reports_experiment_guard_violation(monkeypatch):
    module, calls = _load_editor_tools(monkeypatch)
    mcp = _FakeMcp()
    module.register_editor_tools(mcp)

    result = mcp.tools["editor_step"]()

    assert calls == ["step"]
    assert result["ok"] is False
    assert result["error"]["code"] == "error.experiment_guard"
