from __future__ import annotations

import Infernux.ai_runtime.query_api as query_api
import Infernux.ai_runtime.world_state as world_state
from Infernux.ai_runtime.types import EntityRecord


def test_query_api_delegates_entity_access(monkeypatch):
    entity = EntityRecord(
        id=7,
        name="Root",
        parent_id=None,
        children_ids=[],
        component_types=["Transform"],
    )

    monkeypatch.setattr(query_api._world_state, "list_entities", lambda: [entity])
    monkeypatch.setattr(query_api._world_state, "get_entity", lambda entity_id: entity if entity_id == 7 else None)

    assert query_api.list_entities() == [entity]
    assert query_api.get_entity(7) == entity
    assert query_api.get_entity(999) is None


def test_find_by_component_reuses_world_state_normalization(monkeypatch):
    def _norm(name):
        if name in {"game.components.Rigidbody", "Infernux.Rigidbody", "Rigidbody"}:
            return "Rigid"
        if name == "game.components.MeshRenderer":
            return "Render"
        return str(name)

    rigidbody_entity = EntityRecord(
        id=1,
        name="Mover",
        parent_id=None,
        children_ids=[],
        component_types=["Transform", "Rigidbody"],
    )
    other_entity = EntityRecord(
        id=2,
        name="Static",
        parent_id=None,
        children_ids=[],
        component_types=["Transform", "MeshRenderer"],
    )

    monkeypatch.setattr(world_state, "normalize_type_name", _norm)
    monkeypatch.setattr(query_api._world_state, "list_entities", lambda: [rigidbody_entity, other_entity])

    matches = query_api.find_by_component("game.components.Rigidbody")

    assert matches == [rigidbody_entity]


def test_find_in_radius_defensively_parses_physics_results(monkeypatch):
    class _FakeGameObject:
        def __init__(self, entity_id):
            self.id = entity_id

    class _FakeCollider:
        def __init__(self, entity_id):
            self.game_object = _FakeGameObject(entity_id)

    class _FakeWrapper:
        def __init__(self, entity_id):
            self._game_object = _FakeGameObject(entity_id)

        def get_game_object(self):
            return self._game_object

    class _InvalidResult:
        pass

    entity_one = EntityRecord(
        id=11,
        name="NearOne",
        parent_id=None,
        children_ids=[],
        component_types=["Transform"],
    )
    entity_two = EntityRecord(
        id=12,
        name="NearTwo",
        parent_id=None,
        children_ids=[],
        component_types=["Transform"],
    )

    monkeypatch.setattr(query_api, "Physics", type("_FakePhysics", (), {
        "overlap_sphere": staticmethod(lambda position, radius: [
            _FakeCollider(11),
            _FakeWrapper(12),
            _InvalidResult(),
            _FakeCollider(11),
        ])
    }))
    monkeypatch.setattr(query_api._world_state, "get_entity", lambda entity_id: {
        11: entity_one,
        12: entity_two,
    }.get(entity_id))

    matches = query_api.find_in_radius((0, 0, 0), 5.0)

    assert matches == [entity_one, entity_two]


def test_get_recent_events_returns_empty_list():
    assert query_api.get_recent_events(100) == []
