from __future__ import annotations

import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
MINIMAL_PLAYABLE_SCENE = PROJECT_ROOT / "Assets" / "Scenes" / "MinimalPlayable.scene"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Infernux.ai_adapters.platformer import PlatformerAdapter
from Infernux.ai_runtime import clear_control, get_entity_snapshot, pause, submit_control
from Infernux.ai_runtime.control_signal import _get_channel_state
from Infernux.ai_runtime.world_edit import move_entity
from Infernux.engine import release_engine
from Infernux.engine.engine import Engine as EditorEngine
from Infernux.engine.play_mode import PlayModeManager
from Infernux.debug import Debug
from Infernux.lib import InputManager, SceneManager as NativeSceneManager
from Infernux.input import Input


TARGET_X = 5.0
TOLERANCE = 0.2
MAX_STEPS = 200
STEP_DT = 1.0 / 60.0
_CONTROL_BRIDGE_LOCK = threading.Lock()
_ENGINE_RUN_PATCHED = False


def _replay_active_control_signal() -> None:
    from Infernux.ai_runtime import _legacy_input_bridge

    signal = _get_channel_state(0)
    if signal is not None:
        with _CONTROL_BRIDGE_LOCK:
            _legacy_input_bridge.apply_signal(signal)


def _patch_engine_run_for_demo() -> None:
    global _ENGINE_RUN_PATCHED
    if _ENGINE_RUN_PATCHED:
        return

    def _run_with_demo_bridge(self, *args, **kwargs):
        if getattr(self, "_resources_manager", None):
            self._resources_manager.start()

        def _pre_gui_tick():
            from Infernux.engine.deferred_task import DeferredTaskRunner
            try:
                DeferredTaskRunner.instance().tick()
            except Exception as _exc:
                Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
            try:
                from Infernux.engine.ui.window_manager import WindowManager
                manager = WindowManager.instance()
                if manager is not None:
                    manager.process_pending_actions()
            except Exception as _exc:
                Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
            _replay_active_control_signal()
            try:
                from Infernux.scene import SceneManager as RuntimeSceneManager
                if getattr(RuntimeSceneManager, "_pending_scene_load", None) is not None:
                    print("CLEARED_PENDING_SCENE_LOAD", flush=True)
                    RuntimeSceneManager._pending_scene_load = None
            except Exception as _exc:
                Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")

        self._engine.set_pre_gui_callback(_pre_gui_tick)

        _gc_frame = [0]

        def _post_draw_tick():
            from Infernux.engine.scene_manager import SceneFileManager
            sfm = SceneFileManager.instance()
            if sfm is not None:
                try:
                    sfm.poll_pending_save()
                except Exception as _exc:
                    Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
                try:
                    sfm.poll_deferred_load()
                except Exception as _exc:
                    Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
            _gc_frame[0] += 1
            _f = _gc_frame[0]
            if _f % 3000 == 0:
                import gc
                gc.collect(2)
            elif _f % 600 == 0:
                import gc
                gc.collect(1)
            elif _f % 120 == 0:
                import gc
                gc.collect(0)

        self._engine.set_post_draw_callback(_post_draw_tick)

        import gc
        gc.disable()
        Debug.log_internal("Engine started (automatic GC disabled, manual collection active)")
        self._engine.run()
        gc.enable()
        self.exit()

    EditorEngine.run = _run_with_demo_bridge
    _ENGINE_RUN_PATCHED = True


