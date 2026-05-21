from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "TestProject" / "Assets" / "Scripts" / "PelletChaseController.py"


class _Vector3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _InxComponent:
    pass


class _Input:
    horizontal = 0.0
    vertical = 0.0

    @classmethod
    def get_axis_raw(cls, name):
        if name == "Horizontal":
            return cls.horizontal
        if name == "Vertical":
            return cls.vertical
        return 0.0


def _load_controller_class():
    for name in [
        "PelletChaseController_test",
        "Infernux",
        "Infernux.debug",
        "Infernux.input",
        "Infernux.lib",
    ]:
        sys.modules.pop(name, None)

    infernux = types.ModuleType("Infernux")
    infernux.InxComponent = _InxComponent
    infernux.Vector3 = _Vector3

    debug_mod = types.ModuleType("Infernux.debug")
    debug_mod.Debug = types.SimpleNamespace(log=lambda *args, **kwargs: None, log_warning=lambda *args, **kwargs: None)

    input_mod = types.ModuleType("Infernux.input")
    input_mod.Input = _Input

    lib_mod = types.ModuleType("Infernux.lib")
    lib_mod.SceneManager = types.SimpleNamespace(instance=lambda: None)

    sys.modules["Infernux"] = infernux
    sys.modules["Infernux.debug"] = debug_mod
    sys.modules["Infernux.input"] = input_mod
    sys.modules["Infernux.lib"] = lib_mod

    spec = importlib.util.spec_from_file_location("PelletChaseController_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["PelletChaseController_test"] = module
    spec.loader.exec_module(module)
    return module.PelletChaseController


def test_horizontal_wall_segments_rotate_wall_sprite_90_degrees():
    controller = _load_controller_class()()

    assert controller._wall_rotation_z(0, 3) == 90.0
    assert controller._wall_rotation_z(3, 0) == 0.0


def test_wall_tiles_choose_sprites_from_wall_topology():
    controller = _load_controller_class()()
    controller.wall_sprite_guid = "straight"
    controller.wall_corner_sprite_guid = "corner"

    assert controller._wall_tile(0, 3) == ("straight", 90.0)
    assert controller._wall_tile(3, 0) == ("straight", 0.0)
    assert controller._wall_tile(0, 0) == ("straight", 90.0)
    assert controller._wall_tile(0, 6) == ("straight", 90.0)
    assert controller._wall_tile(2, 4) == ("corner", 180.0)


def test_wall_tiles_fall_back_to_straight_sprite_when_optional_sprites_missing():
    controller = _load_controller_class()()
    controller.wall_sprite_guid = "straight"
    controller.wall_corner_sprite_guid = ""

    assert controller._wall_tile(0, 0) == ("straight", 90.0)
    assert controller._wall_tile(0, 6) == ("straight", 90.0)


def test_input_x_axis_is_flipped_to_match_screen_direction():
    controller = _load_controller_class()()
    _Input.horizontal = 1.0
    _Input.vertical = -1.0

    move_x, move_y = controller._read_input_axes()

    assert move_x == -1.0
    assert move_y == -1.0


def test_wall_collision_checks_player_radius_not_only_center_cell():
    controller = _load_controller_class()()

    # Layout row 1 / col 6 is a wall. This center is still in open col 5, but
    # the player's right edge would overlap the wall and must be blocked.
    assert controller._is_open_area(1.55, 2.0) is False
    assert controller._is_open_area(1.0, 2.0) is True
