from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

EMPTY = ""
HUMAN_MARK = "X"
AI_MARK = "O"

WIN_LINES: tuple[tuple[tuple[int, int], ...], ...] = (
    ((0, 0), (0, 1), (0, 2)),
    ((1, 0), (1, 1), (1, 2)),
    ((2, 0), (2, 1), (2, 2)),
    ((0, 0), (1, 0), (2, 0)),
    ((0, 1), (1, 1), (2, 1)),
    ((0, 2), (1, 2), (2, 2)),
    ((0, 0), (1, 1), (2, 2)),
    ((0, 2), (1, 1), (2, 0)),
)

CORNER_MOVES: tuple[tuple[int, int], ...] = (
    (0, 0),
    (0, 2),
    (2, 0),
    (2, 2),
)

EDGE_MOVES: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 0),
    (1, 2),
    (2, 1),
)


@dataclass(frozen=True)
class BoardState:
    cells: tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]
    current_turn: str = HUMAN_MARK
    winner: str | None = None
    terminal: bool = False
    draw: bool = False


def empty_board() -> tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]:
    return (
        (EMPTY, EMPTY, EMPTY),
        (EMPTY, EMPTY, EMPTY),
        (EMPTY, EMPTY, EMPTY),
    )


def board_from_rows(rows: Iterable[Iterable[str]]) -> tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]:
    normalized: list[tuple[str, str, str]] = []
    for row in rows:
        items = [str(cell or EMPTY) for cell in row]
        if len(items) != 3:
            raise ValueError("Tic-Tac-Toe board rows must have exactly 3 cells")
        normalized.append((items[0], items[1], items[2]))
    if len(normalized) != 3:
        raise ValueError("Tic-Tac-Toe board must have exactly 3 rows")
    return (normalized[0], normalized[1], normalized[2])


def board_from_flat(cells: Iterable[str]) -> tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]:
    flat = [str(cell or EMPTY) for cell in cells]
    if len(flat) != 9:
        raise ValueError("Tic-Tac-Toe board must have exactly 9 cells")
    return board_from_rows((flat[i : i + 3] for i in range(0, 9, 3)))


def flat_from_board(board: Iterable[Iterable[str]]) -> list[str]:
    return [str(cell or EMPTY) for row in board for cell in row]


def normalize_mark(mark: str | None) -> str:
    value = str(mark or "").strip().upper()
    if value in {HUMAN_MARK, AI_MARK}:
        return value
    return HUMAN_MARK


def legal_moves(board: Iterable[Iterable[str]]) -> list[tuple[int, int]]:
    moves: list[tuple[int, int]] = []
    for row_idx, row in enumerate(board):
        for col_idx, cell in enumerate(row):
            if not str(cell or EMPTY):
                moves.append((row_idx, col_idx))
    return moves


def winner_for(board: Iterable[Iterable[str]]) -> str | None:
    rows = board_from_rows(board)
    for line in WIN_LINES:
        a = rows[line[0][0]][line[0][1]]
        if not a:
            continue
        if all(rows[r][c] == a for r, c in line[1:]):
            return a
    return None


def board_is_full(board: Iterable[Iterable[str]]) -> bool:
    return all(cell for row in board for cell in row)


def evaluate_board(board: Iterable[Iterable[str]]) -> tuple[str | None, bool, bool]:
    winner = winner_for(board)
    draw = winner is None and board_is_full(board)
    terminal = winner is not None or draw
    return winner, draw, terminal


def state_from_board(
    board: Iterable[Iterable[str]],
    *,
    current_turn: str = HUMAN_MARK,
) -> BoardState:
    cells = board_from_rows(board)
    winner, draw, terminal = evaluate_board(cells)
    turn = "" if terminal else normalize_mark(current_turn)
    return BoardState(
        cells=cells,
        current_turn=turn,
        winner=winner,
        terminal=terminal,
        draw=draw,
    )


def apply_move(
    state: BoardState,
    row: int,
    col: int,
    mark: str | None = None,
) -> BoardState:
    if state.terminal:
        raise ValueError("Cannot apply a move to a terminal Tic-Tac-Toe state")
    if not (0 <= row < 3 and 0 <= col < 3):
        raise ValueError("row and col must be in range 0..2")
    if state.cells[row][col]:
        raise ValueError("Cell is already occupied")

    move_mark = normalize_mark(mark or state.current_turn)
    if not move_mark:
        raise ValueError("A move mark is required")

    rows = [list(r) for r in state.cells]
    rows[row][col] = move_mark
    next_turn = AI_MARK if move_mark == HUMAN_MARK else HUMAN_MARK
    return state_from_board(rows, current_turn=next_turn)


def choose_ai_move(
    state: BoardState,
    *,
    ai_mark: str = AI_MARK,
    human_mark: str = HUMAN_MARK,
) -> tuple[int, int]:
    if state.terminal:
        raise ValueError("Cannot choose a move for a terminal Tic-Tac-Toe state")

    ai = normalize_mark(ai_mark)
    human = normalize_mark(human_mark)
    moves = legal_moves(state.cells)

    for row, col in moves:
        candidate = apply_move(state, row, col, ai)
        if candidate.winner == ai:
            return row, col

    for row, col in moves:
        candidate = apply_move(state, row, col, human)
        if candidate.winner == human:
            return row, col

    for row, col in ((1, 1),):
        if state.cells[row][col] == EMPTY:
            return row, col

    for move in CORNER_MOVES:
        if move in moves:
            return move

    for move in EDGE_MOVES:
        if move in moves:
            return move

    raise ValueError("No legal Tic-Tac-Toe moves available")


def format_board(state: BoardState | Iterable[Iterable[str]]) -> str:
    board = state.cells if isinstance(state, BoardState) else board_from_rows(state)
    return "\n".join(
        " | ".join(cell or " " for cell in row)
        for row in board
    )
