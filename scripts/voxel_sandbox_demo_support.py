from __future__ import annotations

from dataclasses import dataclass, field


BLOCK_TYPES = ("air", "grass", "dirt", "stone", "wood", "leaf", "water")
SOLID_BLOCK_TYPES = frozenset({"grass", "dirt", "stone", "wood", "leaf"})

BLOCK_CHAR_TO_TYPE = {
    ".": "air",
    "@": "air",
    "G": "grass",
    "D": "dirt",
    "R": "stone",
    "T": "wood",
    "L": "leaf",
    "W": "water",
}

# WORLD_LAYOUT is indexed as WORLD_LAYOUT[y][z][x]. The spawn marker is an
# air cell at x=2, y=2, z=3, one block above the ground.
WORLD_LAYOUT = (
    (
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
        "RRRRRRRRRRRRRRRR",
    ),
    (
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGWWGGGGGG",
        "GGGGGGGGWWGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
        "GGGGGGGGGGGGGGGG",
    ),
    (
        "................",
        "................",
        "..........T.....",
        "..@.R.....T.....",
        "..........T.....",
        "................",
        ".....RRR........",
        "................",
        "................",
        "................",
        "................",
        "................",
    ),
    (
        "................",
        "................",
        ".........LLL....",
        ".........LLL....",
        ".........LLL....",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ),
    (
        "................",
        "................",
        "..........L.....",
        ".........LLL....",
        "..........L.....",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ),
)


@dataclass(frozen=True, slots=True)
class ControlStep:
    action: str
    label: str
    axes: dict[str, float] = field(default_factory=dict)
    buttons: dict[str, bool] = field(default_factory=dict)
    seconds: float = 0.2


CONTROL_ROUTE = (
    ControlStep("move", "walk toward the test block", {"move_forward": 1.0}, {}, 0.35),
    ControlStep("turn", "center first-person view on the test block", {"look_x": 0.20, "look_y": -0.25}, {}, 0.20),
    ControlStep("move", "strafe to show blocked voxel navigation", {"move_right": 0.35}, {}, 0.20),
    ControlStep("mine", "mine selected solid block", {}, {"mine": True}, 0.25),
    ControlStep("slot", "switch inventory slot", {}, {"slot_next": True}, 0.20),
    ControlStep("place", "place the selected block into air", {}, {"place": True}, 0.25),
    ControlStep("move", "step back for visual verification", {"move_forward": -0.55}, {}, 0.40),
)


def cell_key(cell: tuple[int, int, int]) -> str:
    return f"{int(cell[0])},{int(cell[1])},{int(cell[2])}"


def world_dimensions(layout: tuple[tuple[str, ...], ...] = WORLD_LAYOUT) -> tuple[int, int, int]:
    height = len(layout)
    depth = len(layout[0]) if height else 0
    width = len(layout[0][0]) if depth else 0
    return width, height, depth


def block_type_for_char(char: str) -> str:
    return BLOCK_CHAR_TO_TYPE.get(str(char), "air")


def is_solid_block(block: str) -> bool:
    value = str(block)
    block_type = BLOCK_CHAR_TO_TYPE.get(value, value)
    return block_type in SOLID_BLOCK_TYPES


def find_spawn_cell(layout: tuple[tuple[str, ...], ...] = WORLD_LAYOUT) -> tuple[int, int, int]:
    for y, layer in enumerate(layout):
        for z, row in enumerate(layer):
            for x, char in enumerate(row):
                if char == "@":
                    return (x, y, z)
    raise ValueError("voxel sandbox layout must contain a spawn marker '@'")


def iter_layout_blocks(layout: tuple[tuple[str, ...], ...] = WORLD_LAYOUT):
    for y, layer in enumerate(layout):
        for z, row in enumerate(layer):
            for x, char in enumerate(row):
                block_type = block_type_for_char(char)
                if block_type != "air":
                    yield (x, y, z), block_type


def block_at_cell(
    cell: tuple[int, int, int],
    layout: tuple[tuple[str, ...], ...] = WORLD_LAYOUT,
) -> str:
    x, y, z = (int(cell[0]), int(cell[1]), int(cell[2]))
    width, height, depth = world_dimensions(layout)
    if x < 0 or y < 0 or z < 0 or x >= width or y >= height or z >= depth:
        return "air"
    return block_type_for_char(layout[y][z][x])
