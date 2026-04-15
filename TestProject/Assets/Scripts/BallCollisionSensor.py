from Infernux import *
from Infernux.debug import Debug


class BallCollisionSensor(InxComponent):
    collision_count = 0
    last_wall_name = None
    last_contact_normal = None
    last_contact_point = None
    last_relative_velocity = None
    last_impulse = 0.0

    def awake(self):
        self.collision_count = 0
        self.last_wall_name = None
        self.last_contact_normal = None
        self.last_contact_point = None
        self.last_relative_velocity = None
        self.last_impulse = 0.0

    def on_collision_enter(self, collision):
        self.collision_count += 1
        self.last_wall_name = getattr(getattr(collision, "game_object", None), "name", None)
        self.last_contact_normal = getattr(collision, "contact_normal", None)
        self.last_contact_point = getattr(collision, "contact_point", None)
        self.last_relative_velocity = getattr(collision, "relative_velocity", None)
        self.last_impulse = float(getattr(collision, "impulse", 0.0) or 0.0)

        Debug.log(
            "BallCollisionSensor: "
            f"hit={self.last_wall_name} "
            f"count={self.collision_count} "
            f"normal={self.last_contact_normal} point={self.last_contact_point} "
            f"impulse={self.last_impulse:.3f}"
        )
