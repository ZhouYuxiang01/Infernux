from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INFERNUX_DIR = ROOT / "Infernux"
AI_RUNTIME_DIR = INFERNUX_DIR / "ai_runtime"


def _clear_infernux_modules(monkeypatch):
    for name in list(sys.modules):
        if name == "Infernux" or name.startswith("Infernux."):
            monkeypatch.delitem(sys.modules, name, raising=False)


def _install_infernux_package(monkeypatch):
    infernux = types.ModuleType("Infernux")
    infernux.__path__ = [str(INFERNUX_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "Infernux", infernux)


def _load_legacy_namespace(monkeypatch):
    _clear_infernux_modules(monkeypatch)
    _install_infernux_package(monkeypatch)
    package = types.ModuleType("Infernux.ai_runtime")
    package.__path__ = [str(AI_RUNTIME_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime", package)

    spec = importlib.util.spec_from_file_location(
        "Infernux.ai_runtime.legacy",
        AI_RUNTIME_DIR / "legacy.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.legacy", module)
    spec.loader.exec_module(module)
    return module


def _load_ai_runtime_package(monkeypatch):
    _clear_infernux_modules(monkeypatch)
    _install_infernux_package(monkeypatch)

    spec = importlib.util.spec_from_file_location(
        "Infernux.ai_runtime",
        AI_RUNTIME_DIR / "__init__.py",
        submodule_search_locations=[str(AI_RUNTIME_DIR)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime", module)
    spec.loader.exec_module(module)
    return module


def test_legacy_namespace_exports_player_and_action_apis(monkeypatch):
    legacy = _load_legacy_namespace(monkeypatch)

    assert legacy.ActionType.Jump == "jump"
    assert hasattr(legacy, "send_action")
    assert hasattr(legacy, "PlayerSnapshot")
    assert hasattr(legacy, "get_player_snapshot")
    assert "send_action" in legacy.__all__


def test_root_reexports_legacy_symbols_during_migration(monkeypatch):
    runtime = _load_ai_runtime_package(monkeypatch)

    assert hasattr(runtime, "legacy")
    assert runtime.send_action is runtime.legacy.send_action
    assert runtime.PlayerSnapshot is runtime.legacy.PlayerSnapshot
