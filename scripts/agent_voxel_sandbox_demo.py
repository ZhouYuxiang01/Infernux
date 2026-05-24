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

try:
    from scripts.voxel_sandbox_demo_support import CONTROL_ROUTE, WORLD_LAYOUT, iter_layout_blocks
except ModuleNotFoundError:
    from voxel_sandbox_demo_support import CONTROL_ROUTE, WORLD_LAYOUT, iter_layout_blocks


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
MCP_URL = "http://127.0.0.1:9713/mcp"
SCENE_ASSET_PATH = "Assets/Scenes/VoxelSandbox.scene"
SCRIPT_ASSET_PATH = "Assets/Scripts/VoxelSandboxController.py"
CAPTURE_OUTPUT_PATH = PROJECT_ROOT / "Logs" / "agent_observations" / "voxel_sandbox_render_target.png"

TEXTURES = {
    "grass": "Assets/ThirdParty/VoxelSandbox/grass.png",
    "dirt": "Assets/ThirdParty/VoxelSandbox/dirt.png",
    "stone": "Assets/ThirdParty/VoxelSandbox/stone.png",
    "wood": "Assets/ThirdParty/VoxelSandbox/wood.png",
    "leaf": "Assets/ThirdParty/VoxelSandbox/leaf.png",
    "water": "Assets/ThirdParty/VoxelSandbox/water.png",
}


def _log(message: str) -> None:
    print(f"[voxel-sandbox-demo] {message}", flush=True)


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


async def _resolve_textures(client) -> dict[str, str]:
    await _call(client, "asset_refresh", {}, timeout=45.0)
    resolved: dict[str, str] = {}
    for key, path in TEXTURES.items():
        result = await _call(client, "asset_resolve", {"path": path}, timeout=15.0)
        guid = str(result.get("guid") or "")
        if not guid:
            raise RuntimeError(f"asset_resolve did not return a guid for {path}")
        resolved[key] = guid
    return resolved


async def _create_scene(client) -> dict[str, Any]:
    texture_guids = await _resolve_textures(client)
    status = await _call(client, "scene_status", {}, timeout=10.0)
    if status.get("dirty"):
        raise RuntimeError("Active scene is dirty. Save or discard it before building VoxelSandbox.")

    await _call(client, "scene_new", {"force": True, "reason": "Build VoxelSandbox agent demo scene"}, timeout=20.0)
    await _call(client, "scene_save", {"path": SCENE_ASSET_PATH}, timeout=30.0)

    root = await _call(
        client,
        "hierarchy_create_object",
        {"kind": "empty", "name": "VoxelSandbox_Root", "select": False},
        timeout=20.0,
    )
    root_id = int(root.get("id") or root.get("object_id"))
    await _call(client, "transform_set", {"object_id": root_id, "values": {"position": [0.0, 0.0, 0.0]}}, timeout=10.0)

    controller = await _call(
        client,
        "hierarchy_create_object",
        {"kind": "empty", "parent_id": root_id, "name": "VoxelSandbox_Controller", "select": False},
        timeout=20.0,
    )
    controller_id = int(controller.get("id") or controller.get("object_id"))
    await _call(
        client,
        "gameobject_add_component",
        {
            "object_id": controller_id,
            "component_type": "VoxelSandboxController",
            "script_path": SCRIPT_ASSET_PATH,
            "fields": {
                "grass_texture_guid": texture_guids["grass"],
                "dirt_texture_guid": texture_guids["dirt"],
                "stone_texture_guid": texture_guids["stone"],
                "wood_texture_guid": texture_guids["wood"],
                "leaf_texture_guid": texture_guids["leaf"],
                "water_texture_guid": texture_guids["water"],
            },
        },
        timeout=20.0,
    )

    camera = await _call(client, "camera_ensure_main", {"name": "VoxelSandbox_Camera", "create_if_missing": True}, timeout=20.0)
    camera_id = int(camera["camera"]["id"])
    await _call(
        client,
        "component_set_field",
        {"object_id": camera_id, "component_type": "Camera", "field": "projection_mode", "value": 0},
        timeout=10.0,
    )
    await _call(
        client,
        "component_set_field",
        {"object_id": camera_id, "component_type": "Camera", "field": "field_of_view", "value": 55.0},
        timeout=10.0,
    )
    await _call(client, "transform_set", {"object_id": camera_id, "values": {"position": [-3.0, 7.0, 7.0]}}, timeout=10.0)
    await _call(client, "camera_look_at", {"camera_id": camera_id, "position": [3.0, 2.0, 3.0]}, timeout=10.0)

    saved = await _call(client, "scene_save", {"path": SCENE_ASSET_PATH}, timeout=30.0)
    return {
        "root_id": root_id,
        "controller_id": controller_id,
        "scene": saved.get("path", SCENE_ASSET_PATH),
        "block_count": sum(1 for _ in iter_layout_blocks(WORLD_LAYOUT)),
        "textures": texture_guids,
    }


async def _find_one(client, query: dict[str, Any], label: str) -> dict[str, Any]:
    result = await _call(client, "scene_query_objects", {"query": query, "limit": 5, "include_components": True}, timeout=20.0)
    matches = result.get("matches", [])
    if not matches:
        raise RuntimeError(f"Could not find {label}: query={query}")
    return matches[0]


async def _controller_fields(client, controller_id: int) -> dict[str, Any]:
    state = await _call(
        client,
        "runtime_get_component_state",
        {"object_id": controller_id, "component_type": "VoxelSandboxController"},
        timeout=10.0,
    )
    return state.get("fields", {})


