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
SCENE_ASSET_PATH = "Assets/Scenes/PelletChase.scene"
SCRIPT_ASSET_PATH = "Assets/Scripts/PelletChaseController.py"

LAYOUT = (
    "#########",
    "#P....#.#",
    "#.###.#.#",
    "#...#...#",
    "#.#...#.#",
    "#..#..G.#",
    "#########",
)

SPRITES = {
    "player": "Assets/ThirdParty/OpenGameArt/pacman-tiles/pac.png",
    "ghost": "Assets/ThirdParty/OpenGameArt/pacman-tiles/ghost1.png",
    "wall": "Assets/ThirdParty/OpenGameArt/pacman-tiles/block1.png",
    "pellet": "Assets/ThirdParty/OpenGameArt/pacman-tiles/dot.png",
}

CONTROL_PHASES = [
    ("collect the upper corridor", {"move_x": -1.0, "move_y": 0.0}, 1.0),
    ("turn down into the maze", {"move_x": 0.0, "move_y": -1.0}, 0.55),
    ("press against the center wall", {"move_x": 1.0, "move_y": 0.0}, 0.45),
]


def _log(message: str) -> None:
    print(f"[pellet-demo] {message}", flush=True)


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


def _find_cells() -> tuple[tuple[int, int], tuple[int, int], list[tuple[int, int]], list[tuple[int, int]]]:
    player = (-1, -1)
    ghost = (-1, -1)
    walls: list[tuple[int, int]] = []
    pellets: list[tuple[int, int]] = []
    for row, line in enumerate(LAYOUT):
        for col, char in enumerate(line):
            if char == "#":
                walls.append((row, col))
            elif char == "P":
                player = (row, col)
            elif char == "G":
                ghost = (row, col)
            elif char == ".":
                pellets.append((row, col))
    if player == (-1, -1) or ghost == (-1, -1):
        raise RuntimeError("LAYOUT must include P and G cells.")
    return player, ghost, walls, pellets


def _position(state: dict[str, Any]) -> list[float]:
    return [float(v) for v in state["transform"]["position"]]


def _distance_xy(a: list[float], b: list[float]) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return (dx * dx + dy * dy) ** 0.5


def _cell_is_wall(cell: str) -> bool:
    if "," not in str(cell or ""):
        return True
    row_s, col_s = str(cell or "").split(",", 1)
    row = int(row_s)
    col = int(col_s)
    return row < 0 or row >= len(LAYOUT) or col < 0 or col >= len(LAYOUT[row]) or LAYOUT[row][col] == "#"


async def _find_one(client, query: dict[str, Any], label: str) -> dict[str, Any]:
    result = await _call(client, "scene_query_objects", {"query": query, "limit": 5, "include_components": True}, timeout=20.0)
    matches = result.get("matches", [])
    if not matches:
        raise RuntimeError(f"Could not find {label}: query={query}")
    return matches[0]


async def _resolve_sprites(client) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, path in SPRITES.items():
        try:
            result = await _call(client, "asset_resolve", {"path": path}, timeout=15.0)
            guid = str(result.get("guid") or "")
            if guid:
                resolved[key] = guid
        except Exception as exc:
            _log(f"sprite resolve skipped for {path}: {exc}")
    return resolved


