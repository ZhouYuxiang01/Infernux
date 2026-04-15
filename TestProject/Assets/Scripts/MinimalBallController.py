from Infernux import *
from Infernux.debug import Debug
from Infernux.input import Input
from Infernux.components.builtin import Rigidbody


class MinimalBallController(InxComponent):
    speed = 6.0

    def start(self):
        self._rb = self.game_object.get_component(Rigidbody)
        self._frame = 0
        if self._rb is None:
            Debug.log_error("MinimalBallController: Rigidbody missing")
            return

        self._rb.use_gravity = False
        self._rb.drag = 0.0
        self._rb.angular_drag = 0.05
        self._rb.is_kinematic = True
        self._rb.collision_detection_mode = 2

    def fixed_update(self, delta_time: float):
        if self._rb is None:
            return

        self._frame += 1
        move_x = float(Input.get_axis_raw("Horizontal"))
        move_z = float(Input.get_axis_raw("Vertical"))

        direction = Vector3(move_x, 0.0, move_z)
        magnitude = (direction.x * direction.x + direction.z * direction.z) ** 0.5
        if magnitude > 1e-5:
            direction = direction / magnitude
            current_position = self.game_object.transform.position
            next_position = Vector3(
                current_position.x + direction.x * self.speed * delta_time,
                current_position.y,
                current_position.z + direction.z * self.speed * delta_time,
            )
            self._rb.move_position(next_position)
        else:
            self._rb.move_position(self.game_object.transform.position)

        if self._frame <= 5 or self._frame % 60 == 0:
            Debug.log(
                "MinimalBallController: "
                f"frame={self._frame} input=({move_x:.3f}, {move_z:.3f}) "
                f"position=({self.game_object.transform.position.x:.3f}, "
                f"{self.game_object.transform.position.y:.3f}, "
                f"{self.game_object.transform.position.z:.3f})"
            )
