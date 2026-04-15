from Infernux import *
from Infernux.debug import Debug
from Infernux.components.builtin import Rigidbody


class BallLaunchController(InxComponent):
    speed = 3.0
    direction_x = 1.0
    direction_z = 0.0

    def awake(self):
        self._rb = None
        self._frame = 0

    def start(self):
        self._rb = self.game_object.get_component(Rigidbody)
        if self._rb is None:
            Debug.log_error("BallLaunchController: Rigidbody missing")
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
        direction = Vector3(float(self.direction_x), 0.0, float(self.direction_z))
        magnitude = (direction.x * direction.x + direction.z * direction.z) ** 0.5
        if magnitude > 1e-5:
            direction = direction / magnitude

        current_position = self.game_object.transform.position
        next_position = Vector3(
            current_position.x + direction.x * float(self.speed) * delta_time,
            current_position.y,
            current_position.z + direction.z * float(self.speed) * delta_time,
        )
        self._rb.move_position(next_position)

        if self._frame <= 5 or self._frame % 60 == 0:
            Debug.log(
                "BallLaunchController: "
                f"frame={self._frame} speed={float(self.speed):.3f} "
                f"position=({self.game_object.transform.position.x:.3f}, "
                f"{self.game_object.transform.position.y:.3f}, "
                f"{self.game_object.transform.position.z:.3f})"
            )
