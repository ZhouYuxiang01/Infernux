from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
MCP_URL = "http://127.0.0.1:9713/mcp"
SCENE_ASSET_PATH = "Assets/Scenes/AIBilliard.scene"

TARGET_POSITION = [3.7, 0.75, 3.3]
WAYPOINTS = [
    ("AgentDemo_Waypoint_X", [2.4, 0.2, 0.0], [0.35, 0.35, 0.35]),
    ("AgentDemo_Waypoint_Z", [3.7, 0.2, 1.8], [0.35, 0.35, 0.35]),
    ("AgentDemo_Target", TARGET_POSITION, [0.5, 0.5, 0.5]),
]
CONTROL_PHASES = [
    ("drive +X toward the first waypoint", {"move_x": 1.0, "move_y": 0.0}, 0.45),
    ("drive +Z toward the target lane", {"move_x": 0.0, "move_y": 1.0}, 0.42),
]


def _log(message: str) -> None:
    print(f"[agent-demo] {message}", flush=True)


def _engine_child() -> None:
    if str(PYTHON_ROOT) not in sys.path:
        sys.path.insert(0, str(PYTHON_ROOT))

    from Infernux.engine import release_engine

    release_engine(str(PROJECT_ROOT))


def _python_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PYTHON_ROOT) + (os.pathsep + existing if existing else "")
    return env


