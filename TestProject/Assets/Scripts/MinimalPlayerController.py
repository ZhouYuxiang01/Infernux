from Infernux import *
from Infernux.input import Input


class MinimalPlayerController(InxComponent):
    speed = 4.0

    def late_update(self, delta_time: float):
        move_x = Input.get_axis_raw("Horizontal")
        move_z = Input.get_axis_raw("Vertical")
        if move_x == 0.0 and move_z == 0.0:
            return

        pos = self.transform.position
        self.transform.position = Vector3(
            pos.x + move_x * self.speed * delta_time,
            pos.y,
            pos.z + move_z * self.speed * delta_time,
        )
