from __future__ import annotations

import sys
import threading
import time
from math import sqrt
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
SCENE_PATH = PROJECT_ROOT / "Assets" / "Scenes" / "AIParameterTuning.scene"
SCRIPT_ROOT = PROJECT_ROOT / "Assets" / "Scripts"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from BallLaunchController import BallLaunchController
from Infernux.ai_runtime import enter_play_mode, move_entity, pause, resume
from Infernux.ai_runtime.observation_api import get_player_snapshot
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


def _find_ball_controller(ball_obj):
    try:
        for comp in ball_obj.get_py_components() or []:
            if comp.__class__.__name__ == "BallLaunchController":
                return comp
    except Exception:
        return None
    return None


def _focus_game_view() -> None:
    services = EditorServices.instance()
    engine = services.engine if services else None
    if engine is None:
        return

    for _ in range(30):
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
        return all(_find_named_object(scene, name) is not None for name in ("Ground", "TargetMarker", "Ball"))
    except Exception:
        return False


def _ball_position(controller, ball_obj):
    if controller is not None:
        try:
            live_pos = _read_vec3(getattr(controller.game_object.transform, "position", None))
            if live_pos is not None:
                return live_pos
        except Exception:
            pass

    snapshot = None
    try:
        snapshot = get_player_snapshot()
    except Exception:
        snapshot = None

    if snapshot is not None and snapshot.position is not None:
        pos = _read_vec3(snapshot.position)
        if pos is not None:
            return pos

    try:
        return _read_vec3(getattr(ball_obj.transform, "position", None))
    except Exception:
        return None


def _drive_demo() -> None:
    if not _wait_for(lambda: EditorServices.instance().engine is not None, 30.0):
        _log("AIParameterTuning: editor engine never became ready")
        return

    if not _load_scene():
        _log(f"AIParameterTuning: failed to open {SCENE_PATH}")
        return

    if not _wait_for(_scene_is_loaded, 20.0):
        sfm = SceneFileManager.instance()
        current_path = getattr(sfm, "current_scene_path", None) if sfm else None
        _log(f"AIParameterTuning: scene never finished loading (current_scene_path={current_path})")
        return

    _focus_game_view()
    Input.set_game_focused(True)

    scene = NativeSceneManager.instance().get_active_scene()
    if scene is None:
        _log("AIParameterTuning: no active scene after load")
        return

    ground = _find_named_object(scene, "Ground")
    target = _find_named_object(scene, "TargetMarker")
    ball = _find_named_object(scene, "Ball")
    if ground is None or target is None or ball is None:
        _log("AIParameterTuning: missing Ground, TargetMarker, or Ball")
        return

    target_pos = _read_vec3(getattr(target.transform, "position", None))
    ball_pos = _read_vec3(getattr(ball.transform, "position", None))
    if target_pos is None or ball_pos is None:
        _log("AIParameterTuning: unable to read target or ball position")
        return

    start_pos = (-5.5, 0.75, 0.0)
    threshold = 0.5
    low = 0.0
    high = 6.0
    candidate = 3.0
    run_seconds = 4.5
    best = None

    if not enter_play_mode():
        _log("AIParameterTuning: enter_play_mode() failed")
        return

    if not _wait_for(lambda: PlayModeManager.instance() is not None and PlayModeManager.instance().is_playing, 20.0):
        _log("AIParameterTuning: play mode never became active")
        return

    play_scene = NativeSceneManager.instance().get_active_scene()
    if play_scene is not None:
        target = _find_named_object(play_scene, "TargetMarker") or target
        ball = _find_named_object(play_scene, "Ball") or ball
        if target is not None:
            refreshed_target_pos = _read_vec3(getattr(target.transform, "position", None))
            if refreshed_target_pos is not None:
                target_pos = refreshed_target_pos

    _log(
        f"AIParameterTuning target: {target_pos} start={start_pos} "
        f"threshold={threshold:.3f} run_seconds={run_seconds:.1f}"
    )

    for attempt in range(1, 7):
        pause()
        play_scene = NativeSceneManager.instance().get_active_scene()
        if play_scene is not None:
            ball = _find_named_object(play_scene, "Ball") or ball
        if ball is None:
            _log(f"AIParameterTuning attempt {attempt}: Ball object missing")
            return
        ball_id = int(getattr(ball, "id"))
        controller = _find_ball_controller(ball)
        if controller is None:
            _log(f"AIParameterTuning attempt {attempt}: BallLaunchController missing")
            return
        controller.speed = float(candidate)
        move_entity(ball_id, start_pos)
        _log(
            f"AIParameterTuning attempt {attempt}: set speed={float(candidate):.3f} "
            f"controller={controller.__class__.__name__}"
        )

        _focus_game_view()
        Input.set_game_focused(True)
        resume()

        time.sleep(run_seconds)
        pause()

        latest_pos = None
        for _ in range(20):
            time.sleep(0.05)
            latest_pos = _ball_position(controller, ball)
            if latest_pos is None:
                continue
            if abs(latest_pos[0] - start_pos[0]) > 0.05 or abs(latest_pos[2] - start_pos[2]) > 0.05:
                break

        pos = latest_pos
        if pos is None:
            _log(f"AIParameterTuning attempt {attempt}: position unavailable, candidate={candidate:.3f}")
            candidate = 0.5 * (low + high)
            continue

        fx, fy, fz = pos
        dx = fx - target_pos[0]
        dz = fz - target_pos[2]
        distance = sqrt(dx * dx + dz * dz)
        score = 1.0 / (1.0 + distance)

        if best is None or distance < best["distance"]:
            best = {
                "attempt": attempt,
                "candidate": float(candidate),
                "final": (fx, fy, fz),
                "distance": float(distance),
                "score": float(score),
            }

        _log(
            f"AIParameterTuning attempt {attempt}: speed={candidate:.3f} "
            f"final=({fx:.3f}, {fy:.3f}, {fz:.3f}) "
            f"target=({target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}) "
            f"distance={distance:.3f} score={score:.3f}"
        )

        if distance < threshold:
            _log("AIParameterTuning success: within threshold")
            break

        if fx < target_pos[0]:
            low = candidate
        else:
            high = candidate

        candidate = 0.5 * (low + high)
        _log(f"AIParameterTuning next candidate: {candidate:.3f} bracket=({low:.3f}, {high:.3f})")

    if best is not None:
        _log(
            "AIParameterTuning best: "
            f"attempt={best['attempt']} speed={best['candidate']:.3f} "
            f"final=({best['final'][0]:.3f}, {best['final'][1]:.3f}, {best['final'][2]:.3f}) "
            f"distance={best['distance']:.3f} score={best['score']:.3f}"
        )
    else:
        _log("AIParameterTuning best: none")

    _log("AIParameterTuning demo complete; leaving play mode paused for inspection")

    while True:
        time.sleep(1.0)


def main() -> None:
    worker = threading.Thread(target=_drive_demo, name="ai-parameter-tuning-demo", daemon=True)
    worker.start()
    release_engine(str(PROJECT_ROOT))


if __name__ == "__main__":
    main()
