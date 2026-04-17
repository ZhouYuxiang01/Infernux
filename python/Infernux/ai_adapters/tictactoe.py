from __future__ import annotations

from typing import Any

from Infernux.ai_runtime.control_signal import ControlSignal
from Infernux.ai_adapters.protocol import AdapterProtocolError
from Infernux.tictactoe_logic import (
    AI_MARK,
    HUMAN_MARK,
    BoardState,
    EMPTY,
    legal_moves,
    state_from_board,
)


class TicTacToeAdapter:
    BOARD_ROLE = "board"
    BOARD_OBJECT_NAME = "TicTacToeBoard"
    BOARD_CONTROLLER_TYPE = "TicTacToeBoardController"

    def resolve_semantic_entity(self, scene: Any, role: str) -> int | None:
        if role != self.BOARD_ROLE or scene is None:
            return None
        controller = self._find_controller(scene)
        if controller is None:
            return None
        go = getattr(controller, "game_object", None)
        return getattr(go, "id", None) if go is not None else None

    def translate_action(self, name: str, **kwargs: Any) -> ControlSignal:
        if name != "place":
            raise AdapterProtocolError(f"Unknown Tic-Tac-Toe action: {name}")
        row = int(kwargs.get("row", -1))
        col = int(kwargs.get("col", -1))
        if not (0 <= row < 3 and 0 <= col < 3):
            raise AdapterProtocolError("place requires row and col in range 0..2")
        return ControlSignal(buttons={f"place:{row}:{col}": True})

    def get_board_state(self, scene: Any) -> BoardState | None:
        controller = self._find_controller(scene)
        if controller is None:
            return None
        snapshot = getattr(controller, "snapshot_board_state", None)
        if not callable(snapshot):
            return None
        try:
            state = snapshot()
        except Exception:
            return None
        if isinstance(state, BoardState):
            return state
        return None

    def get_current_turn(self, scene: Any) -> str | None:
        state = self.get_board_state(scene)
        if state is None:
            return None
        return state.current_turn

    def list_legal_moves(self, board_state: BoardState) -> list[tuple[int, int]]:
        return legal_moves(board_state.cells)

    def evaluate_board(self, board_state: BoardState) -> dict[str, Any]:
        return {
            "winner": board_state.winner,
            "terminal": board_state.terminal,
            "draw": board_state.draw,
            "current_turn": board_state.current_turn,
            "cells": board_state.cells,
        }

    def _find_controller(self, scene: Any) -> Any | None:
        if scene is None:
            return None

        finder = getattr(scene, "find", None)
        if callable(finder):
            try:
                board_go = finder(self.BOARD_OBJECT_NAME)
            except Exception:
                board_go = None
            controller = self._controller_from_game_object(board_go)
            if controller is not None:
                return controller

        getter = getattr(scene, "get_all_objects", None)
        if not callable(getter):
            return None
        try:
            objects = list(getter() or [])
        except Exception:
            return None
        for game_object in objects:
            controller = self._controller_from_game_object(game_object)
            if controller is not None:
                return controller
        return None

    def _controller_from_game_object(self, game_object: Any) -> Any | None:
        if game_object is None:
            return None
        getter = getattr(game_object, "get_py_components", None)
        if not callable(getter):
            return None
        try:
            components = list(getter() or [])
        except Exception:
            return None
        for comp in components:
            if type(comp).__name__ == self.BOARD_CONTROLLER_TYPE:
                return comp
        return None


__all__ = [
    "AI_MARK",
    "HUMAN_MARK",
    "TicTacToeAdapter",
]
