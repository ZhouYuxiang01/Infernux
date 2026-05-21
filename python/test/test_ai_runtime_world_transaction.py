from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
AI_RUNTIME_DIR = ROOT / "Infernux" / "ai_runtime"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = [str(AI_RUNTIME_DIR)] if name == "Infernux.ai_runtime" else []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _edit_result(ok: bool, message: str = "", changes=None):
    return SimpleNamespace(ok=ok, message=message, changes=changes or [])


def _load_world_transaction(monkeypatch, world_edit):
    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.world_edit", world_edit)
    spec = importlib.util.spec_from_file_location(
        "Infernux.ai_runtime.world_transaction",
        AI_RUNTIME_DIR / "world_transaction.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "Infernux.ai_runtime.world_transaction", module)
    spec.loader.exec_module(module)
    return module


def _fake_world_edit():
    module = types.ModuleType("Infernux.ai_runtime.world_edit")
    module.move_entity = lambda *args, **kwargs: _edit_result(True)
    module.set_component = lambda *args, **kwargs: _edit_result(True)
    return module


def test_transaction_preview_does_not_mutate(monkeypatch):
    world_edit = _fake_world_edit()
    calls = []
    world_edit.move_entity = lambda entity_id, position, preview=False, mode="auto": (
        calls.append((entity_id, position, preview, mode)) or _edit_result(True, "preview")
    )
    tx_mod = _load_world_transaction(monkeypatch, world_edit)

    tx = tx_mod.edit_transaction(mode="edit")
    tx.move_entity(7, (1.0, 2.0, 3.0))
    result = tx.preview()

    assert result.ok is True
    assert result.preview is True
    assert calls == [(7, (1.0, 2.0, 3.0), True, "edit")]
    assert result.audit_log[0]["operation"] == "move_entity"
    assert result.to_dict()["ok"] is True


def test_transaction_preview_collects_field_changes(monkeypatch):
    world_edit = _fake_world_edit()
    change = {"field_path": "Transform.position", "old_value": [0, 0, 0], "new_value": [1, 2, 3]}
    world_edit.move_entity = lambda *args, **kwargs: _edit_result(True, "preview", [change])
    tx_mod = _load_world_transaction(monkeypatch, world_edit)

    tx = tx_mod.edit_transaction()
    tx.move_entity(7, (1.0, 2.0, 3.0))
    result = tx.preview()

    assert result.changes == (change,)
    assert result.to_dict()["changes"] == [change]


def test_transaction_result_to_dict_projects_native_like_vectors(monkeypatch):
    @dataclass(frozen=True)
    class _Change:
        field_path: str
        old_value: object
        new_value: object

    world_edit = _fake_world_edit()
    old_vec = SimpleNamespace(x=0.0, y=0.0, z=0.0)
    new_vec = SimpleNamespace(x=1.0, y=2.0, z=3.0)
    change = _Change("Transform.position", old_vec, new_vec)
    world_edit.move_entity = lambda *args, **kwargs: _edit_result(True, "preview", [change])
    tx_mod = _load_world_transaction(monkeypatch, world_edit)

    tx = tx_mod.edit_transaction()
    tx.move_entity(7, (1.0, 2.0, 3.0))
    payload = tx.preview().to_dict()

    assert payload["changes"][0]["old_value"] == [0.0, 0.0, 0.0]
    assert payload["changes"][0]["new_value"] == [1.0, 2.0, 3.0]
    json.dumps(payload)


def test_transaction_commit_validates_then_applies(monkeypatch):
    world_edit = _fake_world_edit()
    calls = []
    world_edit.move_entity = lambda entity_id, position, preview=False, mode="auto": (
        calls.append((entity_id, position, preview, mode)) or _edit_result(True, "moved")
    )
    tx_mod = _load_world_transaction(monkeypatch, world_edit)
    monkeypatch.setattr(tx_mod, "_read_current_position", lambda entity_id: (0.0, 0.0, 0.0))

    tx = tx_mod.edit_transaction(mode="runtime")
    tx.move_entity(7, (1.0, 2.0, 3.0))
    result = tx.commit()

    assert result.ok is True
    assert result.committed is True
    assert calls == [
        (7, (1.0, 2.0, 3.0), True, "runtime"),
        (7, (1.0, 2.0, 3.0), False, "runtime"),
    ]


def test_transaction_commit_stops_on_first_failure(monkeypatch):
    world_edit = _fake_world_edit()
    calls = []
    world_edit.move_entity = lambda *args, **kwargs: calls.append(("move", kwargs)) or _edit_result(True, "moved")
    world_edit.set_component = lambda *args, **kwargs: calls.append(("set", kwargs)) or _edit_result(False, "field not allowed")
    tx_mod = _load_world_transaction(monkeypatch, world_edit)
    monkeypatch.setattr(tx_mod, "_read_current_position", lambda entity_id: (0.0, 0.0, 0.0))

    tx = tx_mod.edit_transaction(mode="runtime")
    tx.move_entity(7, (0, 0, 0))
    tx.set_component(7, "unknown", 1)

    result = tx.commit()

    assert result.ok is False
    assert result.message == "field not allowed"
    assert [entry["operation"] for entry in result.audit_log] == ["move_entity", "set_component"]
    assert all(call[1]["preview"] is True for call in calls)


def test_transaction_commit_rolls_back_partial_failure(monkeypatch):
    world_edit = _fake_world_edit()
    positions = {7: (0.0, 0.0, 0.0)}

    def _move(entity_id, position, preview=False, mode="auto"):
        if not preview:
            positions[int(entity_id)] = tuple(position)
        return _edit_result(True, "moved")

    def _set_component(*args, preview=False, **kwargs):
        return _edit_result(preview, "" if preview else "failed during commit")

    world_edit.move_entity = _move
    world_edit.set_component = _set_component
    tx_mod = _load_world_transaction(monkeypatch, world_edit)
    monkeypatch.setattr(tx_mod, "_read_current_position", lambda entity_id: positions[int(entity_id)])

    tx = tx_mod.edit_transaction(mode="edit")
    tx.move_entity(7, (1.0, 2.0, 3.0))
    tx.set_component(7, "mass", 2.0)
    result = tx.commit()

    assert result.ok is False
    assert result.rolled_back is True
    assert positions[7] == (0.0, 0.0, 0.0)


def test_transaction_rollback_restores_committed_move(monkeypatch):
    world_edit = _fake_world_edit()
    positions = {7: (0.0, 0.0, 0.0)}

    def _move(entity_id, position, preview=False, mode="auto"):
        if not preview:
            positions[int(entity_id)] = tuple(position)
        return _edit_result(True, "moved")

    world_edit.move_entity = _move
    tx_mod = _load_world_transaction(monkeypatch, world_edit)
    monkeypatch.setattr(tx_mod, "_read_current_position", lambda entity_id: positions[int(entity_id)])

    tx = tx_mod.edit_transaction(mode="edit")
    tx.move_entity(7, (1.0, 2.0, 3.0))
    committed = tx.commit()
    rolled_back = tx.rollback()

    assert committed.ok is True
    assert rolled_back.ok is True
    assert rolled_back.rolled_back is True
    assert positions[7] == (0.0, 0.0, 0.0)
