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

    assert world_edit.move_entity(go.id, (1.0, 2.0, 3.0)).ok is True
    assert _vec3_tuple(go.transform.position) == (1.0, 2.0, 3.0)


def test_move_entity_fails_for_missing_entity(scene):
    assert world_edit.move_entity(9_999_999_999, (1.0, 2.0, 3.0)).ok is False


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

    assert world_edit.move_entity(7, (1.0, 2.0, 3.0)).ok is False


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

    assert world_edit.set_component(21, "velocity", (1.0, 0.0, 0.0)).ok is True


def test_set_component_rejects_non_whitelist_field(scene):
    go = scene.create_game_object("Body")
    go.add_component("Rigidbody")

    assert world_edit.set_component(go.id, "random_field", 123).ok is False


def test_set_component_success_mass(scene):
    go = scene.create_game_object("Body")
    rb = go.add_component("Rigidbody")

    assert world_edit.set_component(go.id, "mass", 3.5).ok is True
    assert rb.mass == 3.5


def test_set_component_rejects_missing_component(monkeypatch):
    class _NoRigidbodyObject:
        def get_component(self, component_type):
            return None

    class _FakeScene:
        def find_by_id(self, entity_id):
            return _NoRigidbodyObject() if entity_id == 11 else None

    monkeypatch.setattr(world_edit, "_get_active_scene", lambda: _FakeScene())

    assert world_edit.set_component(11, "velocity", (1.0, 0.0, 0.0)).ok is False


def test_set_component_rejects_invalid_entity(scene):
    assert world_edit.set_component(9_999_999_999, "velocity", (1.0, 0.0, 0.0)).ok is False


# ---- mode policy ----------------------------------------------------------
#
# Mode rules under test:
#   - "runtime" requested in Edit Mode  → ok=False
#   - "edit"    requested in Play Mode  → ok=False
#   - "auto"    in Edit Mode            → uses Undo
#   - "auto"    in Play Mode            → direct setattr (no Undo)
#   - "edit"    when Undo unavailable   → ok=False (visible failure)


class _RecordingComponent:
    def __init__(self):
        self.velocity = None


def _install_fake_scene_with_rigidbody(monkeypatch, entity_id, component):
    class _Object:
        def get_component(self, name):
            return component if name == "Rigidbody" else None

    class _FakeScene:
        def find_by_id(self, ent):
            return _Object() if ent == entity_id else None

    monkeypatch.setattr(world_edit, "_get_active_scene", lambda: _FakeScene())


def test_mode_runtime_outside_play_mode_returns_error(monkeypatch):
    component = _RecordingComponent()
    _install_fake_scene_with_rigidbody(monkeypatch, 1, component)
    monkeypatch.setattr(world_edit, "_is_play_mode", lambda: False)

    result = world_edit.set_component(1, "velocity", (1.0, 0.0, 0.0), mode="runtime")
    assert result.ok is False
    assert result.message == "runtime mutation requested outside play mode"
    # No mutation took place.
    assert component.velocity is None


def test_mode_edit_inside_play_mode_returns_error(monkeypatch):
    component = _RecordingComponent()
    _install_fake_scene_with_rigidbody(monkeypatch, 1, component)
    monkeypatch.setattr(world_edit, "_is_play_mode", lambda: True)

    result = world_edit.set_component(1, "velocity", (1.0, 0.0, 0.0), mode="edit")
    assert result.ok is False
    assert result.message == "edit mode mutation requested while play mode is active"
    assert component.velocity is None


def test_mode_auto_in_edit_mode_attempts_undo(monkeypatch):
    component = _RecordingComponent()
    _install_fake_scene_with_rigidbody(monkeypatch, 1, component)
    monkeypatch.setattr(world_edit, "_is_play_mode", lambda: False)

    undo_calls = []

    def fake_undo(comp, key, old, new, label):
        undo_calls.append((key, new, label))
        comp.velocity = new
        return True

    monkeypatch.setattr(world_edit, "_apply_with_undo", fake_undo)

    result = world_edit.set_component(1, "velocity", (2.0, 0.0, 0.0), mode="auto")
    assert result.ok is True
    assert undo_calls and undo_calls[0][0] == "velocity"


def test_mode_auto_in_play_mode_skips_undo(monkeypatch):
    component = _RecordingComponent()
    _install_fake_scene_with_rigidbody(monkeypatch, 1, component)
    monkeypatch.setattr(world_edit, "_is_play_mode", lambda: True)

    def fail_undo(*_args, **_kwargs):
        raise AssertionError("auto-mode in Play Mode must not invoke undo")

    monkeypatch.setattr(world_edit, "_apply_with_undo", fail_undo)

    result = world_edit.set_component(1, "velocity", (3.0, 0.0, 0.0), mode="auto")
    assert result.ok is True
    # Direct mutation in Play Mode.
    assert _vec3_tuple(component.velocity) == (3.0, 0.0, 0.0)


def test_mode_edit_surfaces_undo_unavailable(monkeypatch):
    component = _RecordingComponent()
    _install_fake_scene_with_rigidbody(monkeypatch, 1, component)
    monkeypatch.setattr(world_edit, "_is_play_mode", lambda: False)
    # Undo cannot be recorded (no UndoManager, hook returns False).
    monkeypatch.setattr(world_edit, "_apply_with_undo", lambda *_a, **_k: False)

    result = world_edit.set_component(1, "velocity", (4.0, 0.0, 0.0), mode="edit")
    assert result.ok is False
    assert result.message == "undo unavailable in edit mode"
    # Importantly, no silent fallback mutation when caller asked for edit mode.
    assert component.velocity is None
