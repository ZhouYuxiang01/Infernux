import math

from Infernux import *
from Infernux.debug import Debug
from Infernux.lib import SceneManager

try:
    from scripts.voxel_sandbox_demo_support import (
        BLOCK_TYPES,
        CONTROL_ROUTE,
        WORLD_LAYOUT,
        block_type_for_char,
        cell_key,
        find_spawn_cell,
        is_solid_block,
        iter_layout_blocks,
        world_dimensions,
    )
except Exception:
    BLOCK_TYPES = ("air", "grass", "dirt", "stone", "wood", "leaf", "water")
    CONTROL_ROUTE = ()
    WORLD_LAYOUT = ()
    block_type_for_char = lambda char: "air"
    cell_key = lambda cell: f"{int(cell[0])},{int(cell[1])},{int(cell[2])}"
    find_spawn_cell = lambda layout=(): (2, 2, 3)
    is_solid_block = lambda block: str(block) not in {"air", "water"}
    iter_layout_blocks = lambda layout=(): ()
    world_dimensions = lambda layout=(): (16, 5, 12)


class VoxelSandboxController(InxComponent):
    block_prefix = "VoxelSandbox_Block_"
    player_name = "VoxelSandbox_Player"
    selection_name = "VoxelSandbox_Selection"
    camera_name = "VoxelSandbox_Camera"
    light_name = "VoxelSandbox_Sun"

    grass_texture_guid = ""
    dirt_texture_guid = ""
    stone_texture_guid = ""
    wood_texture_guid = ""
    leaf_texture_guid = ""
    water_texture_guid = ""

    player_cell = serialized_field(default="", group="Agent State")
    selected_cell = serialized_field(default="", group="Agent State")
    selected_block_type = serialized_field(default="", group="Agent State")
    blocks_placed = serialized_field(default=0, group="Agent State")
    blocks_removed = serialized_field(default=0, group="Agent State")
    inventory_slot = serialized_field(default=1, group="Agent State")
    status = serialized_field(default="not_started", group="Agent State")

    move_speed = 3.4
    turn_speed = 90.0
    selection_range = 5

    _COLOR_BY_BLOCK = {
        "grass": (0.30, 0.70, 0.28, 1.0),
        "dirt": (0.55, 0.34, 0.18, 1.0),
        "stone": (0.55, 0.58, 0.62, 1.0),
        "wood": (0.62, 0.36, 0.16, 1.0),
        "leaf": (0.24, 0.62, 0.30, 1.0),
        "water": (0.20, 0.48, 0.86, 0.72),
        "player": (1.0, 0.86, 0.16, 1.0),
        "selection": (1.0, 1.0, 1.0, 0.45),
    }

    def awake(self):
        self._blocks = {}
        self._block_types = {}
        self._materials = {}
        self._player = None
        self._selection = None
        self._camera = None
        self._last_mined_cell = None
        self._yaw = 0.0
        self._last_buttons = {}

    def start(self):
        self.blocks_placed = 0
        self.blocks_removed = 0
        self.inventory_slot = 1
        self.status = "running"
        self._blocks = {}
        self._block_types = {}
        self._materials = {}
        self._last_mined_cell = None
        self._yaw = 0.0
        self._last_buttons = {}

        scene = SceneManager.instance().get_active_scene()
        if scene is None:
            self._fail_setup("no active scene")
            return

        if scene.find(self.player_name) is None:
            self._spawn_world(scene)

        self._resolve_references(scene)
        if self._player is None:
            self._fail_setup("missing player")
            return

        self._rebuild_block_cache(scene)
        self._update_selection()
        self._update_public_state()
        Debug.log(
            "VoxelSandbox ready: "
            f"blocks={len(self._blocks)}, player={self.player_cell}, selected={self.selected_cell}"
        )

    def late_update(self, delta_time: float):
        if self.status.startswith("setup_error"):
            return
        if self._player is None:
            self._resolve_references(SceneManager.instance().get_active_scene())
            if self._player is None:
                self._fail_setup("lost player")
                return

        dt = min(max(float(delta_time), 0.0), 0.05)
        signal = self._read_control_signal()
        axes = getattr(signal, "axes", {}) or {}
        buttons = getattr(signal, "buttons", {}) or {}

        self._yaw += float(axes.get("look_x", 0.0)) * float(self.turn_speed) * dt
        self._move_player(
            float(axes.get("move_forward", 0.0)),
            float(axes.get("move_right", 0.0)),
            dt,
        )
        self._handle_inventory(buttons)
        self._update_selection()
        self._handle_block_actions(buttons)
        self._update_selection()
        self._update_camera()
        self._update_public_state()
        self._last_buttons = dict(buttons)

    def _spawn_world(self, scene):
        self._create_materials()
        root = self.game_object
        for cell, block_type in iter_layout_blocks(WORLD_LAYOUT):
            self._spawn_block(scene, root, cell, block_type)

        spawn = find_spawn_cell(WORLD_LAYOUT)
        self._player = scene.create_primitive(PrimitiveType.Cube, self.player_name)
        self._player.transform.position = Vector3(float(spawn[0]), float(spawn[1]) + 0.25, float(spawn[2]))
        self._player.transform.local_scale = Vector3(0.48, 0.95, 0.48)
        self._set_material(self._player, "player")
        try:
            self._player.set_parent(root, True)
        except Exception:
            pass

        self._selection = scene.create_primitive(PrimitiveType.Cube, self.selection_name)
        self._selection.transform.local_scale = Vector3(1.06, 1.06, 1.06)
        self._set_material(self._selection, "selection")
        try:
            self._selection.set_parent(root, True)
        except Exception:
            pass

        self._ensure_light(scene)

    def _spawn_block(self, scene, root, cell, block_type: str):
        name = self._block_name(cell, block_type)
        obj = scene.create_primitive(PrimitiveType.Cube, name)
        if obj is None:
            return None
        obj.transform.position = Vector3(float(cell[0]), float(cell[1]), float(cell[2]))
        obj.transform.local_scale = Vector3(1.0, 1.0, 1.0)
        self._set_material(obj, block_type)
        try:
            obj.add_component("BoxCollider")
        except Exception:
            pass
        try:
            obj.set_parent(root, True)
        except Exception:
            pass
        self._blocks[cell] = obj
        self._block_types[cell] = block_type
        return obj

    def _ensure_light(self, scene):
        light = scene.find(self.light_name)
        if light is None:
            light = scene.create_game_object(self.light_name)
            light.transform.position = Vector3(2.0, 9.0, 2.0)
            light.transform.euler_angles = Vector3(50.0, -35.0, 0.0)
            try:
                comp = light.add_component("Light")
                comp.intensity = 1.8
            except Exception:
                pass
            try:
                light.set_parent(self.game_object, True)
            except Exception:
                pass

    def _resolve_references(self, scene):
        if scene is None:
            return
        self._player = scene.find(self.player_name)
        self._selection = scene.find(self.selection_name)
        self._camera = scene.find(self.camera_name) or scene.find("Main Camera")

    def _rebuild_block_cache(self, scene):
        self._blocks = {}
        self._block_types = {}
        for obj in scene.get_all_objects():
            parsed = self._parse_block_name(str(getattr(obj, "name", "")))
            if parsed is None:
                continue
            cell, block_type = parsed
            if bool(getattr(obj, "active", True)):
                self._blocks[cell] = obj
                self._block_types[cell] = block_type

    def _move_player(self, forward: float, right: float, dt: float):
        if abs(forward) < 0.01 and abs(right) < 0.01:
            return
        yaw_rad = math.radians(float(self._yaw))
        dir_x = math.cos(yaw_rad)
        dir_z = math.sin(yaw_rad)
        right_x = -dir_z
        right_z = dir_x
        dx = (dir_x * forward + right_x * right) * float(self.move_speed) * dt
        dz = (dir_z * forward + right_z * right) * float(self.move_speed) * dt
        pos = self._player.transform.position
        next_pos = Vector3(pos.x + dx, pos.y, pos.z + dz)
        if self._can_stand_at(next_pos.x, next_pos.z):
            self._player.transform.position = next_pos

    def _can_stand_at(self, x: float, z: float) -> bool:
        cell = (int(round(x)), int(round(float(self._player.transform.position.y))), int(round(z)))
        block_type = self._block_types.get(cell, "air")
        if is_solid_block(block_type):
            return False
        width, height, depth = world_dimensions(WORLD_LAYOUT)
        return -0.5 <= x <= width - 0.5 and -0.5 <= z <= depth - 0.5 and height > 0

    def _handle_inventory(self, buttons):
        if self._pressed(buttons, "slot_next"):
            self.inventory_slot += 1
            if self.inventory_slot >= len(BLOCK_TYPES):
                self.inventory_slot = 1
        if self._pressed(buttons, "slot_prev"):
            self.inventory_slot -= 1
            if self.inventory_slot <= 0:
                self.inventory_slot = len(BLOCK_TYPES) - 1

    def _handle_block_actions(self, buttons):
        if self._pressed(buttons, "mine"):
            self._mine_selected()
        if self._pressed(buttons, "place"):
            self._place_selected()

    def _mine_selected(self):
        cell = self._selected_solid_cell()
        if cell is None:
            return
        obj = self._blocks.get(cell)
        if obj is None:
            return
        scene = SceneManager.instance().get_active_scene()
        if scene is not None:
            try:
                scene.destroy_game_object(obj)
                scene.process_pending_destroys()
            except Exception:
                try:
                    obj.active = False
                except Exception:
                    pass
        self._blocks.pop(cell, None)
        self._block_types.pop(cell, None)
        self._last_mined_cell = cell
        self.blocks_removed += 1
        Debug.log(f"VoxelSandbox mined block at {cell_key(cell)}")

    def _place_selected(self):
        scene = SceneManager.instance().get_active_scene()
        if scene is None:
            return
        cell = self._last_mined_cell or self._selected_air_cell()
        if cell is None or self._block_types.get(cell, "air") != "air":
            return
        if cell == self._player_cell_tuple():
            return
        block_type = self._inventory_block_type()
        self._spawn_block(scene, self.game_object, cell, block_type)
        self.blocks_placed += 1
        self._last_mined_cell = None
        Debug.log(f"VoxelSandbox placed {block_type} at {cell_key(cell)}")

    def _update_selection(self):
        target = self._selected_solid_cell()
        if target is None:
            target = self._selected_air_cell()
        if self._selection is not None and target is not None:
            self._selection.active = True
            self._selection.transform.position = Vector3(float(target[0]), float(target[1]), float(target[2]))
        elif self._selection is not None:
            self._selection.active = False

    def _selected_solid_cell(self):
        for cell in self._ray_cells():
            block_type = self._block_types.get(cell, "air")
            if is_solid_block(block_type):
                return cell
        return None

    def _selected_air_cell(self):
        last_air = None
        for cell in self._ray_cells():
            block_type = self._block_types.get(cell, "air")
            if is_solid_block(block_type):
                return last_air
            if block_type == "air":
                last_air = cell
        return last_air

    def _ray_cells(self):
        player_cell = self._player_cell_tuple()
        yaw_rad = math.radians(float(self._yaw))
        step_x = 1 if math.cos(yaw_rad) >= 0 else -1
        step_z = 1 if math.sin(yaw_rad) >= 0 else -1
        prefer_x = abs(math.cos(yaw_rad)) >= abs(math.sin(yaw_rad))
        width, height, depth = world_dimensions(WORLD_LAYOUT)
        for distance in range(1, int(self.selection_range) + 1):
            x = player_cell[0] + (step_x * distance if prefer_x else 0)
            z = player_cell[2] + (0 if prefer_x else step_z * distance)
            y = player_cell[1]
            if 0 <= x < width and 0 <= y < height and 0 <= z < depth:
                yield (x, y, z)

    def _update_camera(self):
        if self._camera is None or self._player is None:
            return
        p = self._player.transform.position
        yaw_rad = math.radians(float(self._yaw))
        back_x = -math.cos(yaw_rad) * 5.6
        back_z = -math.sin(yaw_rad) * 5.6
        self._camera.transform.position = Vector3(p.x + back_x, p.y + 5.2, p.z + back_z + 3.0)
        try:
            self._camera.transform.look_at(Vector3(p.x + 2.0, p.y + 0.3, p.z))
        except Exception:
            pass

    def _update_public_state(self):
        player_cell = self._player_cell_tuple()
        self.player_cell = cell_key(player_cell)
        selected = self._selected_solid_cell() or self._selected_air_cell()
        if selected is None:
            self.selected_cell = ""
            self.selected_block_type = ""
        else:
            self.selected_cell = cell_key(selected)
            self.selected_block_type = self._block_types.get(selected, "air")
        if not self.status.startswith("setup_error"):
            self.status = "running"

    def _read_control_signal(self):
        try:
            from Infernux.ai_runtime.control_signal import get_control_state

            return get_control_state(0)
        except Exception:
            return None

    def _pressed(self, buttons, name: str) -> bool:
        now = bool(buttons.get(name, False))
        before = bool(self._last_buttons.get(name, False))
        return now and not before

    def _inventory_block_type(self) -> str:
        slot = max(1, min(int(self.inventory_slot), len(BLOCK_TYPES) - 1))
        return str(BLOCK_TYPES[slot])

    def _player_cell_tuple(self):
        p = self._player.transform.position
        return (int(round(p.x)), int(round(p.y)), int(round(p.z)))

    def _create_materials(self):
        for block_type in BLOCK_TYPES:
            if block_type == "air":
                continue
            self._materials[block_type] = self._make_material(block_type)
        self._materials["player"] = self._make_material("player")
        self._materials["selection"] = self._make_material("selection")

    def _make_material(self, block_type: str):
        try:
            mat = Material.create_lit(f"VoxelSandbox_{block_type}")
            color = self._COLOR_BY_BLOCK.get(block_type, (1.0, 1.0, 1.0, 1.0))
            for prop in ("_BaseColor", "_Color", "baseColor"):
                try:
                    mat.set_color(prop, color[0], color[1], color[2], color[3])
                except Exception:
                    pass
            texture_guid = self._texture_guid_for(block_type)
            if texture_guid:
                for prop in ("_MainTex", "_BaseMap", "_Albedo"):
                    try:
                        mat.set_texture_guid(prop, texture_guid)
                    except Exception:
                        pass
            return mat
        except Exception:
            return None

    def _set_material(self, obj, block_type: str):
        material = self._materials.get(block_type)
        if material is None:
            return
        try:
            renderer = obj.get_component("MeshRenderer")
            if renderer is not None:
                renderer.set_material(material)
        except Exception:
            try:
                renderer.material = material
            except Exception:
                pass

    def _texture_guid_for(self, block_type: str) -> str:
        return str(getattr(self, f"{block_type}_texture_guid", "") or "")

    def _block_name(self, cell, block_type: str) -> str:
        return f"{self.block_prefix}{int(cell[0])}_{int(cell[1])}_{int(cell[2])}_{block_type}"

    def _parse_block_name(self, name: str):
        if not name.startswith(self.block_prefix):
            return None
        parts = name[len(self.block_prefix):].split("_")
        if len(parts) < 4:
            return None
        try:
            cell = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
        block_type = "_".join(parts[3:])
        return cell, block_type

    def _fail_setup(self, reason: str):
        self.status = f"setup_error:{reason}"
        Debug.log_warning(f"VoxelSandbox setup error: {reason}")
