"""Internal coercion helpers shared by ai_runtime modules."""

from __future__ import annotations

from typing import Any


def coerce_vec3_tuple(value: Any) -> tuple[float, float, float] | None:
    """Coerce a Vec3-like value (Vector3 / sequence of 3 numbers) to a tuple."""
    if value is None or isinstance(value, (str, bytes)):
        return None

    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        try:
            return (float(value.x), float(value.y), float(value.z))
        except Exception:
            return None

    try:
        items = list(value)
    except Exception:
        return None

    if len(items) != 3:
        return None

    try:
        return (float(items[0]), float(items[1]), float(items[2]))
    except Exception:
        return None


__all__ = ["coerce_vec3_tuple"]
