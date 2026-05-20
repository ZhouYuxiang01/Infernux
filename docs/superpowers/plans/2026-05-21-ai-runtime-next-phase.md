# AI Runtime Next Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current AI Runtime Core v1 contract-hardening pass into an enforceable, safer agent-operable runtime by adding executable runtime guards, transactional world edits, and a compatibility-preserving legacy API split.

**Architecture:** Keep `Infernux.ai_runtime` as the stable semantics-free core. Add guard and transaction modules that wrap existing primitives instead of replacing them, then expose MCP tools only after Python contract tests define behavior. Move legacy player/action APIs into a compatibility module while keeping root re-exports during the migration window.

**Tech Stack:** Python 3.12 contract tests with `--noconftest`, Python 3.14/native editor integration for live demos, C++17 input backend, pybind11 bindings, FastMCP tool wrappers.

---

## File Structure

- Create `python/Infernux/ai_runtime/experiment_guard.py`
  - Owns executable experiment-session state and guard violations.
- Modify `python/Infernux/ai_runtime/__init__.py`
  - Re-export guard primitives after contract tests define the stable names.
- Modify `python/Infernux/mcp/tools/runtime.py`
  - Add MCP guard tools and route runtime control through guard checks.
- Modify `python/Infernux/mcp/tools/docs.py`
  - Surface guard tools in onboarding, capability groups, and workflows.
- Create `python/test/test_ai_runtime_experiment_guard.py`
  - Native-free guard contract tests.
- Create or extend `python/test/test_mcp_runtime_world_model_tools.py`
  - MCP wrapper tests for guard tools.
- Create `python/Infernux/ai_runtime/world_transaction.py`
  - Owns transaction preview, validation, commit, rollback result, and audit records.
- Modify `python/Infernux/ai_runtime/world_edit.py`
  - Keep existing single-operation API; expose helpers transaction code can use.
- Create `python/test/test_ai_runtime_world_transaction.py`
  - Native-free fake-scene tests for preview, commit, rollback, and audit behavior.
- Create `python/Infernux/ai_runtime/legacy.py`
  - Compatibility home for `ActionType`, `send_action`, `PlayerSnapshot`, `ActivitySummary`, and related player-centric helpers.
- Keep `python/Infernux/ai_runtime/experimental.py` out of this phase.
  - The legacy split is the only namespace change in this plan; world model APIs remain where they are until their stability boundary is reviewed separately.
- Modify `API_Reference.md`, `README.md`, `AGENTS.md`, and `docs/agent/quickstart.md`
  - Document the guard loop, transaction edit loop, and legacy migration path.

---

## Shared Test Helpers

Use these native-free loader helpers in the new test files so contract tests do
not import `_Infernux.pyd`:

```python
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
AI_RUNTIME_DIR = ROOT / "Infernux" / "ai_runtime"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_ai_runtime_module(monkeypatch, module_name: str, file_name: str):
    _ensure_package(monkeypatch, "Infernux")
    package = _ensure_package(monkeypatch, "Infernux.ai_runtime")
    package.__path__ = [str(AI_RUNTIME_DIR)]  # type: ignore[attr-defined]
    spec = importlib.util.spec_from_file_location(module_name, AI_RUNTIME_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _edit_result(ok: bool, message: str = ""):
    return SimpleNamespace(ok=ok, message=message)


def _load_ai_runtime_package(monkeypatch):
    _ensure_package(monkeypatch, "Infernux")
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
```

---

## Track 1: Runtime Experiment Guard

### Task 1: Define Native-Free Guard State

**Files:**
- Create: `python/Infernux/ai_runtime/experiment_guard.py`
- Test: `python/test/test_ai_runtime_experiment_guard.py`

- [ ] **Step 1: Write failing tests for session lifecycle**

```python
def test_begin_status_end_experiment_guard(monkeypatch):
    guard = _load_ai_runtime_module(
        monkeypatch,
        "Infernux.ai_runtime.experiment_guard",
        "experiment_guard.py",
    )

    state = guard.begin_experiment(mode="step", require_health_check=True)

    assert state.active is True
    assert state.mode == "step"
    assert state.require_health_check is True
    assert guard.experiment_status().active is True

    ended = guard.end_experiment()

    assert ended.active is False
    assert guard.experiment_status().active is False
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_experiment_guard.py::test_begin_status_end_experiment_guard -q --noconftest
```

