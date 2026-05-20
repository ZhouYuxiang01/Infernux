from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INFERNUX_DIR = ROOT / "Infernux"
AI_RUNTIME_DIR = INFERNUX_DIR / "ai_runtime"


def test_ai_runtime_package_imports_without_native_modules(monkeypatch):
    for name in list(sys.modules):
        if name == "Infernux" or name.startswith("Infernux."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    infernux = types.ModuleType("Infernux")
    infernux.__path__ = [str(INFERNUX_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "Infernux", infernux)

    spec = importlib.util.spec_from_file_location(
        "Infernux.ai_runtime",
        AI_RUNTIME_DIR / "__init__.py",
        submodule_search_locations=[str(AI_RUNTIME_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime", module)

    spec.loader.exec_module(module)

    assert hasattr(module, "begin_experiment")
    assert hasattr(module, "edit_transaction")
    assert hasattr(module, "get_world_snapshot")
    assert hasattr(module, "expire_control_signals")
    assert hasattr(module, "legacy")
