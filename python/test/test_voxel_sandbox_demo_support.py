from scripts.voxel_sandbox_demo_support import (
    BLOCK_TYPES,
    CONTROL_ROUTE,
    WORLD_LAYOUT,
    cell_key,
    find_spawn_cell,
    is_solid_block,
)


def test_layout_contains_spawn_and_solid_blocks():
    assert find_spawn_cell(WORLD_LAYOUT) == (2, 2, 3)
    assert any(is_solid_block(block) for layer in WORLD_LAYOUT for row in layer for block in row)


def test_block_types_cover_core_materials():
    assert {"grass", "dirt", "stone", "wood", "leaf", "water"}.issubset(BLOCK_TYPES)
    assert not is_solid_block("air")
    assert not is_solid_block("water")
    assert is_solid_block("grass")


def test_control_route_exercises_agent_actions():
    actions = {step.action for step in CONTROL_ROUTE}
    assert {"move", "turn", "mine", "place", "slot"}.issubset(actions)


def test_control_route_exercises_first_person_look_axes():
    axes = {axis for step in CONTROL_ROUTE for axis in step.axes}
    assert "look_x" in axes
    assert "look_y" in axes


def test_cell_key_is_stable():
    assert cell_key((1, 2, 3)) == "1,2,3"
