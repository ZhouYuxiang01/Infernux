from __future__ import annotations

import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
PROJECT_ROOT = REPO_ROOT / "TestProject"
SCENE_PATH = PROJECT_ROOT / "Assets" / "Scenes" / "TicTacToeDemo.scene"
SCRIPT_ROOT = PROJECT_ROOT / "Assets" / "Scripts"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from TicTacToeBoardController import TicTacToeBoardController  # noqa: F401

from Infernux.ai_adapters.tictactoe import TicTacToeAdapter
from Infernux.ai_runtime import enter_play_mode
from Infernux.debug import Debug
from Infernux.engine import release_engine
from Infernux.engine.play_mode import PlayModeManager
from Infernux.engine.scene_manager import SceneFileManager
from Infernux.engine.ui.closable_panel import ClosablePanel
from Infernux.engine.ui.editor_services import EditorServices
from Infernux.input import Input
from Infernux.lib import SceneManager as NativeSceneManager
from Infernux.tictactoe_logic import AI_MARK, HUMAN_MARK, choose_ai_move, format_board


ADAPTER = TicTacToeAdapter()


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


def _find_board_controller(scene):
    if scene is None:
        return None
    finder = getattr(scene, "find", None)
    if callable(finder):
        try:
            board_go = finder("TicTacToeBoard")
        except Exception:
            board_go = None
        if board_go is not None:
            for comp in board_go.get_py_components():
                if isinstance(comp, TicTacToeBoardController):
                    return comp
    return None


def _game_ui_ready(engine) -> bool:
    if engine is None:
        return False
    try:
        return engine.get_screen_ui_renderer() is not None and engine.get_game_texture_id() != 0
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
        return scene.find("TicTacToeBoard") is not None
    except Exception:
        return False


def _run_demo() -> None:
    if not _wait_for(lambda: EditorServices.instance().engine is not None, 30.0):
        _log("TicTacToe: editor engine never became ready")
        return

    if not _load_scene():
        _log(f"TicTacToe: failed to open {SCENE_PATH}")
        return

    if not _wait_for(_scene_is_loaded, 20.0):
        sfm = SceneFileManager.instance()
        _log(f"TicTacToe: scene never finished loading (current_scene_path={getattr(sfm, 'current_scene_path', None)})")
        return

    _focus_game_view()
    Input.set_game_focused(True)

    if not enter_play_mode():
        _log("TicTacToe: enter_play_mode() failed")
        return

    if not _wait_for(lambda: PlayModeManager.instance() is not None and PlayModeManager.instance().is_playing, 20.0):
        _log("TicTacToe: play mode never became active")
        return

    _focus_game_view()
    Input.set_game_focused(True)

    engine = EditorServices.instance().engine
    _log("TicTacToe: waiting for game UI renderer")
    if not _wait_for(lambda: _game_ui_ready(engine), 20.0):
        _log("TicTacToe: game UI renderer was not ready in time")
    else:
        _log("TicTacToe: game UI renderer ready")

    scene = NativeSceneManager.instance().get_active_scene()
    if scene is None:
        _log("TicTacToe: no active scene after play mode")
        return

    board = _find_board_controller(scene)
    if board is None:
        _log("TicTacToe: board controller not found")
        return

    _log("TicTacToe: board loaded")
    if hasattr(board, "reset_board_state"):
        board.reset_board_state()
    _log(format_board(board.snapshot_board_state()))
    _log("TicTacToe: fresh game ready for manual test")

    while True:
        scene = NativeSceneManager.instance().get_active_scene()
        if scene is None:
            time.sleep(0.05)
            continue

        board = _find_board_controller(scene)
        if board is None:
            time.sleep(0.05)
            continue

        state = ADAPTER.get_board_state(scene)
        if state is None:
            time.sleep(0.05)
            continue

        if state.terminal:
            if state.winner:
                _log(f"TicTacToe: {state.winner} wins")
            else:
                _log("TicTacToe: draw")
            _log(format_board(state))
            break

        if state.current_turn == board.ai_mark:
            move = choose_ai_move(state, ai_mark=board.ai_mark, human_mark=board.human_mark)
            if move is not None and board.request_place(*move):
                _log(f"TicTacToe AI -> {move}")
                _log(format_board(board.snapshot_board_state()))
            time.sleep(0.05)
            continue

        Input.set_game_focused(True)
        time.sleep(0.05)

    while True:
        time.sleep(1.0)


def main() -> None:
    worker = threading.Thread(target=_run_demo, name="tictactoe-agent-demo", daemon=True)
    worker.start()
    try:
        release_engine(str(PROJECT_ROOT))
    finally:
        Input.set_game_focused(False)


if __name__ == "__main__":
    main()
