"""Runtime observation and validation MCP tools."""

from __future__ import annotations

import time
from typing import Any

from Infernux.mcp.threading import MainThreadCommandQueue
from Infernux.mcp.tools.common import (
    fail,
    find_game_object,
    ok,
    register_tool_metadata,
    serialize_component,
    serialize_value,
)


def register_runtime_tools(mcp) -> None:
    _register_metadata()

    @mcp.tool(name="runtime_wait")
    def runtime_wait(
        play_state: str = "",
        deferred_idle: bool = True,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.1,
    ) -> dict:
        """Wait until editor runtime conditions are met."""
        deadline = time.time() + max(float(timeout_seconds), 0.01)
        desired_state = str(play_state or "").lower()
        last_state: dict[str, Any] = {}
        while time.time() < deadline:
            last_state = _run_on_main("runtime.wait.state", _editor_state)
            state_ok = not desired_state or last_state.get("play_state") == desired_state
            idle_ok = not deferred_idle or not last_state.get("deferred_task_busy")
            if state_ok and idle_ok:
                return ok({"ready": True, "state": last_state, "elapsed_seconds": max(0.0, timeout_seconds - (deadline - time.time()))})
            time.sleep(max(float(poll_interval), 0.01))
        return fail(
            "error.timeout",
            "Timed out waiting for runtime condition.",
            hint="Use editor_get_state, console_read, or runtime_read_errors to diagnose why the condition did not become true.",
            explain={"tool": "runtime_wait", "summary": "Wait for Play Mode/deferred task conditions."},
        ) | {"data": {"ready": False, "state": last_state}}

    @mcp.tool(name="runtime_run_for")
    def runtime_run_for(seconds: float = 1.0, stop_on_error: bool = True, poll_interval: float = 0.25) -> dict:
        """Let Play Mode run for a duration while polling for errors."""
        duration = max(float(seconds), 0.0)
        deadline = time.time() + duration
        samples = []
        errors: list[dict[str, Any]] = []
        while time.time() < deadline:
            time.sleep(max(float(poll_interval), 0.01))
            state = _run_on_main("runtime.run_for.state", _editor_state)
            samples.append(state)
            errors = _run_on_main("runtime.run_for.errors", _read_errors)["errors"]
            if stop_on_error and errors:
                break
        return ok({
            "elapsed_seconds": duration,
            "stopped_on_error": bool(stop_on_error and errors),
            "samples": samples[-10:],
            "errors": errors,
        })

    @mcp.tool(name="runtime_get_object_state")
    def runtime_get_object_state(object_id: int) -> dict:
        """Read runtime GameObject transform and component summary."""

        def _read():
            obj = find_game_object(object_id)
            trans = obj.transform
            return {
                "id": int(obj.id),
                "name": str(obj.name),
                "active": bool(getattr(obj, "active", True)),
                "transform": {
                    "position": _vec(trans.position),
                    "euler_angles": _vec(trans.euler_angles),
                    "local_position": _vec(trans.local_position),
                    "local_euler_angles": _vec(trans.local_euler_angles),
                    "local_scale": _vec(trans.local_scale),
                },
                "components": _components(obj),
                "parent_id": int(getattr(obj.get_parent(), "id", 0) or 0),
                "child_count": int(obj.get_child_count()),
            }

        return ok(_run_on_main("runtime_get_object_state", _read))

    @mcp.tool(name="runtime_get_component_state")
    def runtime_get_component_state(object_id: int, component_type: str, ordinal: int = 0) -> dict:
        """Read a component snapshot at runtime."""

        def _read():
            obj = find_game_object(object_id)
            comp = _find_component(obj, component_type, int(ordinal))
            if comp is None:
                raise FileNotFoundError(f"Component '{component_type}' was not found on GameObject {object_id}.")
            data = serialize_component(comp)
            fields = {}
            try:
                from Infernux.components.serialized_field import get_serialized_fields
                for name in get_serialized_fields(type(comp)):
                    try:
                        fields[name] = serialize_value(getattr(comp, name))
                    except Exception:
                        pass
            except Exception:
                pass
            return {"object_id": int(obj.id), "component": data, "fields": fields}

        try:
            return ok(_run_on_main("runtime_get_component_state", _read))
        except FileNotFoundError as exc:
            return fail("error.not_found", str(exc), hint="Use component_list_on_object or gameobject_get first.")

    @mcp.tool(name="runtime_get_world_snapshot")
    def runtime_get_world_snapshot(include_components: bool = True, include_fields: bool = True) -> dict:
        """Read the active scene as a structured AI runtime world snapshot."""

        def _read():
            from Infernux.ai_runtime.world_model import get_world_snapshot

            return get_world_snapshot(
                include_components=bool(include_components),
                include_fields=bool(include_fields),
            ).to_dict()

        return ok(_run_on_main("runtime_get_world_snapshot", _read))

    @mcp.tool(name="runtime_get_component_schema")
    def runtime_get_component_schema(component_type: str) -> dict:
        """Read readable and core-writable field metadata for a component type."""

        def _read():
            from Infernux.ai_runtime.world_model import get_component_schema

            schema = get_component_schema(component_type)
            return schema.to_dict() if schema is not None else None

        data = _run_on_main("runtime_get_component_schema", _read)
        if data is None:
            return fail(
                "error.not_found",
                f"Component schema '{component_type}' was not found.",
                hint="Use runtime_get_world_snapshot or component_describe_type to inspect component names.",
            )
        return ok(data)

    @mcp.tool(name="runtime_submit_control")
    def runtime_submit_control(
        channel_id: int = 0,
        axes: dict[str, Any] | None = None,
        buttons: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        timestamp_ms: int | None = None,
        agent_id: int | None = None,
    ) -> dict:
        """Submit a generic AI runtime ControlSignal."""

        def _submit():
            from Infernux.ai_runtime import ControlSignal, get_control_state, submit_control

            signal = ControlSignal(
                channel_id=int(channel_id),
                axes=dict(axes or {}),
                buttons=dict(buttons or {}),
                duration_ms=duration_ms,
                timestamp_ms=timestamp_ms,
                agent_id=agent_id,
            )
            submit_control(signal)
            state = get_control_state(int(channel_id)) or signal
            return {"signal": _control_signal_to_dict(state)}

        return ok(_run_on_main("runtime_submit_control", _submit))

    @mcp.tool(name="runtime_clear_control")
    def runtime_clear_control(channel_id: int | None = None) -> dict:
        """Clear one ControlSignal channel, or all channels when channel_id is null."""

        def _clear():
            from Infernux.ai_runtime import clear_control

            clear_control(None if channel_id is None else int(channel_id))
            return {"cleared_channel_id": None if channel_id is None else int(channel_id)}

        return ok(_run_on_main("runtime_clear_control", _clear))

    @mcp.tool(name="runtime_diff_world_snapshots")
    def runtime_diff_world_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict:
        """Compare two world snapshots returned by runtime_get_world_snapshot."""
        if not isinstance(before, dict) or not isinstance(after, dict):
            return fail(
                "error.invalid_argument",
                "before and after must be world snapshot dictionaries.",
                hint="Call runtime_get_world_snapshot before and after an operation, then pass both data payloads here.",
            )
        from Infernux.ai_runtime.world_model import diff_world_snapshots

        return ok(diff_world_snapshots(before, after).to_dict())

    @mcp.tool(name="runtime_read_errors")
    def runtime_read_errors(include_warnings: bool = False, limit: int = 100) -> dict:
        """Read console errors and script loader errors."""
        return ok(_run_on_main("runtime_read_errors", lambda: _read_errors(include_warnings=include_warnings, limit=limit)))

    @mcp.tool(name="runtime_assert")
    def runtime_assert(assertions: list[dict[str, Any]]) -> dict:
        """Evaluate simple runtime assertions."""

        def _assert():
            results = []
            for item in assertions or []:
                kind = str(item.get("kind", ""))
                passed = False
                message = ""
                if kind == "play_state":
                    state = _editor_state().get("play_state")
                    expected = str(item.get("equals", "")).lower()
                    passed = state == expected
                    message = f"play_state is {state!r}, expected {expected!r}"
                elif kind == "object_exists":
                    obj = _try_find_object(int(item.get("object_id", 0)))
                    passed = obj is not None
                    message = f"object_id {item.get('object_id')} exists={passed}"
                elif kind == "component_exists":
                    obj = _try_find_object(int(item.get("object_id", 0)))
                    comp = _find_component(obj, str(item.get("component_type", "")), 0) if obj else None
                    passed = comp is not None
                    message = f"component {item.get('component_type')} exists={passed}"
                elif kind == "no_errors":
                    errors = _read_errors(include_warnings=False).get("errors", [])
                    passed = len(errors) == 0
                    message = f"{len(errors)} error(s)"
                else:
                    message = f"Unknown assertion kind: {kind}"
                results.append({"assertion": item, "passed": passed, "message": message})
            return {"passed": all(r["passed"] for r in results), "results": results}

        return ok(_run_on_main("runtime_assert", _assert))