def _launch_engine() -> subprocess.Popen:
    args = [sys.executable, str(Path(__file__).resolve()), "--engine-child"]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        args,
        cwd=str(REPO_ROOT),
        env=_python_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _endpoint_alive(timeout_seconds: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(MCP_URL, timeout=timeout_seconds) as response:
            return 200 <= int(response.status) < 500
    except urllib.error.HTTPError as exc:
        return 200 <= int(exc.code) < 500
    except Exception:
        return False


def _wait_http_endpoint(timeout_seconds: float = 90.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _endpoint_alive(timeout_seconds=1.0):
            return
        time.sleep(0.5)
    raise TimeoutError(f"MCP endpoint did not become reachable: {MCP_URL}")


def _unwrap_tool_payload(name: str, result) -> Any:
    payload = getattr(result, "data", None)
    if payload is None:
        payload = getattr(result, "structured_content", None)
    if isinstance(payload, dict) and "ok" in payload:
        if not payload.get("ok"):
            raise RuntimeError(f"{name} failed: {payload.get('error')}")
        return payload.get("data", {})
    return payload


async def _call(client, name: str, arguments: dict[str, Any] | None = None, timeout: float = 45.0) -> Any:
    result = await client.call_tool(name, arguments or {}, timeout=timeout)
    return _unwrap_tool_payload(name, result)


async def _wait_health(client, timeout_seconds: float = 90.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_health: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last_health = await _call(client, "mcp_health", {}, timeout=10.0)
            if last_health.get("main_thread_queue_ready"):
                return last_health
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Editor MCP main thread queue was not ready: {last_health}")


async def _wait_scene(client, scene_name: str, timeout_seconds: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status: dict[str, Any] = {}
    while time.time() < deadline:
        last_status = await _call(client, "scene_status_tool" if False else "scene_status", {}, timeout=10.0)
        current_name = str(
            last_status.get("scene", "")
            or last_status.get("name", "")
            or last_status.get("scene_name", "")
        )
        loading = bool(last_status.get("loading", False))
        if scene_name in current_name and not loading:
            return last_status
        await asyncio.sleep(0.25)
    raise TimeoutError(f"Scene {scene_name!r} did not finish loading: {last_status}")


async def _find_one(client, query: dict[str, Any], label: str) -> dict[str, Any]:
    result = await _call(client, "scene_query_objects", {"query": query, "limit": 5, "include_components": True})
    matches = result.get("matches", [])
    if not matches:
        raise RuntimeError(f"Could not find {label}: query={query}")
    return matches[0]


async def _create_marker(client, name: str, position: list[float], scale: list[float]) -> int:
    created = await _call(
        client,
        "hierarchy_create_object",
        {"kind": "primitive.sphere", "name": name, "select": False},
    )
    object_id = int(created.get("id") or created.get("object_id"))
    operations = [{"op": "move_entity", "entity_id": object_id, "position": position}]
    preview = await _call(client, "runtime_edit_transaction_preview", {"operations": operations, "mode": "edit"})
    if not preview.get("ok"):
        raise RuntimeError(f"marker transaction preview failed for {name}: {preview.get('message')}")
    committed = await _call(client, "runtime_edit_transaction_commit", {"operations": operations, "mode": "edit"})
    if not committed.get("ok"):
        raise RuntimeError(f"marker transaction commit failed for {name}: {committed.get('message')}")
    await _call(client, "transform_set", {"object_id": object_id, "values": {"local_scale": scale}})
    return object_id


def _position(state: dict[str, Any]) -> list[float]:
    return [float(v) for v in state["transform"]["position"]]


def _xz_distance(a: list[float], b: list[float]) -> float:
    dx = float(a[0]) - float(b[0])
    dz = float(a[2]) - float(b[2])
    return (dx * dx + dz * dz) ** 0.5


async def _run_agent(auto_close: bool) -> None:
    from fastmcp import Client

    async with Client(MCP_URL, timeout=60.0) as client:
        try:
            health = await _wait_health(client)
            _log(f"MCP ready at {health.get('endpoint')}")

            await _call(client, "scene_open", {"path": SCENE_ASSET_PATH}, timeout=20.0)
            await _wait_scene(client, "AIBilliard")
            _log(f"opened {SCENE_ASSET_PATH}")

            schema = await _call(client, "runtime_get_component_schema", {"component_type": "Transform"})
            _log(f"schema query: Transform fields={len(schema.get('fields', []))}")

            ball = await _find_one(client, {"name_exact": "Ball"}, "Ball")
            ball_id = int(ball["id"])
            await _call(client, "scene_clear_generated", {"name_prefix": "AgentDemo_"}, timeout=20.0)
            world_before_edit = await _call(
                client,
                "runtime_get_world_snapshot",
                {"include_components": True, "include_fields": True},
                timeout=20.0,
            )

            marker_ids = []
            for name, position, scale in WAYPOINTS:
                marker_ids.append(await _create_marker(client, name, position, scale))
            await _call(
                client,
                "camera_frame_targets",
                {"target_ids": [ball_id, *marker_ids], "padding": 0.25, "mode": "move_or_zoom"},
                timeout=20.0,
            )
            await _call(client, "scene_save", {}, timeout=20.0)
            _log(f"created {len(marker_ids)} agent markers, framed the camera, and saved the scene for Play Mode")

            world_after_edit = await _call(
                client,
                "runtime_get_world_snapshot",
                {"include_components": True, "include_fields": True},
                timeout=20.0,
            )
            edit_diff = await _call(
                client,
                "runtime_diff_world_snapshots",
                {"before": world_before_edit, "after": world_after_edit},
                timeout=20.0,
            )

            play = await _call(client, "editor_play", {}, timeout=20.0)
            _log(f"play requested: accepted={play.get('accepted')} state={play.get('state')}")
            await _call(
                client,
                "runtime_wait",
                {"play_state": "playing", "deferred_idle": True, "timeout_seconds": 30.0},
                timeout=35.0,
            )

            before_ball = await _call(client, "runtime_get_object_state", {"object_id": ball_id}, timeout=10.0)
            start_position = _position(before_ball)
            _log(f"ball start position={start_position}")
            await _call(client, "runtime_experiment_begin", {"mode": "run", "require_health_check": True}, timeout=10.0)
            await _call(client, "runtime_experiment_mark_health_check", {}, timeout=10.0)

            for label, axes, seconds in CONTROL_PHASES:
                duration_ms = int(seconds * 1000) + 150
                await _call(
                    client,
                    "runtime_submit_control",
                    {"channel_id": 0, "axes": axes, "buttons": {}, "duration_ms": duration_ms, "agent_id": 0},
                    timeout=10.0,
                )
                await _call(
                    client,
                    "runtime_run_for",
                    {"seconds": seconds, "stop_on_error": False, "poll_interval": 0.1},
                    timeout=max(10.0, seconds + 5.0),
                )
                state = await _call(client, "runtime_get_object_state", {"object_id": ball_id}, timeout=10.0)
                _log(f"{label}: axes={axes} position={_position(state)}")

            await _call(client, "runtime_clear_control", {"channel_id": 0}, timeout=10.0)
            guard_status = await _call(client, "runtime_experiment_status", {}, timeout=10.0)
            await _call(client, "runtime_experiment_end", {}, timeout=10.0)

            after_ball = await _call(client, "runtime_get_object_state", {"object_id": ball_id}, timeout=10.0)
            end_position = _position(after_ball)
            movement = _xz_distance(start_position, end_position)
            target_distance = _xz_distance(end_position, TARGET_POSITION)

            assertions = await _call(
                client,
                "runtime_assert",
                {"assertions": [{"kind": "object_exists", "object_id": ball_id}]},
                timeout=10.0,
            )
            errors = await _call(client, "runtime_read_errors", {"include_warnings": False, "limit": 20}, timeout=10.0)

            _log(f"ball end position={end_position}")
            _log(f"movement_xz={movement:.3f} target_distance_xz={target_distance:.3f}")
            _log(
                "world edit diff: "
                f"entities_added={len(edit_diff.get('entities_added', []))} "
                f"entities_removed={len(edit_diff.get('entities_removed', []))} "
                f"entities_changed={len(edit_diff.get('entities_changed', []))}"
            )
            _log(f"runtime assertions passed={assertions.get('passed')}")
            _log(f"experiment guard paths={guard_status.get('control_paths', [])}")
            _log(f"runtime errors={len(errors.get('errors', []))} script_errors={len(errors.get('script_errors', []))}")

            if movement < 0.25:
                raise RuntimeError(f"Ball did not move enough through ControlSignal: movement_xz={movement:.3f}")
        finally:
            await _call(client, "runtime_clear_control", {"channel_id": 0}, timeout=10.0)
            try:
                await _call(client, "runtime_experiment_end", {}, timeout=10.0)
            except Exception:
                pass
        if auto_close:
            try:
                await _call(client, "editor_stop", {}, timeout=20.0)
            except Exception as exc:
                _log(f"editor_stop failed during cleanup: {exc}")
            try:
                await _call(client, "runtime_wait", {"play_state": "edit", "timeout_seconds": 20.0}, timeout=25.0)
                await _call(client, "scene_clear_generated", {"name_prefix": "AgentDemo_"}, timeout=20.0)
                await _call(client, "scene_save", {}, timeout=20.0)
            except Exception as exc:
                _log(f"generated marker cleanup failed: {exc}")


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an external-agent world operation demo against Infernux MCP.")
    parser.add_argument("--engine-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--use-existing", action="store_true", help="Use an already running editor MCP endpoint.")
    parser.add_argument("--auto-close", action="store_true", help="Stop the launched editor process after the demo.")
    args = parser.parse_args()

    if args.engine_child:
        _engine_child()
        return 0

    process: subprocess.Popen | None = None
    reused_existing = False
    if args.use_existing or _endpoint_alive(timeout_seconds=0.5):
        reused_existing = True
        _log("using existing MCP endpoint")
    else:
        process = _launch_engine()
        _log(f"launched engine process pid={process.pid}")

    try:
        _wait_http_endpoint()
        asyncio.run(_run_agent(auto_close=args.auto_close))
    finally:
        if args.auto_close and not reused_existing:
            _stop_process(process)

    if process is not None and not args.auto_close:
        _log(f"demo complete; engine window remains open in pid={process.pid}")
    else:
        _log("demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
