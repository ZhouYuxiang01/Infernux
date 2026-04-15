from __future__ import annotations

import Infernux.ai_runtime.world_state as world_state
from Infernux.ai_runtime import EntityRecord, get_entity, list_entities
from Infernux.lib import Vector3


def test_list_entities_returns_entity_records(scene):
    root = scene.create_game_object("Root")
    root.transform.position = Vector3(1, 2, 3)
    root.add_component("Rigidbody")

    child = scene.create_game_object("Child")
    child.set_parent(root)

    entities = list_entities()

    assert isinstance(entities, list)
    assert all(isinstance(entity, EntityRecord) for entity in entities)
    assert {entity.name for entity in entities} >= {"Root", "Child"}


def test_get_entity_returns_parent_child_relationship(scene):
    root = scene.create_game_object("Parent")
    child = scene.create_game_object("Leaf")
    child.set_parent(root)

    entity = get_entity(root.id)
    assert entity is not None
    assert entity.id == root.id
    assert entity.parent_id is None
    assert child.id in entity.children_ids
    assert "Transform" in entity.component_types

    child_entity = get_entity(child.id)
    assert child_entity is not None
    assert child_entity.parent_id == root.id


def test_transform_is_present_in_component_types(scene):
    go = scene.create_game_object("TransformCheck")
    entity = get_entity(go.id)

    assert entity is not None
    assert "Transform" in entity.component_types


def test_world_state_normalizes_component_names_and_skips_invalid_ids(monkeypatch):
    class _FakeComponent:
        def __init__(self, type_name):
            self.type_name = type_name

    class _BadObject:
        id = None
        name = "Bad"

        def get_parent(self):
            return None

        def get_children(self):
            return []

        def get_components(self):
            return [_FakeComponent("game.components.Rigidbody")]

        def get_py_components(self):
            return [_FakeComponent("Infernux.MyScript")]

    class _GoodObject:
        id = 42
        name = "Good"

        def get_parent(self):
            return None

        def get_children(self):
            return []

        def get_components(self):
            return [
                _FakeComponent("game.components.Rigidbody"),
                _FakeComponent("<class 'Infernux.Transform'>"),
            ]

        def get_py_components(self):
            return [_FakeComponent("Infernux.MyScript")]

    class _FakeScene:
        def get_all_objects(self):
            return [_BadObject(), _GoodObject()]

    monkeypatch.setattr(world_state, "_get_active_scene", lambda: _FakeScene())

    entities = list_entities()

    assert [entity.id for entity in entities] == [42]
    assert entities[0].component_types[0] == "Transform"
    assert "Rigidbody" in entities[0].component_types
    assert "MyScript" in entities[0].component_types