async def _create_scene(client) -> dict[str, Any]:
    player_cell, ghost_cell, walls, pellets = _find_cells()
    await _call(client, "asset_refresh", {}, timeout=45.0)
    sprite_guids = await _resolve_sprites(client)

    status = await _call(client, "scene_status", {}, timeout=10.0)
    if status.get("dirty"):
        raise RuntimeError("Active scene is dirty. Save or discard it before running the Pellet Chase builder.")
    await _call(client, "scene_new", {"force": True, "reason": "Build Pellet Chase agent demo scene"}, timeout=20.0)
    await _call(client, "scene_save", {"path": SCENE_ASSET_PATH}, timeout=30.0)

    root = await _call(
        client,
        "hierarchy_create_object",
        {"kind": "empty", "name": "PelletChase_Root", "select": False},
        timeout=20.0,
    )
    root_id = int(root.get("id") or root.get("object_id"))
    await _call(client, "transform_set", {"object_id": root_id, "values": {"position": [0.0, 0.0, 0.0]}}, timeout=10.0)

    controller = await _call(
        client,
        "hierarchy_create_object",
        {"kind": "empty", "parent_id": root_id, "name": "PelletChase_Controller", "select": False},
        timeout=20.0,
    )
    controller_id = int(controller.get("id") or controller.get("object_id"))
    await _call(
        client,
        "gameobject_add_component",
        {
            "object_id": controller_id,
            "component_type": "PelletChaseController",
            "script_path": SCRIPT_ASSET_PATH,
            "fields": {
                "wall_sprite_guid": sprite_guids.get("wall", ""),
                "pellet_sprite_guid": sprite_guids.get("pellet", ""),
                "player_sprite_guid": sprite_guids.get("player", ""),
                "ghost_sprite_guid": sprite_guids.get("ghost", ""),
            },
        },
        timeout=20.0,
    )

    camera = await _call(client, "camera_ensure_main", {"name": "PelletChase_Camera", "create_if_missing": True}, timeout=20.0)
    camera_id = int(camera["camera"]["id"])
    await _call(
        client,
        "component_set_field",
        {"object_id": camera_id, "component_type": "Camera", "field": "projection_mode", "value": 1},
        timeout=10.0,
    )
    await _call(
        client,
        "component_set_field",
        {"object_id": camera_id, "component_type": "Camera", "field": "orthographic_size", "value": 5.2},
        timeout=10.0,
    )
    await _call(client, "transform_set", {"object_id": camera_id, "values": {"position": [0.0, 0.0, 18.0]}}, timeout=10.0)
    await _call(client, "camera_look_at", {"camera_id": camera_id, "position": [0.0, 0.0, 0.0]}, timeout=10.0)

    saved = await _call(client, "scene_save", {"path": SCENE_ASSET_PATH}, timeout=30.0)
    return {
        "root_id": root_id,
        "controller_id": controller_id,
        "created_objects": 2,
        "pellets": len(pellets),
        "walls": len(walls),
        "player_start": player_cell,
        "ghost_start": ghost_cell,
        "scene": saved.get("path", SCENE_ASSET_PATH),
        "sprites": sprite_guids,
    }


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

    player = await _find_one(client, {"name_exact": "PelletChase_Player"}, "runtime player")
    player_id = int(player["id"])
    before_state = await _call(client, "runtime_get_object_state", {"object_id": player_id}, timeout=10.0)
    before_controller = await _call(
        client,
        "runtime_get_component_state",
        {"object_id": controller_id, "component_type": "PelletChaseController"},
        timeout=10.0,
    )
    start_position = _position(before_state)
    start_score = int(before_controller.get("fields", {}).get("score", 0) or 0)
    _log(f"player start={start_position} score={start_score}")

    for label, axes, seconds in CONTROL_PHASES:
        await _call(
            client,
            "runtime_submit_control",
            {
                "channel_id": 0,
                "axes": axes,
                "buttons": {},
                "duration_ms": int(seconds * 1000) + 120,
                "agent_id": 0,
            },
            timeout=10.0,
        )
        await _call(
            client,
            "runtime_run_for",
            {"seconds": seconds, "stop_on_error": False, "poll_interval": 0.1},
            timeout=max(10.0, seconds + 5.0),
        )
        current = await _call(client, "runtime_get_object_state", {"object_id": player_id}, timeout=10.0)
        fields = (
            await _call(
                client,
                "runtime_get_component_state",
                {"object_id": controller_id, "component_type": "PelletChaseController"},
                timeout=10.0,
            )
        ).get("fields", {})
        _log(f"{label}: axes={axes} pos={_position(current)} score={fields.get('score')} left={fields.get('pellets_remaining')}")

    await _call(client, "runtime_clear_control", {"channel_id": 0}, timeout=10.0)
    guard_status = await _call(client, "runtime_experiment_status", {}, timeout=10.0)
    await _call(client, "runtime_experiment_end", {}, timeout=10.0)

    final_state = await _call(client, "runtime_get_object_state", {"object_id": player_id}, timeout=10.0)
    final_fields = (
        await _call(
            client,
            "runtime_get_component_state",
            {"object_id": controller_id, "component_type": "PelletChaseController"},
            timeout=10.0,
        )
    ).get("fields", {})
    errors = await _call(client, "runtime_read_errors", {"limit": 20}, timeout=10.0)
    end_position = _position(final_state)
    movement = _distance_xy(start_position, end_position)
    score = int(final_fields.get("score", 0) or 0)
    player_cell = str(final_fields.get("player_cell", ""))
    if movement < 1.0:
        raise AssertionError(f"Player did not move enough through ControlSignal: movement={movement:.3f}")
    if score <= start_score:
        raise AssertionError(f"Pellet score did not increase: start={start_score}, final={score}")
    if _cell_is_wall(player_cell):
        raise AssertionError(f"Player ended inside a wall cell after collision test: player_cell={player_cell}")
    if errors.get("count", 0):
        raise AssertionError(f"Runtime reported errors: {errors}")

    _log(
        "validation passed: "
        f"movement={movement:.2f}, score={score}, left={final_fields.get('pellets_remaining')}, cell={player_cell}, "
        f"guard_paths={guard_status.get('control_paths')}"
    )


async def _run_agent(auto_close: bool) -> None:
    from fastmcp import Client

    async with Client(MCP_URL, timeout=60.0) as client:
        health = await _wait_health(client)
        _log(f"MCP ready at {health.get('endpoint')}")
        ids = await _create_scene(client)
        _log(
            f"created {ids['created_objects']} objects, pellets={ids['pellets']}, "
            f"scene={ids['scene']}, sprites={len(ids['sprites'])}"
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
    parser = argparse.ArgumentParser(description="Build and validate the Pellet Chase agent demo.")
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
