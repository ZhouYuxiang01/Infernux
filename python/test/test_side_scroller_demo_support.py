from scripts.side_scroller_demo_support import (
    CONTROL_ROUTE,
    LAYOUT,
    find_layout_cells,
    is_solid_cell,
)


def test_layout_has_required_platformer_markers():
    cells = find_layout_cells(LAYOUT)

    assert cells.player == (7, 2)
    assert cells.finish[1] > cells.player[1]
    assert len(cells.collectibles) >= 6
    assert len(cells.enemies) >= 1
    assert len(cells.reward_blocks) >= 1


def test_solid_cell_policy_treats_bounds_and_reward_blocks_as_solid():
    assert is_solid_cell(LAYOUT, 999, 999) is True
    assert is_solid_cell(LAYOUT, 9, 0) is True
    assert is_solid_cell(LAYOUT, 5, 13) is True
    assert is_solid_cell(LAYOUT, 7, 2) is False


def test_control_route_contains_movement_and_jump():
    assert any(phase.axes.get("move_x", 0.0) > 0.0 for phase in CONTROL_ROUTE)
    assert any(phase.buttons.get("jump") for phase in CONTROL_ROUTE)
    assert sum(phase.seconds for phase in CONTROL_ROUTE) > 3.0