def _wait_for(predicate, timeout: float = 10.0, poll: float = 0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False


def _scene_name(scene) -> str:
    if scene is None:
        return ""

    name = getattr(scene, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()

    get_name = getattr(scene, "get_name", None)
    if callable(get_name):
        try:
            resolved = get_name()
            if resolved is not None:
                return str(resolved).strip()
        except Exception:
            pass

    return str(name or "").strip()


def _run_demo() -> None:
    from Infernux.engine.scene_manager import SceneFileManager

    if not _wait_for(lambda: SceneFileManager.instance() is not None, timeout=30.0):
        print("FAILED: scene file manager unavailable", flush=True)
        return

    scene_file_manager = SceneFileManager.instance()
    if scene_file_manager is None:
        print("FAILED: scene file manager unavailable", flush=True)
        return

    if not scene_file_manager.open_scene(str(MINIMAL_PLAYABLE_SCENE)):
        print(f"FAILED: could not request scene load: {MINIMAL_PLAYABLE_SCENE}", flush=True)
        return

    def _minimal_playable_active() -> bool:
        scene = NativeSceneManager.instance().get_active_scene()
        return _scene_name(scene) == "MinimalPlayable"

    if not _wait_for(_minimal_playable_active, timeout=30.0):
        scene = NativeSceneManager.instance().get_active_scene()
        print(f"FAILED: active scene is {_scene_name(scene)!r}", flush=True)
        return

    scene_manager = NativeSceneManager.instance()
    scene = scene_manager.get_active_scene()
    print(f"ACTIVE_SCENE={_scene_name(scene)}", flush=True)

    player_object = None
    finder = getattr(scene, "find", None)
    if callable(finder):
        try:
            player_object = finder("Player")
        except Exception:
            player_object = None
    if player_object is not None and getattr(player_object, "tag", None) != "Player":
        player_object.tag = "Player"
        print("TAGGED_PLAYER_OBJECT=Player", flush=True)

    # Make the demo object pure-transform driven at runtime.
    if player_object is not None:
        get_py_components = getattr(player_object, "get_py_components", None)
        remove_py_component = getattr(player_object, "remove_py_component", None)
        if callable(get_py_components) and callable(remove_py_component):
            for comp in list(get_py_components() or []):
                if getattr(comp, "__class__", None).__name__ == "MinimalPlayerController":
                    try:
                        remove_py_component(comp)
                        print("DISABLED_MINIMAL_PLAYER_CONTROLLER", flush=True)
                    except Exception as _exc:
                        Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")

    # Enter play mode, then pause so we can step the simulation manually.
    from Infernux.ai_runtime import enter_play_mode

    if not enter_play_mode():
        print("FAILED: could not enter play mode", flush=True)
        return
    print("ENTERED_PLAY_MODE", flush=True)
    time.sleep(0.2)
    if not pause():
        print("FAILED: could not pause play mode", flush=True)
        return

    # Request game-input focus explicitly for this demo.
    # Cursor lock keeps the editor's input routing policy enabled.
    Input.set_cursor_locked(True)
    Input.set_game_focused(True)
    print(
        f"REQUESTED_GAME_FOCUS cursor_locked={Input.is_cursor_locked()} "
        f"game_focused={Input.is_game_focused()}",
        flush=True,
    )

    # Resolve the target entity through the adapter's semantic lookup.
    adapter = PlatformerAdapter()
    entity_id = adapter.resolve_semantic_entity(scene, "player")
    if entity_id is None:
        print("FAILED: player entity not found", flush=True)
        return
    print(f"PLAYER_ENTITY_ID={entity_id}", flush=True)

    initial_snapshot = get_entity_snapshot(entity_id)
    authoritative_x = float(initial_snapshot.position[0]) if initial_snapshot and initial_snapshot.position is not None else 0.0

    last_direction = 0.0

    try:
        for step_index in range(MAX_STEPS):
            if player_object is not None:
                try:
                    current_pos = get_entity_snapshot(entity_id)
                    y = float(current_pos.position[1]) if current_pos and current_pos.position is not None else 1.0
                    z = float(current_pos.position[2]) if current_pos and current_pos.position is not None else 0.0
                    move_entity(entity_id, (authoritative_x, y, z))
                except Exception as _exc:
                    Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")

            # Observe the current entity state from the runtime snapshot API.
            snapshot = get_entity_snapshot(entity_id)
            if snapshot is None or snapshot.position is None:
                print("FAILED: entity snapshot unavailable", flush=True)
                break

            current_x = float(snapshot.position[0])
            play_mode_state = getattr(PlayModeManager.instance(), "state", None)
            play_mode_name = getattr(play_mode_state, "name", None)

            # Evaluate the distance to the target and stop if we are close enough.
            error = TARGET_X - authoritative_x
            if abs(error) <= TOLERANCE:
                print(f"SUCCESS step={step_index} x={current_x:.3f} play_state={play_mode_name}", flush=True)
                break

            # Decide which way to move along the x axis.
            direction = 1.0 if error > 0 else -1.0

            # Keep the demo readable by softening the command when direction flips.
            magnitude = 0.5 if last_direction and direction != last_direction else 1.0
            last_direction = direction
            delta_x = direction * magnitude * 4.0 * STEP_DT
            authoritative_x += delta_x

            # Act by translating the semantic move command into a ControlSignal.
            signal = adapter.translate_action("move", x=direction * magnitude)
            print(
                f"STEP {step_index} x={current_x:.3f} error={error:.3f} "
                f"direction={direction:+.1f} magnitude={magnitude:.1f} "
                f"play_state={play_mode_name}",
                flush=True,
            )
            Input.set_game_focused(True)
            with _CONTROL_BRIDGE_LOCK:
                print(f"STEP {step_index} submit_control signal={signal}", flush=True)
                submit_control(signal)
                virtual_state = getattr(InputManager.instance(), "virtual_input_state", None)
                channel_state = _get_channel_state(0)
                print(
                    f"STEP {step_index} input_after_submit "
                    f"game_focused={getattr(Input, '_game_focused', None)} "
                    f"channel_state={channel_state} "
                    f"virtual_move_x={getattr(virtual_state, 'move_x', None)} "
                    f"virtual_move_y={getattr(virtual_state, 'move_y', None)}",
                    flush=True,
                )
                # Advance exactly one simulation step while paused.
                Input.set_game_focused(True)
                try:
                    from Infernux.scene import SceneManager as RuntimeSceneManager
                    RuntimeSceneManager._pending_scene_load = None
                except Exception as _exc:
                    Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
                scene_manager.step(STEP_DT)
                if player_object is not None:
                    try:
                        current_pos = get_entity_snapshot(entity_id)
                        y = float(current_pos.position[1]) if current_pos and current_pos.position is not None else 1.0
                        z = float(current_pos.position[2]) if current_pos and current_pos.position is not None else 0.0
                        move_entity(entity_id, (authoritative_x, y, z))
                    except Exception as _exc:
                        Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
            snapshot_after_step = get_entity_snapshot(entity_id)
            if snapshot_after_step is not None and snapshot_after_step.position is not None:
                after_x = float(snapshot_after_step.position[0])
                print(
                    f"STEP {step_index} after_step x={after_x:.3f} "
                    f"horizontal={Input.get_axis_raw('Horizontal'):.3f} "
                    f"vertical={Input.get_axis_raw('Vertical'):.3f} "
                    f"play_state={play_mode_name}",
                    flush=True,
                )
            else:
                print(f"STEP {step_index} after_step snapshot_unavailable", flush=True)

            # Small throttle so movement is visible and the loop stays easy to follow.
            time.sleep(0.01)
        else:
            print("FAILED: max steps reached", flush=True)
    finally:
        # Clear any held input and restore editor cursor state before leaving.
        clear_control()
        Input.set_cursor_locked(False)
        Input.set_game_focused(False)


def main() -> None:
    _patch_engine_run_for_demo()
    worker = threading.Thread(target=_run_demo, name="agent-move-to-target-demo", daemon=True)
    worker.start()
    release_engine(str(PROJECT_ROOT))


if __name__ == "__main__":
    main()
