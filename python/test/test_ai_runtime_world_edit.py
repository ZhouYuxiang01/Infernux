from __future__ import annotations

import Infernux.ai_runtime.world_edit as world_edit
from Infernux.lib import Vector3


def _vec3_tuple(value):
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return (float(value.x), float(value.y), float(value.z))
    return tuple(value)


def test_move_entity_success(scene):
    go = scene.create_game_object("Mover")
    go.transform.position = Vector3(0, 0, 0)

    assert world_edit.move_entity(go.id, (1.0, 2.0, 3.0)) is True
    assert _vec3_tuple(go.transform.position) == (1.0, 2.0, 3.0)


def test_move_entity_fails_for_missing_entity(scene):
    assert world_edit.move_entity(9_999_999_999, (1.0, 2.0, 3.0)) is False


def test_move_entity_fails_without_transform(monkeypatch):
    class _NoTransformObject:
        def get_component(self, component_type):
            if component_type == "Transform":
                return None
            return None

    class _FakeScene:
        def find_by_id(self, entity_id):
            return _NoTransformObject() if entity_id == 7 else None

    monkeypatch.setattr(world_edit, "_get_active_scene", lambda: _FakeScene())

    assert world_edit.move_entity(7, (1.0, 2.0, 3.0)) is False


def test_set_component_success_velocity(monkeypatch):
    class _VelocityComponent:
        def __init__(self):
            self.velocity = None

    class _VelocityObject:
        def __init__(self):
            self.component = _VelocityComponent()

        def get_component(self, component_type):
            return self.component if component_type == "Rigidbody" else None

    class _FakeScene:
        def find_by_id(self, entity_id):
            return _VelocityObject() if entity_id == 21 else None

    monkeypatch.setattr(world_edit, "_get_active_scene", lambda: _FakeScene())

    assert world_edit.set_component(21, "velocity", (1.0, 0.0, 0.0)) is True


def test_set_component_rejects_non_whitelist_field(scene):
    go = scene.create_game_object("Body")
    go.add_component("Rigidbody")

    assert world_edit.set_component(go.id, "random_field", 123) is False


def test_set_component_success_mass(scene):
    go = scene.create_game_object("Body")
    rb = go.add_component("Rigidbody")

    assert world_edit.set_component(go.id, "mass", 3.5) is True
    assert rb.mass == 3.5


def test_set_component_rejects_missing_component(monkeypatch):
    class _NoRigidbodyObject:
        def get_component(self, component_type):
            return None

    class _FakeScene:
        def find_by_id(self, entity_id):
            return _NoRigidbodyObject() if entity_id == 11 else None

    monkeypatch.setattr(world_edit, "_get_active_scene", lambda: _FakeScene())

    assert world_edit.set_component(11, "velocity", (1.0, 0.0, 0.0)) is False


def test_set_component_rejects_invalid_entity(scene):
    assert world_edit.set_component(9_999_999_999, "velocity", (1.0, 0.0, 0.0)) is False
