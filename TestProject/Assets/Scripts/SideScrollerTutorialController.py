from Infernux import *
from Infernux.debug import Debug
from Infernux.input import Input
from Infernux.lib import InputManager, SceneManager


try:
    from scripts.side_scroller_demo_support import LAYOUT as SHARED_LAYOUT
except Exception:
    SHARED_LAYOUT = (
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


class SideScrollerTutorialController(InxComponent):
    player_name = "SideScroller_Player"
    enemy_prefix = "SideScroller_Enemy_"
    coin_prefix = "SideScroller_Coin_"
    tile_prefix = "SideScroller_Tile_"
    reward_prefix = "SideScroller_Reward_"
    finish_name = "SideScroller_Finish"
    camera_name = "SideScroller_Camera"

    player_sprite_guid = ""
    player_walk_sprite_guid = ""
    enemy_sprite_guid = ""
    coin_sprite_guid = ""
    ground_sprite_guid = ""
    platform_sprite_guid = ""
    reward_block_sprite_guid = ""
    used_block_sprite_guid = ""
    finish_sprite_guid = ""

    cell_size = 1.0
    player_speed = 4.2
    jump_speed = 7.2
    gravity = -18.0
    max_fall_speed = -12.0
    player_half_width = 0.34
    player_half_height = 0.42
    enemy_half_width = 0.36
    enemy_half_height = 0.32
    enemy_speed = 1.2
    collect_radius = 0.55
    finish_radius = 0.75
    camera_lookahead = 2.5

    score = 0
    coins_remaining = 0
    enemies_defeated = 0
    reward_blocks_used = 0
    finished = False
    failed = False
    grounded = False
    status = "not_started"
    player_cell = ""
    finish_cell = ""

    _LAYOUT = SHARED_LAYOUT

    def awake(self):
        self._player = None
        self._camera = None
        self._finish = None
        self._coins = []
        self._enemies = []
        self._enemy_dirs = {}
        self._reward_blocks = {}
        self._velocity_y = 0.0
        self._jump_was_held = False
        self._last_status = ""

    def start(self):
        self.score = 0
        self.coins_remaining = 0
        self.enemies_defeated = 0
        self.reward_blocks_used = 0
        self.finished = False
        self.failed = False
        self.grounded = False
        self.status = "running"
        self._velocity_y = 0.0
        self._jump_was_held = False
        self._enemy_dirs = {}
        self._reward_blocks = {}

        scene = SceneManager.instance().get_active_scene()
        if scene is None:
            self._fail_setup("no active scene")
            return

        if scene.find(self.player_name) is None:
            self._spawn_level(scene)

        self._resolve_references(scene)
        if self._player is None or self._finish is None:
            self._fail_setup("missing player or finish object")
            return

        self.coins_remaining = len([coin for coin in self._coins if bool(getattr(coin, "active", True))])
        self._update_cells()
        Debug.log(
            "SideScrollerTutorial ready: "
            f"coins={self.coins_remaining}, enemies={len(self._enemies)}, player={self.player_cell}, finish={self.finish_cell}"
        )

    def late_update(self, delta_time: float):
        if self.finished or self.failed:
            self._update_camera()
            return

        scene = SceneManager.instance().get_active_scene()
        if self._player is None or self._finish is None:
            self._resolve_references(scene)
            if self._player is None or self._finish is None:
                self._fail_setup("lost player or finish object")
                return

        dt = min(max(float(delta_time), 0.0), 0.05)
        self._update_player(dt)
        self._update_enemies(dt)
        self._collect_coins()
        self._check_enemy_contacts()
        self._check_finish()
        self._update_cells()
        self._update_camera()

    def _spawn_level(self, scene):
        coin_index = 0
        enemy_index = 0
        for row, line in enumerate(self._LAYOUT):
            for col, char in enumerate(line):
                if char == "#":
                    self._spawn_sprite(
                        scene,
                        f"{self.tile_prefix}{row:02d}_{col:02d}",
                        row,
                        col,
                        0.0,
                        1.0,
                        self._tile_sprite(row, col),
                    )
                elif char == "?":
                    obj = self._spawn_sprite(
                        scene,
                        f"{self.reward_prefix}{row:02d}_{col:02d}",
                        row,
                        col,
                        -0.02,
                        1.0,
                        self.reward_block_sprite_guid,
                    )
                    if obj is not None:
                        self._reward_blocks[(row, col)] = {"object": obj, "used": False}
                elif char == "C":
                    self._spawn_sprite(
                        scene,
                        f"{self.coin_prefix}{coin_index:03d}",
                        row,
                        col,
                        -0.10,
                        0.55,
                        self.coin_sprite_guid,
                    )
                    coin_index += 1
                elif char == "E":
                    enemy = self._spawn_sprite(
                        scene,
                        f"{self.enemy_prefix}{enemy_index:03d}",
                        row,
                        col,
                        -0.13,
                        0.82,
                        self.enemy_sprite_guid,
                    )
                    if enemy is not None:
                        self._enemy_dirs[getattr(enemy, "id", enemy_index)] = -1.0
                    enemy_index += 1
                elif char == "P":
                    self._spawn_sprite(scene, self.player_name, row, col, -0.20, 0.90, self.player_sprite_guid)
                elif char == "F":
                    self._spawn_sprite(scene, self.finish_name, row, col, -0.12, 1.15, self.finish_sprite_guid)

    def _spawn_sprite(self, scene, name: str, row: int, col: int, z: float, scale: float, sprite_guid: str):
        pos = self._cell_to_world(row, col, z)
        return self._spawn_raw_sprite(scene, name, pos.x, pos.y, pos.z, scale, sprite_guid)

    def _spawn_raw_sprite(self, scene, name: str, x: float, y: float, z: float, scale: float, sprite_guid: str):
        obj = scene.create_game_object(name)
        if obj is None:
            return None
        try:
            obj.set_parent(self.game_object, True)
        except Exception:
            pass
        obj.transform.position = Vector3(float(x), float(y), float(z))
        obj.transform.local_scale = Vector3(float(scale), float(scale), float(scale))
        cpp_renderer = obj.add_component("SpriteRenderer")
        if cpp_renderer is not None and sprite_guid:
            try:
                from Infernux.components.builtin.sprite_renderer import SpriteRenderer

                wrapper = SpriteRenderer._get_or_create_wrapper(cpp_renderer, obj)
                wrapper.sprite = sprite_guid
            except Exception:
                try:
                    cpp_renderer.sprite_guid = sprite_guid
                except Exception:
                    pass
        return obj

    def _resolve_references(self, scene):
        if scene is None:
            return
        self._player = scene.find(self.player_name)
        self._finish = scene.find(self.finish_name)
        self._camera = scene.find(self.camera_name) or scene.find("Main Camera")
        objects = scene.get_all_objects()
        self._coins = [obj for obj in objects if str(getattr(obj, "name", "")).startswith(self.coin_prefix)]
        self._enemies = [obj for obj in objects if str(getattr(obj, "name", "")).startswith(self.enemy_prefix)]

    def _update_player(self, dt: float):
        move_x = float(Input.get_axis_raw("Horizontal"))
        jump_held = self._read_jump_held()
        jump_pressed = jump_held and not self._jump_was_held
        self._jump_was_held = jump_held

        if jump_pressed and self.grounded:
            self._velocity_y = float(self.jump_speed)
            self.grounded = False

        self._velocity_y = max(float(self.max_fall_speed), self._velocity_y + float(self.gravity) * dt)
        pos = self._player.transform.position
        next_x = pos.x + move_x * float(self.player_speed) * dt
        if self._area_clear(next_x, pos.y, self.player_half_width, self.player_half_height):
            pos = Vector3(next_x, pos.y, pos.z)
        elif abs(move_x) > 0.01:
            self._set_player_walk_sprite(False)

        next_y = pos.y + self._velocity_y * dt
        if self._area_clear(pos.x, next_y, self.player_half_width, self.player_half_height):
            pos = Vector3(pos.x, next_y, pos.z)
            self.grounded = False
        else:
            if self._velocity_y > 0.0:
                self._hit_reward_above(pos.x, pos.y)
            elif self._velocity_y < 0.0:
                self.grounded = True
            self._velocity_y = 0.0

        self._player.transform.position = pos
        self._set_player_walk_sprite(abs(move_x) > 0.05)
        if pos.y < -2.0:
            self.failed = True
            self.status = "fell"
            self._log_status_once("fell")

    def _read_jump_held(self) -> bool:
        try:
            manager = InputManager.instance()
            virtual_state = getattr(manager, "virtual_input_state", None)
            channel_state = getattr(manager, "channel_virtual_input_state", None)
            if bool(getattr(virtual_state, "jump", False)) or bool(getattr(channel_state, "jump", False)):
                return True
        except Exception:
            pass
        try:
            return bool(Input.get_key("space"))
        except Exception:
            return False

    def _set_player_walk_sprite(self, walking: bool):
        if self._player is None:
            return
        guid = self.player_walk_sprite_guid if walking and self.player_walk_sprite_guid else self.player_sprite_guid
        if not guid:
            return
        try:
            from Infernux.components.builtin.sprite_renderer import SpriteRenderer

            renderer = self._player.get_component("SpriteRenderer")
            wrapper = SpriteRenderer._get_or_create_wrapper(renderer, self._player)
            wrapper.sprite = guid
        except Exception:
            pass

    def _update_enemies(self, dt: float):
        for enemy in self._enemies:
            if not bool(getattr(enemy, "active", True)):
                continue
            key = getattr(enemy, "id", id(enemy))
            direction = float(self._enemy_dirs.get(key, -1.0))
            pos = enemy.transform.position
            step = direction * float(self.enemy_speed) * dt
            next_x = pos.x + step
            if self._area_clear(next_x, pos.y, self.enemy_half_width, self.enemy_half_height) and self._has_floor_ahead(next_x, pos.y, direction):
                enemy.transform.position = Vector3(next_x, pos.y, pos.z)
            else:
                self._enemy_dirs[key] = -direction

    def _has_floor_ahead(self, x: float, y: float, direction: float) -> bool:
        probe_x = float(x) + float(direction) * (float(self.enemy_half_width) + 0.15)
        probe_y = float(y) - float(self.enemy_half_height) - 0.12
        row, col = self._world_xy_to_cell(probe_x, probe_y)
        return self._is_solid_cell(row, col)

    def _collect_coins(self):
        collected = 0
        player_pos = self._player.transform.position
        for coin in self._coins:
            if not bool(getattr(coin, "active", True)):
                continue
            if self._distance_xy(player_pos, coin.transform.position) <= float(self.collect_radius):
                coin.active = False
                collected += 1
        if collected:
            self.score += collected * 10
            self.coins_remaining = max(0, self.coins_remaining - collected)
            Debug.log(f"SideScrollerTutorial collected {collected}; score={self.score}; left={self.coins_remaining}")

    def _check_enemy_contacts(self):
        player_pos = self._player.transform.position
        for enemy in self._enemies:
            if not bool(getattr(enemy, "active", True)):
                continue
            enemy_pos = enemy.transform.position
            if abs(player_pos.x - enemy_pos.x) > 0.62 or abs(player_pos.y - enemy_pos.y) > 0.70:
                continue
            if player_pos.y > enemy_pos.y + 0.45:
                enemy.active = False
                self.enemies_defeated += 1
                self.score += 50
                self._velocity_y = float(self.jump_speed) * 0.45
                Debug.log(f"SideScrollerTutorial defeated enemy; score={self.score}")
            else:
                self.failed = True
                self.status = "hurt"
                self._log_status_once("hurt")
                return

    def _check_finish(self):
        if self._finish is None:
            return
        if self._distance_xy(self._player.transform.position, self._finish.transform.position) <= float(self.finish_radius):
            self.finished = True
            self.status = "finished"
            self.score += 100
            self._log_status_once("finished")

    def _hit_reward_above(self, x: float, y: float):
        top_y = float(y) + float(self.player_half_height) + 0.05
        for offset_x in (-self.player_half_width * 0.6, 0.0, self.player_half_width * 0.6):
            row, col = self._world_xy_to_cell(float(x) + offset_x, top_y)
            data = self._reward_blocks.get((row, col))
            if not data or data.get("used"):
                continue
            data["used"] = True
            self.reward_blocks_used += 1
            self.score += 25
            obj = data.get("object")
            if obj is not None and self.used_block_sprite_guid:
                try:
                    from Infernux.components.builtin.sprite_renderer import SpriteRenderer

                    renderer = obj.get_component("SpriteRenderer")
                    wrapper = SpriteRenderer._get_or_create_wrapper(renderer, obj)
                    wrapper.sprite = self.used_block_sprite_guid
                except Exception:
                    pass
            Debug.log(f"SideScrollerTutorial reward block used; score={self.score}")
            return

    def _update_camera(self):
        if self._camera is None or self._player is None:
            return
        player_pos = self._player.transform.position
        max_x = max(8.0, len(self._LAYOUT[0]) - 8.0)
        camera_x = min(max(player_pos.x + float(self.camera_lookahead), 7.0), max_x)
        camera_y = 4.2
        self._camera.transform.position = Vector3(float(camera_x), float(camera_y), 18.0)

    def _area_clear(self, x: float, y: float, half_width: float, half_height: float) -> bool:
        samples = (
            (-half_width, -half_height),
            (half_width, -half_height),
            (-half_width, half_height),
            (half_width, half_height),
            (0.0, -half_height),
            (0.0, half_height),
        )
        for offset_x, offset_y in samples:
            row, col = self._world_xy_to_cell(float(x) + float(offset_x), float(y) + float(offset_y))
            if self._is_solid_cell(row, col):
                return False
        return True

    def _tile_sprite(self, row: int, col: int) -> str:
        if row >= len(self._LAYOUT) - 2:
            return self.ground_sprite_guid or self.platform_sprite_guid
        return self.platform_sprite_guid or self.ground_sprite_guid

    def _is_solid_cell(self, row: int, col: int) -> bool:
        if row < 0 or row >= len(self._LAYOUT):
            return True
        if col < 0 or col >= len(self._LAYOUT[row]):
            return True
        return self._LAYOUT[row][col] in ("#", "?")

    def _update_cells(self):
        if self._player is not None:
            self.player_cell = self._format_cell(self._world_to_cell(self._player.transform.position))
        if self._finish is not None:
            self.finish_cell = self._format_cell(self._world_to_cell(self._finish.transform.position))

    def _cell_to_world(self, row: int, col: int, z: float):
        x = int(col) * float(self.cell_size)
        y = (len(self._LAYOUT) - 1 - int(row)) * float(self.cell_size)
        return Vector3(float(x), float(y), float(z))

    def _world_to_cell(self, position):
        return self._world_xy_to_cell(position.x, position.y)

    def _world_xy_to_cell(self, x: float, y: float):
        col = int(round(float(x) / float(self.cell_size)))
        row = int(round((len(self._LAYOUT) - 1) - float(y) / float(self.cell_size)))
        return row, col

    def _format_cell(self, cell) -> str:
        return f"{int(cell[0])},{int(cell[1])}"

    def _distance_xy(self, a, b) -> float:
        dx = float(a.x) - float(b.x)
        dy = float(a.y) - float(b.y)
        return (dx * dx + dy * dy) ** 0.5

    def _log_status_once(self, status: str):
        if self._last_status != status:
            self._last_status = status
            Debug.log(f"SideScrollerTutorial status={status}; score={self.score}")

    def _fail_setup(self, reason: str):
        self.failed = True
        self.finished = False
        self.status = f"setup_error:{reason}"
        Debug.log_warning(f"SideScrollerTutorial setup error: {reason}")
