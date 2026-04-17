from __future__ import annotations

from types import SimpleNamespace

from Infernux.ai_adapters.tictactoe import TicTacToeAdapter
from Infernux.tictactoe_logic import (
    AI_MARK,
    HUMAN_MARK,
    BoardState,
    apply_move,
    choose_ai_move,
    empty_board,
    legal_moves,
    state_from_board,
)


def test_board_state_detects_winner():
    state = state_from_board(
        (
            ("X", "X", "X"),
            ("", "O", ""),
            ("O", "", ""),
        ),
        current_turn=AI_MARK,
    )

    assert state.terminal is True
    assert state.winner == HUMAN_MARK
    assert state.draw is False


def test_choose_ai_move_wins_before_blocking():
    state = state_from_board(
        (
            ("O", "O", ""),
            ("X", "X", ""),
            ("", "", ""),
        ),
        current_turn=AI_MARK,
    )

    assert choose_ai_move(state, ai_mark=AI_MARK, human_mark=HUMAN_MARK) == (0, 2)


def test_choose_ai_move_blocks_when_no_win():
    state = state_from_board(
        (
            ("X", "X", ""),
            ("O", "", ""),
            ("", "", ""),
        ),
        current_turn=AI_MARK,
    )

    assert choose_ai_move(state, ai_mark=AI_MARK, human_mark=HUMAN_MARK) == (0, 2)


def test_choose_ai_move_prefers_center_then_corner_then_edge():
    center_state = state_from_board(
        (
            ("X", "", ""),
            ("", "", ""),
            ("", "", "O"),
        ),
        current_turn=AI_MARK,
    )
    corner_state = state_from_board(
        (
            ("", "", "X"),
            ("", "O", ""),
            ("", "", ""),
        ),
        current_turn=AI_MARK,
    )
    edge_state = state_from_board(
        (
            ("X", "O", "X"),
            ("", "X", "O"),
            ("O", "X", "O"),
        ),
        current_turn=AI_MARK,
    )

    assert choose_ai_move(center_state, ai_mark=AI_MARK, human_mark=HUMAN_MARK) == (1, 1)
    assert choose_ai_move(corner_state, ai_mark=AI_MARK, human_mark=HUMAN_MARK) == (0, 0)
    assert choose_ai_move(edge_state, ai_mark=AI_MARK, human_mark=HUMAN_MARK) == (1, 0)


def test_adapter_translate_action_encodes_cell_coordinates():
    adapter = TicTacToeAdapter()
    signal = adapter.translate_action("place", row=2, col=1)

    assert signal.buttons == {"place:2:1": True}


def test_adapter_get_board_state_reads_pure_semantics():
    class TicTacToeBoardController:
        def snapshot_board_state(self):
            return BoardState(
                cells=empty_board(),
                current_turn=AI_MARK,
                winner=None,
                terminal=False,
                draw=False,
            )

    class _FakeGameObject:
        id = 17

        def get_py_components(self):
            return [TicTacToeBoardController()]

    class _FakeScene:
        def find(self, name):
            if name == "TicTacToeBoard":
                return _FakeGameObject()
            return None

    adapter = TicTacToeAdapter()
    state = adapter.get_board_state(_FakeScene())

    assert state is not None
    assert state.current_turn == AI_MARK
    assert state.cells == empty_board()


def test_apply_move_requires_empty_cell():
    state = state_from_board(empty_board(), current_turn=HUMAN_MARK)
    next_state = apply_move(state, 1, 1, HUMAN_MARK)

    assert next_state.cells[1][1] == HUMAN_MARK
    assert next_state.current_turn == AI_MARK
    assert legal_moves(next_state.cells)