Expected: fails because `experiment_guard.py` does not exist.

- [ ] **Step 3: Implement minimal guard dataclasses**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ExperimentMode = Literal["step", "run"]


class ExperimentGuardViolation(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExperimentGuardState:
    active: bool = False
    mode: str = "step"
    require_health_check: bool = True
    health_checked: bool = False
    control_paths: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()


@dataclass(slots=True)
class _MutableGuardState:
    active: bool = False
    mode: str = "step"
    require_health_check: bool = True
    health_checked: bool = False
    control_paths: set[str] = field(default_factory=set)
    violations: list[str] = field(default_factory=list)


_STATE = _MutableGuardState()


def _snapshot() -> ExperimentGuardState:
    return ExperimentGuardState(
        active=_STATE.active,
        mode=_STATE.mode,
        require_health_check=_STATE.require_health_check,
        health_checked=_STATE.health_checked,
        control_paths=tuple(sorted(_STATE.control_paths)),
        violations=tuple(_STATE.violations),
    )


def begin_experiment(mode: str = "step", require_health_check: bool = True) -> ExperimentGuardState:
    if mode not in {"step", "run"}:
        raise ValueError("mode must be 'step' or 'run'")
    _STATE.active = True
    _STATE.mode = mode
    _STATE.require_health_check = bool(require_health_check)
    _STATE.health_checked = False
    _STATE.control_paths.clear()
    _STATE.violations.clear()
    return _snapshot()


def experiment_status() -> ExperimentGuardState:
    return _snapshot()


def end_experiment() -> ExperimentGuardState:
    _STATE.active = False
    _STATE.control_paths.clear()
    return _snapshot()
```

- [ ] **Step 4: Run the lifecycle test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_experiment_guard.py::test_begin_status_end_experiment_guard -q --noconftest
```

Expected: passes.

### Task 2: Enforce Health Check and Single Control Path

**Files:**
- Modify: `python/Infernux/ai_runtime/experiment_guard.py`
- Test: `python/test/test_ai_runtime_experiment_guard.py`

- [ ] **Step 1: Add tests for guard violations**

```python
def test_guard_requires_health_check_before_control(monkeypatch):
    guard = _load_ai_runtime_module(
        monkeypatch,
        "Infernux.ai_runtime.experiment_guard",
        "experiment_guard.py",
    )
    guard.begin_experiment(mode="run", require_health_check=True)

    with pytest.raises(guard.ExperimentGuardViolation):
        guard.assert_can_use_control_path("control_signal")


def test_guard_blocks_mixed_control_paths(monkeypatch):
    guard = _load_ai_runtime_module(
        monkeypatch,
        "Infernux.ai_runtime.experiment_guard",
        "experiment_guard.py",
    )
    guard.begin_experiment(mode="run", require_health_check=False)

    guard.assert_can_use_control_path("control_signal")

    with pytest.raises(guard.ExperimentGuardViolation):
        guard.assert_can_use_control_path("transform_mutation")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_experiment_guard.py -q --noconftest
```

Expected: fails because marker/check functions do not exist.

- [ ] **Step 3: Implement guard checks**

```python
def mark_health_check() -> ExperimentGuardState:
    _STATE.health_checked = True
    return _snapshot()


def _violate(message: str) -> None:
    _STATE.violations.append(message)
    raise ExperimentGuardViolation(message)


def assert_can_use_control_path(path: str) -> ExperimentGuardState:
    normalized = str(path or "").strip()
    if not normalized:
        _violate("control path is required")
    if _STATE.active and _STATE.require_health_check and not _STATE.health_checked:
        _violate("runtime experiment requires mcp_health before control")
    if _STATE.control_paths and normalized not in _STATE.control_paths:
        existing = ", ".join(sorted(_STATE.control_paths))
        _violate(f"mixed control paths are not allowed: existing={existing}, requested={normalized}")
    _STATE.control_paths.add(normalized)
    return _snapshot()
```

- [ ] **Step 4: Run guard tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_experiment_guard.py -q --noconftest
```

Expected: all guard tests pass.

### Task 3: Expose Guard Through MCP Runtime Tools

**Files:**
- Modify: `python/Infernux/mcp/tools/runtime.py`
- Modify: `python/Infernux/mcp/tools/docs.py`
- Test: `python/test/test_mcp_runtime_world_model_tools.py`

- [ ] **Step 1: Add MCP tests**

```python
def test_runtime_experiment_guard_tools(monkeypatch):
    world_model = types.ModuleType("Infernux.ai_runtime.world_model")
    world_model.get_world_snapshot = lambda **kwargs: _Payload({"entities": []})
    world_model.get_component_schema = lambda name: None
    world_model.diff_world_snapshots = lambda before, after: _Payload({})
    module = _load_runtime_tools(monkeypatch, world_model)
    ai_runtime = sys.modules["Infernux.ai_runtime"]
    states = []

    ai_runtime.begin_experiment = lambda mode="step", require_health_check=True: _Payload({
        "active": True,
        "mode": mode,
        "require_health_check": require_health_check,
    })
    ai_runtime.experiment_status = lambda: _Payload({"active": True, "mode": "run"})
    ai_runtime.end_experiment = lambda: _Payload({"active": False, "mode": "run"})
    ai_runtime.mark_health_check = lambda: states.append("health")

    mcp = _FakeMcp()
    module.register_runtime_tools(mcp)

    assert mcp.tools["runtime_experiment_begin"](mode="run")["ok"] is True
    assert mcp.tools["runtime_experiment_status"]()["ok"] is True
    assert mcp.tools["runtime_experiment_end"]()["data"]["active"] is False
```

- [ ] **Step 2: Run the MCP test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_mcp_runtime_world_model_tools.py::test_runtime_experiment_guard_tools -q --noconftest
```

Expected: fails because MCP guard tools are not registered.

- [ ] **Step 3: Add MCP tool wrappers**

Add a local payload helper near `_control_signal_to_dict`:

```python
from dataclasses import asdict, is_dataclass


def _runtime_payload_to_dict(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return value
```

```python
@mcp.tool(name="runtime_experiment_begin")
def runtime_experiment_begin(mode: str = "step", require_health_check: bool = True) -> dict:
    def _begin():
        from Infernux.ai_runtime import begin_experiment
        return _runtime_payload_to_dict(begin_experiment(mode=mode, require_health_check=require_health_check))
    return ok(_run_on_main("runtime_experiment_begin", _begin))


@mcp.tool(name="runtime_experiment_status")
def runtime_experiment_status() -> dict:
    def _status():
        from Infernux.ai_runtime import experiment_status
        return _runtime_payload_to_dict(experiment_status())
    return ok(_run_on_main("runtime_experiment_status", _status))


@mcp.tool(name="runtime_experiment_end")
def runtime_experiment_end() -> dict:
    def _end():
        from Infernux.ai_runtime import end_experiment
        return _runtime_payload_to_dict(end_experiment())
    return ok(_run_on_main("runtime_experiment_end", _end))
```

- [ ] **Step 4: Route `runtime_submit_control` through guard**

Add before `submit_control(signal)`:

```python
from Infernux.ai_runtime import assert_can_use_control_path

assert_can_use_control_path("control_signal")
```

- [ ] **Step 5: Run MCP and guard tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_experiment_guard.py python\test\test_mcp_runtime_world_model_tools.py -q --noconftest
```

Expected: passes.

---

## Track 2: World Edit Transaction System

### Task 4: Define Transaction Result and Preview

**Files:**
- Create: `python/Infernux/ai_runtime/world_transaction.py`
- Test: `python/test/test_ai_runtime_world_transaction.py`

- [ ] **Step 1: Add tests for preview-only transactions**

```python
def test_transaction_preview_does_not_mutate(monkeypatch):
    _load_ai_runtime_module(monkeypatch, "Infernux.ai_runtime.world_edit", "world_edit.py")
    tx_mod = _load_ai_runtime_module(
        monkeypatch,
        "Infernux.ai_runtime.world_transaction",
        "world_transaction.py",
    )
    calls = []
    monkeypatch.setattr(tx_mod.world_edit, "move_entity", lambda entity_id, position, preview=False, mode="auto": calls.append((entity_id, position, preview, mode)) or _edit_result(True))

    tx = tx_mod.edit_transaction(mode="edit")
    tx.move_entity(7, (1.0, 2.0, 3.0))
    result = tx.preview()

    assert result.ok is True
    assert calls == [(7, (1.0, 2.0, 3.0), True, "edit")]
    assert result.audit_log[0]["operation"] == "move_entity"
```

- [ ] **Step 2: Run preview test to verify it fails**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py::test_transaction_preview_does_not_mutate -q --noconftest
```

Expected: fails because `world_transaction.py` does not exist.

- [ ] **Step 3: Implement minimal transaction preview**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import world_edit


@dataclass(frozen=True, slots=True)
class TransactionResult:
    ok: bool
    message: str = ""
    audit_log: tuple[dict[str, Any], ...] = ()


@dataclass(slots=True)
class _Operation:
    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)


