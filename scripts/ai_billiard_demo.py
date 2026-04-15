from __future__ import annotations

import sys
import threading
import time
from math import sqrt
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
SCENE_PATH = PROJECT_ROOT / "Assets" / "Scenes" / "AIBilliard.scene"
SCRIPT_ROOT = PROJECT_ROOT / "Assets" / "Scripts"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from Infernux.ai_runtime import ActionType, clear_actions, enter_play_mode, send_action
from Infernux.ai_runtime.observation_api import get_player_snapshot, get_recent_events
from Infernux.debug import Debug
from Infernux.engine import release_engine
from Infernux.engine.play_mode import PlayModeManager
from Infernux.engine.scene_manager import SceneFileManager
from Infernux.engine.ui.closable_panel import ClosablePanel
from Infernux.engine.ui.editor_services import EditorServices
from Infernux.input import Input
from Infernux.lib import SceneManager as NativeSceneManager
from Infernux.lib import Vector3


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


def _find_named_object(scene, name: str):
    try:
        return scene.find(name)
    except Exception:
        pass
    try:
        for obj in scene.get_all_objects():
            if getattr(obj, "name", "") == name:
                return obj
    except Exception:
        return None
    return None


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


def _load_scene() -> bool:
    sfm = SceneFileManager.instance()
    if sfm is None:
        return False
    return bool(sfm.open_scene(str(SCENE_PATH)))


def _scene_is_loaded() -> bool:
    sfm = SceneFileManager.instance()
    if sfm is None:
        return False
    if str(getattr(sfm, "current_scene_path", "") or "") != str(SCENE_PATH):
        return False
    scene = NativeSceneManager.instance().get_active_scene()
    if scene is None:
        return False
    try:
        return all(_find_named_object(scene, name) is not None for name in ("Floor", "Wall_North", "Wall_South", "Wall_East", "Wall_West", "Ball"))
    except Exception:
        return False


def _find_ball_sensor(ball_obj):
    try:
        for comp in ball_obj.get_py_components() or []:
            if type(comp).__name__ == "BallCollisionSensor":
                return comp
    except Exception:
        return None
    return None


def _normalize_xz(vec: Vector3) -> Vector3:
    length = sqrt(float(vec.x) * float(vec.x) + float(vec.z) * float(vec.z))
    if length <= 1e-6:
        return Vector3(0.0, 0.0, 0.0)
    return Vector3(float(vec.x) / length, 0.0, float(vec.z) / length)


def _reflect_direction(direction: Vector3, normal: Vector3) -> Vector3:
    d = _normalize_xz(direction)
    n = _normalize_xz(normal)
    if abs(n.x) < 1e-6 and abs(n.z) < 1e-6:
        return d
    dot = d.x * n.x + d.z * n.z
    reflected = Vector3(
        d.x - 2.0 * dot * n.x,
        0.0,
        d.z - 2.0 * dot * n.z,
    )
    return _normalize_xz(reflected)


def _extract_collision_from_events():
    recent = get_recent_events(250)
    for event in reversed(recent):
        payload = event.get("payload") or {}
        event_type = str(event.get("type") or "").lower()
        if "collision" not in event_type:
            continue
        normal = payload.get("contact_normal") or payload.get("normal")
        point = payload.get("contact_point") or payload.get("point")
        other = payload.get("other_name") or payload.get("game_object_name") or payload.get("target_name")
        return {
            "source": "event_stream",
            "type": event_type,
            "other_name": other,
            "normal": normal,
            "point": point,
        }
    return None


