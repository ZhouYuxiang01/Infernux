from __future__ import annotations

ALLOWED_COMPONENT_FIELDS: dict[str, set[str]] = {
    "Transform": {"position"},
    "Rigidbody": {"velocity", "mass"},
}

__all__ = [
    "ALLOWED_COMPONENT_FIELDS",
]
