from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from math import hypot


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
SCENE_PATH = PROJECT_ROOT / "Assets" / "Scenes" / "MinimalPlayable.scene"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Infernux.ai_runtime import ActionType, clear_actions, enter_play_mode, pause, send_action, step
from Infernux.debug import Debug
from Infernux.engine import release_engine
from Infernux.engine.play_mode import PlayModeManager
from Infernux.engine.scene_manager import SceneFileManager
from Infernux.engine.ui.closable_panel import ClosablePanel
from Infernux.engine.ui.editor_services import EditorServices
from Infernux.input import Input
from Infernux.lib import SceneManager as NativeSceneManager


def _log(message: str) -> None:
    Debug.log(message)
    print(message, flush=True)


def _wait_for(condition, timeout: float, poll: float = 0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False


def _find_player_snapshot():
    try:
        from Infernux.ai_runtime import get_player_snapshot

        return get_player_snapshot()
    except Exception:
        return None


def _find_scene_object(scene, name: str):
    try:
        for obj in scene.get_all_objects():
            if getattr(obj, "name", "") == name:
                return obj
    except Exception:
        return None
    return None


def _read_vec3(value):
    if value is None:
        return None
    try:
        return (float(value.x), float(value.y), float(value.z))
    except Exception:
        try:
            return tuple(float(v) for v in value)
        except Exception:
            return None


def _read_transform_vec3(transform, names: tuple[str, ...]):
    for name in names:
        try:
            value = getattr(transform, name)
        except Exception:
            continue
        vec = _read_vec3(value)
        if vec is not None:
            return vec
    return None


def _estimate_ground_target(ground_obj, player_pos):
    ground_t = getattr(ground_obj, "transform", None)
    if ground_t is None:
        return None, None

    ground_pos = _read_transform_vec3(ground_t, ("position", "local_position"))
    ground_scale = _read_transform_vec3(ground_t, ("lossy_scale", "local_scale", "scale"))
    if ground_pos is None or ground_scale is None:
        return None, None

    gx, gy, gz = ground_pos
    sx, sy, sz = ground_scale
    half_x = abs(sx) * 0.5
    half_z = abs(sz) * 0.5

    margin = max(0.75, min(2.0, min(half_x, half_z) * 0.2))
    target = (gx + half_x - margin, gy + 1.0, gz + half_z - margin)

    if player_pos is not None:
        px, py, pz = player_pos
        # Pick the quadrant that is farthest from the current start point so
        # the movement is visually obvious without leaving the platform.
        candidates = [
            (gx + half_x - margin, py, gz + half_z - margin),
            (gx - half_x + margin, py, gz + half_z - margin),
            (gx + half_x - margin, py, gz - half_z + margin),
            (gx - half_x + margin, py, gz - half_z + margin),
        ]
        target = max(candidates, key=lambda pos: hypot(pos[0] - px, pos[2] - pz))

    x_min, x_max = gx - half_x, gx + half_x
    z_min, z_max = gz - half_z, gz + half_z
    return target, {
        "ground_pos": ground_pos,
        "ground_scale": ground_scale,
        "x_range": (x_min, x_max),
        "z_range": (z_min, z_max),
        "margin": margin,
    }


def _ensure_minimal_scene_loaded() -> bool:
    scene_mgr = SceneFileManager.instance()
    if scene_mgr is None:
        return False

    scene = NativeSceneManager.instance().get_active_scene()
    if scene is not None:
        try:
            player = _find_scene_object(scene, "Player")
            ground = _find_scene_object(scene, "Ground")
            return player is not None and ground is not None
        except Exception:
            pass

    try:
        return bool(scene_mgr.open_scene(str(SCENE_PATH)))
    except Exception:
        return False


def _focus_game_view() -> None:
    services = EditorServices.instance()
    engine = services.engine if services else None
    if engine is None:
        return

    for _ in range(60):
        try:
            ClosablePanel.focus_panel_by_id("game_view")
            engine.select_docked_window("game_view")
        except Exception:
            pass

        if Input.is_game_focused():
            return
        time.sleep(0.05)


def _drive_ai_takeover() -> None:
    if not _wait_for(lambda: EditorServices.instance().engine is not None, 30.0):
        _log("AI demo: editor engine never became ready")
        return

    if not _ensure_minimal_scene_loaded():
        _log("AI demo: failed to confirm MinimalPlayable.scene")
        return

    _focus_game_view()
    Input.set_game_focused(True)

    if not enter_play_mode():
        _log("AI demo: enter_play_mode() failed")
        return

    if not _wait_for(lambda: PlayModeManager.instance() is not None and PlayModeManager.instance().is_playing, 20.0):
        _log("AI demo: play mode never became active")
        return

    _focus_game_view()
    Input.set_game_focused(True)
    if not _wait_for(Input.is_game_focused, 10.0):
        _log("AI demo: Game View never reported focus")
        return

    scene = NativeSceneManager.instance().get_active_scene()
    if scene is None:
        _log("AI demo: no active scene after play mode")
        return

    ground = _find_scene_object(scene, "Ground")
    player = _find_scene_object(scene, "Player")
    if ground is None or player is None:
        _log("AI demo: Ground or Player not found")
        return

    before = _find_player_snapshot()
    start_pos = _read_vec3(getattr(before, "position", None))
    player_pos = start_pos

    ground_target, ground_info = _estimate_ground_target(ground, player_pos)
    if ground_target is None or ground_info is None:
        _log("AI demo: failed to estimate Ground target")
        return

    _log(f"AI demo start position: {start_pos}")
    _log(
        "AI demo ground: "
        f"pos={ground_info['ground_pos']} scale={ground_info['ground_scale']} "
        f"x_range={ground_info['x_range']} z_range={ground_info['z_range']}"
    )
    _log(f"AI demo target: {ground_target}")

    if not pause():
        _log("AI demo: pause() failed")
        return

    threshold = 0.35
    batch_steps = 1
    max_batches = 130

    for batch_index in range(max_batches):
        snapshot = _find_player_snapshot()
        player_pos = _read_vec3(getattr(snapshot, "position", None)) or player_pos
        if player_pos is None:
            _log("AI demo: player snapshot unavailable")
            break

        dx = ground_target[0] - player_pos[0]
        dz = ground_target[2] - player_pos[2]
        distance = hypot(dx, dz)
        if distance <= threshold:
            break

        move_x = 0.0 if abs(dx) < 0.05 else (1.0 if dx > 0 else -1.0)
        move_y = 0.0 if abs(dz) < 0.05 else (1.0 if dz > 0 else -1.0)

        # Prefer the dominant axis to keep the motion legible.
        if abs(dx) > abs(dz) * 1.25:
            move_y = 0.0
        elif abs(dz) > abs(dx) * 1.25:
            move_x = 0.0

        Input.set_game_focused(True)
        send_action(ActionType.Move, x=move_x, y=move_y)
        stepped = step(batch_steps)
        snapshot = _find_player_snapshot()
        player_pos = _read_vec3(getattr(snapshot, "position", None)) or player_pos

        _log(
            f"AI demo batch {batch_index + 1}: pos={player_pos} "
            f"delta=({dx:.3f}, {dz:.3f}) move=({move_x}, {move_y}) "
            f"distance={distance:.3f} stepped={stepped}"
        )
        if (batch_index + 1) % 10 == 0:
            time.sleep(0.20)
        else:
            time.sleep(0.03)

    clear_actions()
    _log("AI demo: input cleared")

    time.sleep(0.75)
    stopped = _find_player_snapshot()
    _log(f"AI demo stop position: {getattr(stopped, 'position', None)}")
    _log("AI demo: movement complete, leaving play mode running for inspection")

    while True:
        time.sleep(1.0)


def main() -> None:
    worker = threading.Thread(target=_drive_ai_takeover, name="ai-takeover-demo", daemon=True)
    worker.start()
    release_engine(str(PROJECT_ROOT))


if __name__ == "__main__":
    main()