class WorldEditTransaction:
    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self._operations: list[_Operation] = []

    def move_entity(self, entity_id: int | str, position: Any) -> "WorldEditTransaction":
        self._operations.append(_Operation("move_entity", (entity_id, position)))
        return self

    def set_component(self, entity_id: int | str, key: str, value: Any) -> "WorldEditTransaction":
        self._operations.append(_Operation("set_component", (entity_id, key, value)))
        return self

    def preview(self) -> TransactionResult:
        return self._apply(preview=True)

    def _apply(self, preview: bool) -> TransactionResult:
        audit: list[dict[str, Any]] = []
        for op in self._operations:
            result = _dispatch(op, mode=self.mode, preview=preview)
            audit.append({"operation": op.name, "ok": bool(getattr(result, "ok", False)), "message": str(getattr(result, "message", ""))})
            if not getattr(result, "ok", False):
                return TransactionResult(False, str(getattr(result, "message", "operation failed")), tuple(audit))
        return TransactionResult(True, "", tuple(audit))


def _dispatch(op: _Operation, *, mode: str, preview: bool):
    if op.name == "move_entity":
        return world_edit.move_entity(*op.args, preview=preview, mode=mode)
    if op.name == "set_component":
        return world_edit.set_component(*op.args, preview=preview, mode=mode)
    raise ValueError(f"unknown transaction operation: {op.name}")


