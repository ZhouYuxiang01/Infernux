from Infernux import *
from Infernux.debug import Debug
from Infernux.input import Input
from Infernux.lib import SceneManager


class PelletChaseController(InxComponent):
    player_name = "PelletChase_Player"
    ghost_name = "PelletChase_Ghost"
    pellet_prefix = "PelletChase_Pellet_"
    wall_sprite_guid = ""
    pellet_sprite_guid = ""
    player_sprite_guid = ""
    ghost_sprite_guid = ""
    cell_size = 1.0
    player_speed = 4.0
    ghost_speed = 1.4
    collect_radius = 0.42
    hit_radius = 0.55

    score = 0
    pellets_remaining = 0
    game_over = False
    won = False
    status = "not_started"
    player_cell = ""
    ghost_cell = ""

    _LAYOUT = (
        "#########",
        "#P....#.#",
        "#.###.#.#",
        "#...#...#",
        "#.#...#.#",
        "#..#..G.#",
        "#########",
    )

    def awake(self):
        self._player = None
        self._ghost = None
        self._pellets = []
        self._last_status = ""

    def start(self):
        self.score = 0
        self.game_over = False
        self.won = False
        self.status = "running"
        scene = SceneManager.instance().get_active_scene()
        if scene is None:
            self._fail_setup("no active scene")
            return

        if scene.find(self.player_name) is None:
            self._spawn_board(scene)

        self._player = scene.find(self.player_name)
        self._ghost = scene.find(self.ghost_name)
        self._pellets = [
            obj for obj in scene.get_all_objects()
            if str(getattr(obj, "name", "")).startswith(self.pellet_prefix)
        ]
        for pellet in self._pellets:
            pellet.active = True

        self.pellets_remaining = len(self._pellets)
        if self._player is None or self._ghost is None:
            self._fail_setup("missing player or ghost object")
            return

        self._update_cells()
        Debug.log(
            "Pellet Chase ready: "
            f"{self.pellets_remaining} pellets, player={self.player_cell}, ghost={self.ghost_cell}"
        )

    def late_update(self, delta_time: float):
        if self.game_over:
            return
        if self._player is None or self._ghost is None:
            self._resolve_references()
            if self._player is None or self._ghost is None:
                self._fail_setup("lost player or ghost object")
                return

        dt = min(max(float(delta_time), 0.0), 0.05)
        self._move_player(dt)
        self._move_ghost(dt)
        self._collect_pellets()
        self._update_cells()
        self._check_terminal_state()

    def _resolve_references(self):
        scene = SceneManager.instance().get_active_scene()
        if scene is None:
            return
        self._player = scene.find(self.player_name)
        self._ghost = scene.find(self.ghost_name)

    def _spawn_board(self, scene):
        pellet_index = 0
        for row, line in enumerate(self._LAYOUT):
            for col, char in enumerate(line):
                if char == "#":
                    self._spawn_sprite(
                        scene,
                        f"PelletChase_Wall_{row:02d}_{col:02d}",
                        row,
                        col,
                        0.0,
                        1.0,
                        self.wall_sprite_guid,
                    )
                elif char == ".":
                    self._spawn_sprite(
                        scene,
                        f"PelletChase_Pellet_{pellet_index:03d}",
                        row,
                        col,
                        -0.05,
                        0.25,
                        self.pellet_sprite_guid,
                    )
                    pellet_index += 1
                elif char == "P":
                    self._spawn_sprite(scene, self.player_name, row, col, -0.1, 0.75, self.player_sprite_guid)
                elif char == "G":
                    self._spawn_sprite(scene, self.ghost_name, row, col, -0.12, 0.78, self.ghost_sprite_guid)

    def _spawn_sprite(self, scene, name: str, row: int, col: int, z: float, scale: float, sprite_guid: str):
        obj = scene.create_game_object(name)
        if obj is None:
            return None
        try:
            obj.set_parent(self.game_object, True)
        except Exception:
            pass
        pos = self._cell_to_world(row, col, z)
        obj.transform.position = pos
        obj.transform.local_scale = Vector3(scale, scale, scale)
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

    def _move_player(self, dt: float):
        move_x = float(Input.get_axis_raw("Horizontal"))
        move_y = float(Input.get_axis_raw("Vertical"))
        if abs(move_x) < 0.01 and abs(move_y) < 0.01:
            return

        length = max((move_x * move_x + move_y * move_y) ** 0.5, 1.0)
        step_x = (move_x / length) * self.player_speed * dt
        step_y = (move_y / length) * self.player_speed * dt
        self._try_move(self._player, step_x, step_y)

    def _move_ghost(self, dt: float):
        gp = self._ghost.transform.position
        pp = self._player.transform.position
        dx = pp.x - gp.x
        dy = pp.y - gp.y
        primary = (1.0 if dx > 0 else -1.0, 0.0) if abs(dx) >= abs(dy) else (0.0, 1.0 if dy > 0 else -1.0)
        secondary = (0.0, 1.0 if dy > 0 else -1.0) if primary[0] else (1.0 if dx > 0 else -1.0, 0.0)
        candidates = (primary, secondary, (-primary[0], -primary[1]), (-secondary[0], -secondary[1]))
        step = self.ghost_speed * dt
        for cx, cy in candidates:
            if self._can_move(self._ghost, cx * step, cy * step):
                self._try_move(self._ghost, cx * step, cy * step)
                return

    def _try_move(self, obj, dx: float, dy: float):
        pos = obj.transform.position
        next_x = pos.x + dx
        next_y = pos.y + dy
        moved_x = False
        moved_y = False
        if self._is_open_position(next_x, pos.y):
            pos = Vector3(next_x, pos.y, pos.z)
            moved_x = True
        if self._is_open_position(pos.x, next_y):
            pos = Vector3(pos.x, next_y, pos.z)
            moved_y = True
        if moved_x or moved_y:
            obj.transform.position = pos

    def _can_move(self, obj, dx: float, dy: float) -> bool:
        pos = obj.transform.position
        return self._is_open_position(pos.x + dx, pos.y + dy)

    def _collect_pellets(self):
        collected = 0
        player_pos = self._player.transform.position
        for pellet in self._pellets:
            if not bool(getattr(pellet, "active", True)):
                continue
            pellet_pos = pellet.transform.position
            if self._distance_xy(player_pos, pellet_pos) <= self.collect_radius:
                pellet.active = False
                collected += 1

        if collected:
            self.score += collected * 10
            self.pellets_remaining = max(0, self.pellets_remaining - collected)
            Debug.log(f"Pellet Chase collected {collected}; score={self.score}; left={self.pellets_remaining}")

    def _check_terminal_state(self):
        if self.pellets_remaining <= 0:
            self.won = True
            self.game_over = True
            self.status = "won"
            self._log_status_once("won")
            return
        if self._distance_xy(self._player.transform.position, self._ghost.transform.position) <= self.hit_radius:
            self.won = False
            self.game_over = True
            self.status = "caught"
            self._log_status_once("caught")

    def _log_status_once(self, status: str):
        if self._last_status != status:
            self._last_status = status
            Debug.log(f"Pellet Chase finished: {status}; score={self.score}")

    def _fail_setup(self, reason: str):
        self.game_over = True
        self.won = False
        self.status = f"setup_error:{reason}"
        Debug.log_warning(f"Pellet Chase setup error: {reason}")

    def _update_cells(self):
        if self._player is not None:
            self.player_cell = self._format_cell(self._world_to_cell(self._player.transform.position))
        if self._ghost is not None:
            self.ghost_cell = self._format_cell(self._world_to_cell(self._ghost.transform.position))

    def _is_open_position(self, x: float, y: float) -> bool:
        row, col = self._world_xy_to_cell(x, y)
        if row < 0 or row >= len(self._LAYOUT):
            return False
        if col < 0 or col >= len(self._LAYOUT[row]):
            return False
        return self._LAYOUT[row][col] != "#"

    def _cell_to_world(self, row: int, col: int, z: float):
        width = len(self._LAYOUT[0])
        height = len(self._LAYOUT)
        x = (int(col) - (width - 1) * 0.5) * self.cell_size
        y = ((height - 1) * 0.5 - int(row)) * self.cell_size
        return Vector3(float(x), float(y), float(z))

    def _world_to_cell(self, position):
        return self._world_xy_to_cell(position.x, position.y)

    def _world_xy_to_cell(self, x: float, y: float):
        width = len(self._LAYOUT[0])
        height = len(self._LAYOUT)
        col = int(round(float(x) / self.cell_size + (width - 1) * 0.5))
        row = int(round((height - 1) * 0.5 - float(y) / self.cell_size))
        return row, col

    def _format_cell(self, cell) -> str:
        return f"{int(cell[0])},{int(cell[1])}"

    def _distance_xy(self, a, b) -> float:
        dx = float(a.x) - float(b.x)
        dy = float(a.y) - float(b.y)
        return (dx * dx + dy * dy) ** 0.5