def _run_on_main(name: str, fn):
    return MainThreadCommandQueue.instance().run_sync(name, fn, timeout_ms=30000)


def _editor_state() -> dict[str, Any]:
    from Infernux.engine.deferred_task import DeferredTaskRunner
    from Infernux.engine.play_mode import PlayModeManager
    from Infernux.engine.scene_manager import SceneFileManager
    from Infernux.engine.ui.selection_manager import SelectionManager

    pmm = PlayModeManager.instance()
    sfm = SceneFileManager.instance()
    sel = SelectionManager.instance()
    runner = DeferredTaskRunner.instance()
    return {
        "play_state": getattr(getattr(pmm, "state", None), "name", "edit").lower() if pmm else "edit",
        "deferred_task_busy": bool(getattr(runner, "is_busy", False)),
        "selected_ids": sel.get_ids() if sel else [],
        "scene_dirty": bool(sfm.is_dirty) if sfm else False,
        "is_prefab_mode": bool(getattr(sfm, "is_prefab_mode", False)) if sfm else False,
    }


def _read_errors(include_warnings: bool = False, limit: int = 100) -> dict[str, Any]:
    from Infernux.debug import DebugConsole
    from Infernux.components.script_loader import get_script_errors

    allowed = {"ERROR", "FATAL"}
    if include_warnings:
        allowed.add("WARN")
        allowed.add("WARNING")
    entries = []
    for entry in DebugConsole.instance().get_entries()[-max(int(limit), 1):]:
        level = getattr(entry.log_type, "name", str(entry.log_type)).upper()
        if level not in allowed:
            continue
        entries.append({
            "time": entry.get_formatted_time(),
            "level": level,
            "message": entry.message,
            "source_file": entry.source_file,
            "source_line": entry.source_line,
        })
    script_errors = [
        {"path": path, "traceback": tb}
        for path, tb in get_script_errors().items()
    ]
    return {"errors": entries, "script_errors": script_errors}