async def _object_position(client, object_id: int) -> list[float]:
    state = await _call(client, "runtime_get_object_state", {"object_id": object_id}, timeout=10.0)
    return [float(value) for value in state["transform"]["position"]]


def _distance_xz(a: list[float], b: list[float]) -> float:
    dx = float(a[0]) - float(b[0])
    dz = float(a[2]) - float(b[2])
    return (dx * dx + dz * dz) ** 0.5


async def _run_validation(client, ids: dict[str, Any]) -> None:
    controller_id = int(ids["controller_id"])
    await _call(client, "runtime_experiment_begin", {"mode": "run", "require_health_check": True}, timeout=10.0)
    await _call(client, "mcp_health", {}, timeout=10.0)
    await _call(client, "runtime_experiment_mark_health_check", {}, timeout=10.0)

    play = await _call(client, "editor_play", {}, timeout=20.0)
    _log(f"play requested: accepted={play.get('accepted')} state={play.get('state')}")
    await _call(
        client,
        "runtime_wait",
        {"play_state": "playing", "deferred_idle": True, "timeout_seconds": 30.0},
        timeout=35.0,
    )

    player = await _find_one(client, {"name_exact": "VoxelSandbox_Player"}, "runtime player")
    player_id = int(player["id"])
    start_position = await _object_position(client, player_id)
    start_fields = await _controller_fields(client, controller_id)
    _log(f"player start={start_position} fields={start_fields}")

    for phase in CONTROL_ROUTE:
        await _call(
            client,
            "runtime_submit_control",
            {
                "channel_id": 0,
                "axes": dict(phase.axes),
                "buttons": dict(phase.buttons),
                "duration_ms": int(phase.seconds * 1000) + 120,
                "agent_id": 0,
            },
            timeout=10.0,
        )
        await _call(
            client,
            "runtime_run_for",
            {"seconds": phase.seconds, "stop_on_error": False, "poll_interval": 0.1},
            timeout=max(10.0, phase.seconds + 5.0),
        )
        fields = await _controller_fields(client, controller_id)
        _log(
            f"{phase.label}: player={fields.get('player_cell')} selected={fields.get('selected_cell')} "
            f"type={fields.get('selected_block_type')} removed={fields.get('blocks_removed')} "
            f"placed={fields.get('blocks_placed')} status={fields.get('status')}"
        )
        if str(fields.get("status", "")).startswith("setup_error"):
            raise AssertionError(f"VoxelSandbox setup failed during route: {fields}")

    await _call(client, "runtime_clear_control", {"channel_id": 0}, timeout=10.0)
    guard_status = await _call(client, "runtime_experiment_status", {}, timeout=10.0)
    await _call(client, "runtime_experiment_end", {}, timeout=10.0)

    final_position = await _object_position(client, player_id)
    final_fields = await _controller_fields(client, controller_id)
    movement = _distance_xz(start_position, final_position)
    removed = int(final_fields.get("blocks_removed", 0) or 0)
    placed = int(final_fields.get("blocks_placed", 0) or 0)
    selected_cell = str(final_fields.get("selected_cell", "") or "")
    status = str(final_fields.get("status", "") or "")
    if movement < 0.25:
        raise AssertionError(f"Player did not move enough through ControlSignal: movement={movement:.3f}")
    if removed < 1:
        raise AssertionError(f"No block was mined: {final_fields}")
    if placed < 1:
        raise AssertionError(f"No block was placed: {final_fields}")
    if not selected_cell:
        raise AssertionError(f"No selected cell reported: {final_fields}")
    if status != "running":
        raise AssertionError(f"Unexpected controller status: {final_fields}")

    capture = await _call(
        client,
        "runtime_capture_game_render_target",
        {"output_path": str(CAPTURE_OUTPUT_PATH)},
        timeout=20.0,
    )
    if not capture.get("available"):
        raise AssertionError(f"Game render target capture was unavailable: {capture}")
    errors = await _call(client, "runtime_read_errors", {"limit": 20}, timeout=10.0)
    if errors.get("count", 0):
        raise AssertionError(f"Runtime reported errors: {errors}")

    _log(
        "validation passed: "
        f"movement={movement:.2f}, removed={removed}, placed={placed}, "
        f"player={final_fields.get('player_cell')}, selected={selected_cell}, "
        f"guard_paths={guard_status.get('control_paths')}, capture={capture.get('image_path')}"
    )


async def _run_agent(auto_close: bool) -> None:
    from fastmcp import Client

    async with Client(MCP_URL, timeout=60.0) as client:
        health = await _wait_health(client)
        _log(f"MCP ready at {health.get('endpoint')}")
        ids = await _create_scene(client)
        _log(
            f"created VoxelSandbox scene={ids['scene']} blocks={ids['block_count']} "
            f"textures={len(ids['textures'])}"
        )
        await _run_validation(client, ids)
        if auto_close:
            await _call(client, "editor_stop", {}, timeout=20.0)
            await _call(
                client,
                "runtime_wait",
                {"play_state": "stopped", "deferred_idle": True, "timeout_seconds": 30.0},
                timeout=35.0,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate the VoxelSandbox agent demo.")
    parser.add_argument("--engine-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--auto-close", action="store_true", help="Stop Play Mode after validation.")
    args = parser.parse_args()

    if args.engine_child:
        _engine_child()
        return 0

    process = None
    if _endpoint_alive(timeout_seconds=1.0):
        _log(f"using existing engine MCP endpoint: {MCP_URL}")
    else:
        process = _launch_engine()
        _log(f"launched engine process pid={process.pid}")
        _wait_http_endpoint()

    try:
        asyncio.run(_run_agent(auto_close=args.auto_close))
        return 0
    finally:
        if process is not None and args.auto_close:
            process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