def edit_transaction(mode: str = "auto") -> WorldEditTransaction:
    return WorldEditTransaction(mode=mode)
```

- [ ] **Step 4: Run transaction preview test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py::test_transaction_preview_does_not_mutate -q --noconftest
```

Expected: passes.

### Task 5: Commit and Audit Log

**Files:**
- Modify: `python/Infernux/ai_runtime/world_transaction.py`
- Test: `python/test/test_ai_runtime_world_transaction.py`

- [ ] **Step 1: Add commit failure test**

```python
def test_transaction_commit_stops_on_first_failure(monkeypatch):
    _load_ai_runtime_module(monkeypatch, "Infernux.ai_runtime.world_edit", "world_edit.py")
    tx_mod = _load_ai_runtime_module(
        monkeypatch,
        "Infernux.ai_runtime.world_transaction",
        "world_transaction.py",
    )
    results = [_edit_result(True, "moved"), _edit_result(False, "field not allowed")]
    monkeypatch.setattr(tx_mod.world_edit, "move_entity", lambda *args, **kwargs: results.pop(0))
    monkeypatch.setattr(tx_mod.world_edit, "set_component", lambda *args, **kwargs: results.pop(0))

    tx = tx_mod.edit_transaction(mode="runtime")
    tx.move_entity(7, (0, 0, 0))
    tx.set_component(7, "unknown", 1)

    result = tx.commit()

    assert result.ok is False
    assert result.message == "field not allowed"
    assert [entry["operation"] for entry in result.audit_log] == ["move_entity", "set_component"]
```

- [ ] **Step 2: Run the failing commit test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py::test_transaction_commit_stops_on_first_failure -q --noconftest
```

Expected: fails because `commit()` does not exist.

- [ ] **Step 3: Implement commit**

```python
def commit(self) -> TransactionResult:
    preview = self.preview()
    if not preview.ok:
        return preview
    return self._apply(preview=False)
```

- [ ] **Step 4: Run transaction tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py -q --noconftest
```

Expected: passes.

### Task 6: Add Best-Effort Rollback for Existing Primitive Edits

**Files:**
- Modify: `python/Infernux/ai_runtime/world_transaction.py`
- Test: `python/test/test_ai_runtime_world_transaction.py`

- [ ] **Step 1: Add rollback tests for captured move operations**