def _components(obj) -> list[dict[str, Any]]:
    items = []
    seen = set()
    for getter in ("get_components", "get_py_components"):
        try:
            for comp in getattr(obj, getter)() or []:
                data = serialize_component(comp)
                key = (data.get("type"), data.get("component_id"))
                if key in seen:
                    continue
                seen.add(key)
                items.append(data)
        except Exception:
            pass
    return items


def _find_component(obj, component_type: str, ordinal: int = 0):
    if obj is None:
        return None
    matches = []
    for getter in ("get_components", "get_py_components"):
        try:
            for comp in getattr(obj, getter)() or []:
                if getattr(comp, "type_name", type(comp).__name__) == component_type or type(comp).__name__ == component_type:
                    matches.append(comp)
        except Exception:
            pass
    return matches[ordinal] if 0 <= ordinal < len(matches) else None


def _try_find_object(object_id: int):
    try:
        return find_game_object(object_id)
    except Exception:
        return None


def _vec(value) -> list[float]:
    return [float(value.x), float(value.y), float(value.z)]


def _control_signal_to_dict(signal) -> dict[str, Any]:
    return {
        "channel_id": int(getattr(signal, "channel_id", 0)),
        "axes": dict(getattr(signal, "axes", {}) or {}),
        "buttons": dict(getattr(signal, "buttons", {}) or {}),
        "duration_ms": getattr(signal, "duration_ms", None),
        "timestamp_ms": getattr(signal, "timestamp_ms", None),
        "agent_id": getattr(signal, "agent_id", None),
    }


def _register_metadata() -> None:
    for name, summary in {
        "runtime_wait": "Wait for Play Mode/deferred task state.",
        "runtime_run_for": "Let runtime advance while polling errors.",
        "runtime_get_object_state": "Read object transform and component state at runtime.",
        "runtime_get_component_state": "Read one component state at runtime.",
        "runtime_get_world_snapshot": "Read a structured AI runtime world snapshot.",
        "runtime_get_component_schema": "Read component field metadata for world snapshots and edits.",
        "runtime_submit_control": "Submit a generic ControlSignal through the AI runtime.",
        "runtime_clear_control": "Clear one or all AI runtime control channels.",
        "runtime_diff_world_snapshots": "Compare two AI runtime world snapshots.",
        "runtime_read_errors": "Read console and script loader errors.",
        "runtime_assert": "Evaluate simple runtime assertions.",
    }.items():
        register_tool_metadata(name, summary=summary, next_suggested_tools=["runtime_read_errors", "console_read"])