def _drive_demo() -> None:
    if not _wait_for(lambda: EditorServices.instance().engine is not None, 30.0):
        _log("AIBilliard: editor engine never became ready")
        return

    if not _load_scene():
        _log(f"AIBilliard: failed to open {SCENE_PATH}")
        return

    if not _wait_for(_scene_is_loaded, 20.0):
        sfm = SceneFileManager.instance()
        current_path = getattr(sfm, "current_scene_path", None) if sfm else None
        _log(f"AIBilliard: scene never finished loading (current_scene_path={current_path})")
        return

    _focus_game_view()
    Input.set_game_focused(True)

    if not enter_play_mode():
        _log("AIBilliard: enter_play_mode() failed")
        return

    if not _wait_for(lambda: PlayModeManager.instance() is not None and PlayModeManager.instance().is_playing, 20.0):
        _log("AIBilliard: play mode never became active")
        return

    _focus_game_view()
    Input.set_game_focused(True)

    scene = NativeSceneManager.instance().get_active_scene()
    if scene is None:
        _log("AIBilliard: no active scene after play mode")
        return

    if _find_named_object(scene, "Ball") is None or _find_named_object(scene, "Floor") is None:
        _log("AIBilliard: missing Ball, Floor, or wall objects")
        return

    floor = _find_named_object(scene, "Floor")
    floor_pos = _read_vec3(getattr(floor.transform, "position", None)) if floor else None
    floor_scale = _read_vec3(getattr(floor.transform, "local_scale", None)) if floor else None
    if floor_scale is None:
        floor_scale = _read_vec3(getattr(floor.transform, "scale", None))

    ball_snapshot = get_player_snapshot()
    ball_pos = _read_vec3(getattr(ball_snapshot, "position", None) if ball_snapshot is not None else None)
    if ball_pos is None or floor_pos is None or floor_scale is None:
        _log("AIBilliard: unable to read initial scene geometry")
        return

    half_x = abs(floor_scale[0]) * 0.5
    half_z = abs(floor_scale[2]) * 0.5
    margin = max(0.75, min(half_x, half_z) * 0.18)
    target_edge = Vector3(floor_pos[0] + half_x - margin, ball_pos[1], floor_pos[2] + half_z - margin)

    _log(f"AIBilliard start: ball={ball_pos} floor_pos={floor_pos} floor_scale={floor_scale}")
    _log(
        "AIBilliard bounds: "
        f"x=({floor_pos[0] - half_x:.3f}, {floor_pos[0] + half_x:.3f}) "
        f"z=({floor_pos[2] - half_z:.3f}, {floor_pos[2] + half_z:.3f}) margin={margin:.3f}"
    )
    _log(f"AIBilliard target edge point: {target_edge}")

    current_direction = _normalize_xz(Vector3(0.82, 0.0, 0.57))
    last_collision_count = 0
    last_collision_time = time.time()
    clear_actions()

    deadline = time.time() + 18.0
    while time.time() < deadline:
        scene = NativeSceneManager.instance().get_active_scene()
        if scene is None:
            time.sleep(0.05)
            continue

        ball_snapshot = get_player_snapshot()
        floor = _find_named_object(scene, "Floor")
        ball = _find_named_object(scene, "Ball")
        sensor = _find_ball_sensor(ball) if ball is not None else None
        if ball_snapshot is None or floor is None or sensor is None:
            time.sleep(0.05)
            continue

        try:
            ball_pos = _read_vec3(getattr(ball_snapshot, "position", None)) or ball_pos
        except Exception:
            pass

        sensor_count = int(getattr(sensor, "collision_count", 0) or 0)
        event_collision = _extract_collision_from_events()

        if sensor_count > last_collision_count:
            last_collision_count = sensor_count
            normal = _read_vec3(getattr(sensor, "last_contact_normal", None))
            other_name = getattr(sensor, "last_wall_name", None)
            if normal is not None:
                current_direction = _reflect_direction(current_direction, Vector3(*normal))
                last_collision_time = time.time()
                _log(
                    f"AIBilliard collision[{sensor_count}]: wall={other_name} "
                    f"normal={normal} reflected=({current_direction.x:.3f}, {current_direction.z:.3f}) "
                    f"ball={ball_pos}"
                )
        elif event_collision and event_collision.get("normal") is not None:
            normal = _read_vec3(event_collision.get("normal"))
            if normal is not None:
                current_direction = _reflect_direction(current_direction, Vector3(*normal))
                last_collision_time = time.time()
                _log(
                    "AIBilliard event-stream collision: "
                    f"wall={event_collision.get('other_name')} normal={normal} "
                    f"reflected=({current_direction.x:.3f}, {current_direction.z:.3f})"
                )

        send_action(ActionType.Move, x=float(current_direction.x), y=float(current_direction.z))
        Input.set_game_focused(True)

        if time.time() - last_collision_time > 2.25 and ball_pos is not None:
            dx = target_edge.x - ball_pos[0]
            dz = target_edge.z - ball_pos[2]
            if abs(dx) + abs(dz) > 0.25:
                current_direction = _normalize_xz(Vector3(dx, 0.0, dz))
                _log(
                    f"AIBilliard steering to edge: ball={ball_pos} target={target_edge} "
                    f"direction=({current_direction.x:.3f}, {current_direction.z:.3f})"
                )

        time.sleep(0.03)

    clear_actions()
    time.sleep(0.5)
    scene = NativeSceneManager.instance().get_active_scene()
    ball_snapshot = get_player_snapshot()
    final_ball = _read_vec3(getattr(ball_snapshot, "position", None)) if ball_snapshot is not None else None
    _log(f"AIBilliard final ball position: {final_ball}")
    _log("AIBilliard demo complete; leaving play mode running for inspection")

    while True:
        time.sleep(1.0)


def main() -> None:
    worker = threading.Thread(target=_drive_demo, name="ai-billiard-demo", daemon=True)
    worker.start()
    release_engine(str(PROJECT_ROOT))


if __name__ == "__main__":
    main()
