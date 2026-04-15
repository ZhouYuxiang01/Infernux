from __future__ import annotations

import json
from pathlib import Path

from Infernux import *


class BallTelemetryProbe(InxComponent):
    write_interval_frames = 2

    def awake(self):
        self._frame = 0
        self._telemetry_path = Path(__file__).resolve().parents[2] / "Temp" / "ai_parameter_tuning_state.json"
        try:
            self._telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _write_telemetry(self, settled: bool = False) -> None:
        try:
            rb = self.game_object.get_component("Rigidbody")
        except Exception:
            rb = None

        position = self.game_object.transform.position
        velocity = getattr(rb, "velocity", Vector3(0.0, 0.0, 0.0)) if rb is not None else Vector3(0.0, 0.0, 0.0)

        payload = {
            "frame": int(self._frame),
            "position": [float(position.x), float(position.y), float(position.z)],
            "velocity": [float(velocity.x), float(velocity.y), float(velocity.z)],
            "speed": float((velocity.x * velocity.x + velocity.z * velocity.z) ** 0.5),
            "settled": bool(settled),
        }

        try:
            tmp_path = self._telemetry_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload), encoding="utf-8")
            tmp_path.replace(self._telemetry_path)
        except Exception:
            try:
                self._telemetry_path.write_text(json.dumps(payload), encoding="utf-8")
            except Exception:
                pass

    def update(self, delta_time: float):
        self._frame += 1
        if self._frame == 1 or self._frame % int(self.write_interval_frames) == 0:
            self._write_telemetry(settled=False)

    def on_disable(self):
        self._write_telemetry(settled=True)

    def on_destroy(self):
        self._write_telemetry(settled=True)