```python
def test_transaction_rollback_restores_committed_move(monkeypatch):
    _load_ai_runtime_module(monkeypatch, "Infernux.ai_runtime.world_edit", "world_edit.py")
    tx_mod = _load_ai_runtime_module(
        monkeypatch,
        "Infernux.ai_runtime.world_transaction",
        "world_transaction.py",
    )
    positions = {7: (0.0, 0.0, 0.0)}

    monkeypatch.setattr(tx_mod, "_read_current_position", lambda entity_id: positions[int(entity_id)])

    def _move(entity_id, position, preview=False, mode="auto"):
        if not preview:
            positions[int(entity_id)] = tuple(position)
        return _edit_result(True, "moved")

    monkeypatch.setattr(tx_mod.world_edit, "move_entity", _move)

    tx = tx_mod.edit_transaction(mode="edit")
    tx.move_entity(7, (1.0, 2.0, 3.0))
    committed = tx.commit()
    rolled_back = tx.rollback()

    assert committed.ok is True
    assert rolled_back.ok is True
    assert positions[7] == (0.0, 0.0, 0.0)
```

- [ ] **Step 2: Run rollback test to verify it fails**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py::test_transaction_rollback_restores_committed_move -q --noconftest
```

Expected: fails because `rollback()` and captured inverse operations do not exist.

- [ ] **Step 3: Capture inverse operations before commit**

```python
def _inverse_for(op: _Operation) -> _Operation | None:
    if op.name == "move_entity":
        current = _read_current_position(op.args[0])
        if current is None:
            return None
        return _Operation("move_entity", (op.args[0], current))
    if op.name == "set_component":
        current = _read_current_component_field(op.args[0], op.args[1])
        if current is None:
            return None
        return _Operation("set_component", (op.args[0], op.args[1], current))
    return None
```

- [ ] **Step 4: Implement rollback**

```python
def rollback(self) -> TransactionResult:
    if not self._rollback_operations:
        return TransactionResult(True, "nothing to rollback", ())
    audit: list[dict[str, Any]] = []
    for op in reversed(self._rollback_operations):
        result = _dispatch(op, mode=self.mode, preview=False)
        audit.append({"operation": op.name, "ok": bool(getattr(result, "ok", False)), "message": str(getattr(result, "message", ""))})
        if not getattr(result, "ok", False):
            return TransactionResult(False, str(getattr(result, "message", "rollback failed")), tuple(audit))
    self._rollback_operations.clear()
    return TransactionResult(True, "", tuple(audit))
```

- [ ] **Step 5: Run transaction tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py -q --noconftest
```

Expected: passes.

### Task 7: Add MCP Transaction Preview/Commit

**Files:**
- Modify: `python/Infernux/mcp/tools/runtime.py`
- Modify: `python/Infernux/mcp/tools/docs.py`
- Test: `python/test/test_mcp_runtime_world_model_tools.py`

- [ ] **Step 1: Define JSON operation shape in tests**

```python
ops = [
    {"op": "move_entity", "entity_id": 7, "position": [1, 2, 3]},
    {"op": "set_component", "entity_id": 7, "key": "mass", "value": 2.0},
]
```

- [ ] **Step 2: Add tests for `runtime_edit_transaction_preview` and `runtime_edit_transaction_commit`**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_mcp_runtime_world_model_tools.py::test_runtime_edit_transaction_tools -q --noconftest
```

Expected: fails until MCP tools exist.

- [ ] **Step 3: Implement MCP operation builder**

```python
def _build_transaction(operations: list[dict[str, Any]], mode: str):
    from Infernux.ai_runtime import edit_transaction

    tx = edit_transaction(mode=mode)
    for op in operations:
        name = str(op.get("op", ""))
        if name == "move_entity":
            tx.move_entity(op.get("entity_id"), op.get("position"))
        elif name == "set_component":
            tx.set_component(op.get("entity_id"), str(op.get("key", "")), op.get("value"))
        else:
            raise ValueError(f"unknown transaction op: {name}")
    return tx
```

- [ ] **Step 4: Run MCP transaction tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_world_transaction.py python\test\test_mcp_runtime_world_model_tools.py -q --noconftest
```

Expected: passes.

---

## Track 3: Legacy API Compatibility Migration

### Task 8: Add `ai_runtime.legacy` Without Breaking Root Imports

**Files:**
- Create: `python/Infernux/ai_runtime/legacy.py`
- Modify: `python/Infernux/ai_runtime/__init__.py`
- Test: `python/test/test_ai_runtime_legacy_namespace.py`

- [ ] **Step 1: Add compatibility tests**

