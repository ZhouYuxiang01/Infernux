from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from . import world_edit


@dataclass(frozen=True, slots=True)
class TransactionResult:
    ok: bool
    message: str = ""
    changes: tuple[Any, ...] = ()
    audit_log: tuple[dict[str, Any], ...] = ()
    preview: bool = False
    committed: bool = False
    rolled_back: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "changes": [_change_to_dict(change) for change in self.changes],
            "audit_log": list(self.audit_log),
            "preview": self.preview,
            "committed": self.committed,
            "rolled_back": self.rolled_back,
        }


@dataclass(slots=True)
class _Operation:
    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)


class WorldEditTransaction:
    def __init__(self, mode: str = "auto"):
        self.mode = str(mode or "auto")
        self._operations: list[_Operation] = []
        self._rollback_operations: list[_Operation] = []

    def __enter__(self) -> "WorldEditTransaction":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def move_entity(self, entity_id: int | str, position: Any) -> "WorldEditTransaction":
        self._operations.append(_Operation("move_entity", (entity_id, position)))
        return self

    def set_component(self, entity_id: int | str, key: str, value: Any) -> "WorldEditTransaction":
        self._operations.append(_Operation("set_component", (entity_id, key, value)))
        return self

    def validate(self) -> TransactionResult:
        return self.preview()

    def preview(self) -> TransactionResult:
        return self._apply(preview=True)

    def commit(self) -> TransactionResult:
        validation = self.preview()
        if not validation.ok:
            return validation

        audit: list[dict[str, Any]] = []
        changes: list[Any] = []
        self._rollback_operations.clear()
        for op in self._operations:
            inverse = _inverse_for(op)
            result = _dispatch(op, mode=self.mode, preview=False)
            audit.append(_audit_entry(op, result))
            changes.extend(_result_changes(result))
            if not _result_ok(result):
                rollback = self.rollback()
                message = _result_message(result) or "operation failed"
                if not rollback.ok:
                    message = f"{message}; rollback failed: {rollback.message}"
                return TransactionResult(
                    ok=False,
                    message=message,
                    changes=tuple(changes) + tuple(rollback.changes),
                    audit_log=tuple(audit) + tuple(rollback.audit_log),
                    committed=False,
                    rolled_back=rollback.ok,
                )
            if inverse is not None:
                self._rollback_operations.append(inverse)
        return TransactionResult(ok=True, changes=tuple(changes), audit_log=tuple(audit), committed=True)

    def rollback(self) -> TransactionResult:
        if not self._rollback_operations:
            return TransactionResult(True, "nothing to rollback", (), rolled_back=True)

        audit: list[dict[str, Any]] = []
        changes: list[Any] = []
        for op in reversed(self._rollback_operations):
            result = _dispatch(op, mode=self.mode, preview=False)
            audit.append(_audit_entry(op, result))
            changes.extend(_result_changes(result))
            if not _result_ok(result):
                return TransactionResult(
                    ok=False,
                    message=_result_message(result) or "rollback failed",
                    changes=tuple(changes),
                    audit_log=tuple(audit),
                    rolled_back=False,
                )
        self._rollback_operations.clear()
        return TransactionResult(ok=True, changes=tuple(changes), audit_log=tuple(audit), rolled_back=True)

    def _apply(self, preview: bool) -> TransactionResult:
        audit: list[dict[str, Any]] = []
        changes: list[Any] = []
        for op in self._operations:
            result = _dispatch(op, mode=self.mode, preview=preview)
            audit.append(_audit_entry(op, result))
            changes.extend(_result_changes(result))
            if not _result_ok(result):
                return TransactionResult(
                    ok=False,
                    message=_result_message(result) or "operation failed",
                    changes=tuple(changes),
                    audit_log=tuple(audit),
                    preview=preview,
                )
        return TransactionResult(ok=True, changes=tuple(changes), audit_log=tuple(audit), preview=preview)


def _result_ok(result: Any) -> bool:
    return bool(getattr(result, "ok", False))


def _result_message(result: Any) -> str:
    return str(getattr(result, "message", "") or "")


def _result_changes(result: Any) -> tuple[Any, ...]:
    try:
        return tuple(getattr(result, "changes", ()) or ())
    except Exception:
        return ()


def _change_to_dict(change: Any) -> Any:
    if hasattr(change, "to_dict"):
        return change.to_dict()
    if is_dataclass(change):
        return asdict(change)
    if isinstance(change, dict):
        return dict(change)
    return change


def _audit_entry(op: _Operation, result: Any) -> dict[str, Any]:
    return {
        "operation": op.name,
        "ok": _result_ok(result),
        "message": _result_message(result),
        "changes": [_change_to_dict(change) for change in _result_changes(result)],
    }


def _dispatch(op: _Operation, *, mode: str, preview: bool):
    if op.name == "move_entity":
        return world_edit.move_entity(*op.args, preview=preview, mode=mode)
    if op.name == "set_component":
        return world_edit.set_component(*op.args, preview=preview, mode=mode)
    raise ValueError(f"unknown transaction operation: {op.name}")


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


def _read_current_position(entity_id: int | str) -> Any | None:
    obj = _get_scene_object(entity_id)
    if obj is None:
        return None
    try:
        transform = obj.get_component("Transform")
    except Exception:
        transform = getattr(obj, "transform", None)
    if transform is None:
        return None
    try:
        return getattr(transform, "position", None)
    except Exception:
        return None


def _read_current_component_field(entity_id: int | str, key: str) -> Any | None:
    obj = _get_scene_object(entity_id)
    if obj is None:
        return None
    component_name = None
    resolver = getattr(world_edit, "_get_allowed_component_name", None)
    if callable(resolver):
        try:
            component_name = resolver(key)
        except Exception:
            component_name = None
    if component_name is None:
        return None
    try:
        component = obj.get_component(component_name)
    except Exception:
        return None
    if component is None:
        return None
    try:
        return getattr(component, key)
    except Exception:
        return None


def _get_scene_object(entity_id: int | str) -> Any | None:
    getter = getattr(world_edit, "_get_scene_object", None)
    if not callable(getter):
        return None
    try:
        return getter(entity_id)
    except Exception:
        return None


def edit_transaction(mode: str = "auto") -> WorldEditTransaction:
    return WorldEditTransaction(mode=mode)


__all__ = [
    "TransactionResult",
    "WorldEditTransaction",
    "edit_transaction",
]
