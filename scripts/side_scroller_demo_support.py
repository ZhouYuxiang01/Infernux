from __future__ import annotations

from dataclasses import dataclass


LAYOUT = (
    "............................................",
    "............................................",
    "............................................",
    ".................................###........",
    ".....................C...C..................",
    ".........C...?...#####....C...C.............",
    "........#####...............................",
    "..P.C......C.......E....................F...",
    "############################################",
    "############################################",
)


@dataclass(frozen=True, slots=True)
class LayoutCells:
    player: tuple[int, int]
    finish: tuple[int, int]
    collectibles: tuple[tuple[int, int], ...]
    enemies: tuple[tuple[int, int], ...]
    reward_blocks: tuple[tuple[int, int], ...]
    solids: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class ControlPhase:
    label: str
    axes: dict[str, float]
    buttons: dict[str, bool]
    seconds: float


CONTROL_ROUTE = (
    ControlPhase("run to the first coin", {"move_x": 1.0}, {}, 1.60),
    ControlPhase("jump the first floor gap", {"move_x": 1.0}, {"jump": True}, 0.42),
    ControlPhase("land past the first gap", {"move_x": 1.0}, {"jump": False}, 0.75),
    ControlPhase("approach the patrol enemy", {"move_x": 1.0}, {"jump": False}, 0.55),
    ControlPhase("jump over the patrol enemy", {"move_x": 1.0}, {"jump": True}, 0.50),
    ControlPhase("continue to the second gap", {"move_x": 1.0}, {"jump": False}, 1.20),
    ControlPhase("jump the second floor gap", {"move_x": 1.0}, {"jump": True}, 0.42),
    ControlPhase("final approach to the finish flag", {"move_x": 1.0}, {"jump": False}, 4.10),
)


def find_layout_cells(layout: tuple[str, ...]) -> LayoutCells:
    player: tuple[int, int] | None = None
    finish: tuple[int, int] | None = None
    collectibles: list[tuple[int, int]] = []
    enemies: list[tuple[int, int]] = []
    reward_blocks: list[tuple[int, int]] = []
    solids: list[tuple[int, int]] = []

    for row, line in enumerate(layout):
        for col, char in enumerate(line):
            if char == "P":
                player = (row, col)
            elif char == "F":
                finish = (row, col)
            elif char == "C":
                collectibles.append((row, col))
            elif char == "E":
                enemies.append((row, col))
            elif char == "?":
                reward_blocks.append((row, col))
                solids.append((row, col))
            elif char == "#":
                solids.append((row, col))

    if player is None:
        raise ValueError("layout must contain a player marker P")
    if finish is None:
        raise ValueError("layout must contain a finish marker F")
    return LayoutCells(
        player=player,
        finish=finish,
        collectibles=tuple(collectibles),
        enemies=tuple(enemies),
        reward_blocks=tuple(reward_blocks),
        solids=tuple(solids),
    )


def is_solid_cell(layout: tuple[str, ...], row: int, col: int) -> bool:
    if row < 0 or row >= len(layout):
        return True
    if col < 0 or col >= len(layout[row]):
        return True
    return layout[row][col] in {"#", "?"}