```python
def test_legacy_namespace_exports_player_and_action_apis(monkeypatch):
    legacy = _load_ai_runtime_module(monkeypatch, "Infernux.ai_runtime.legacy", "legacy.py")

    assert hasattr(legacy, "ActionType")
    assert hasattr(legacy, "send_action")
    assert hasattr(legacy, "PlayerSnapshot")
    assert hasattr(legacy, "get_player_snapshot")


def test_root_reexports_legacy_symbols_during_migration(monkeypatch):
    runtime = _load_ai_runtime_package(monkeypatch)

    assert runtime.send_action is runtime.legacy.send_action
    assert runtime.PlayerSnapshot is runtime.legacy.PlayerSnapshot
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_legacy_namespace.py -q --noconftest
```

Expected: fails because `legacy.py` does not exist.

- [ ] **Step 3: Implement `legacy.py` as a compatibility facade**

```python
from __future__ import annotations

from .input_api import ActionType, clear_actions, send_action
from .observation_api import ActivitySummary, PlayerSnapshot, get_activity_summary, get_player_snapshot

__all__ = [
    "ActionType",
    "ActivitySummary",
    "PlayerSnapshot",
    "clear_actions",
    "get_activity_summary",
    "get_player_snapshot",
    "send_action",
]
```

- [ ] **Step 4: Update root package imports**

```python
from . import legacy
from .legacy import ActionType, ActivitySummary, PlayerSnapshot, clear_actions, get_activity_summary, get_player_snapshot, send_action
```

- [ ] **Step 5: Run legacy tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_legacy_namespace.py python\test\test_ai_runtime_import_contract.py -q --noconftest
```

Expected: passes.

### Task 9: Document Stable, Experimental, and Legacy Namespaces

**Files:**
- Modify: `API_Reference.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Test: docs grep commands

- [ ] **Step 1: Add API reference namespace table**

```markdown
| Namespace | Status | Use |
| --- | --- | --- |
| `Infernux.ai_runtime` | stable migration surface | Semantics-free APIs plus temporary root legacy re-exports. |
| `Infernux.ai_runtime.legacy` | transitional | Player/action convenience APIs kept for compatibility. |
| `Infernux.ai_runtime.experimental` | optional | Experimental APIs if they need a named import boundary. |
```

- [ ] **Step 2: Add README migration rule**

```markdown
New agent-facing code should import semantics-free primitives from
`Infernux.ai_runtime`. Player-centric helpers should be imported from
`Infernux.ai_runtime.legacy` during the migration window.
```

- [ ] **Step 3: Verify docs mention the migration path**

Run:

```powershell
rg -n "ai_runtime\.legacy|stable migration surface|Player-centric helpers" README.md API_Reference.md AGENTS.md
```

Expected: all three docs mention the migration boundary.

### Task 10: Add Deprecation Timeline Without Removing Compatibility

**Files:**
- Modify: `API_Reference.md`
- Modify: `README.md`
- Test: `python/test/test_ai_runtime_input_api.py`

- [ ] **Step 1: Add a v1.x/v2.0 migration statement**

```markdown
Root re-exports of legacy player/action APIs remain available through v1.x.
The v2.0 target is to remove them from the root namespace after adapters and
examples import from `Infernux.ai_runtime.legacy`.
```

- [ ] **Step 2: Run existing deprecation behavior tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_input_api.py -q --noconftest
```

Expected: tests pass and existing `send_action` deprecation warnings remain.

---

## Final Verification

Run after each completed track:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_ai_runtime_experiment_guard.py python\test\test_ai_runtime_world_transaction.py python\test\test_ai_runtime_legacy_namespace.py python\test\test_mcp_runtime_world_model_tools.py python\test\test_ai_runtime_import_contract.py -q --noconftest
git diff --check
```

Run before publishing native-facing changes:

```powershell
cmake --build --preset release
```

Run editor integration after Track 1 or Track 2 changes touch MCP runtime behavior:

```powershell
$env:PYTHONPATH="$PWD\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_world_operation_demo.py --auto-close
```

---

## Review Checklist

- Runtime guard starts as native-free Python contract before MCP wiring.
- Guard checks do not block normal editor use unless an experiment session is active.
- Transaction v1 wraps existing `move_entity` and `set_component`; it does not invent broad arbitrary component mutation.
- Transaction preview uses existing `preview=True` paths and reports audit records.
- Legacy namespace migration keeps root imports compatible through v1.x.
- Documentation names the engine/agent boundary and avoids presenting legacy player/action APIs as new Core API.
