from __future__ import annotations

from Infernux.ai_runtime import (
    EntityActivitySummary,
    EntitySnapshot,
    get_entity_activity_summary,
    get_entity_snapshot,
    get_entity_snapshot_by_name,
)
import Infernux.ai_runtime.entity_observation as entity_observation
from Infernux.lib import Vector3


def test_get_entity_snapshot_success(scene):
    go = scene.create_game_object("Observed")
    go.transform.position = Vector3(1.0, 2.0, 3.0)
    rb = go.add_component("Rigidbody")

    snapshot = get_entity_snapshot(go.id)

    assert isinstance(snapshot, EntitySnapshot)
    assert snapshot.entity_id == go.id
    assert snapshot.name == "Observed"
    assert snapshot.position == (1.0, 2.0, 3.0)
    assert snapshot.velocity is not None
    assert "Transform" in snapshot.component_types
    assert "Rigidbody" in snapshot.component_types


def test_get_entity_snapshot_failure(scene):
    assert get_entity_snapshot(9_999_999_999) is None


def test_get_entity_snapshot_by_name_success(scene):
    go = scene.create_game_object("ByName")
    go.transform.position = Vector3(4.0, 5.0, 6.0)

    snapshot = get_entity_snapshot_by_name("ByName")

    assert isinstance(snapshot, EntitySnapshot)
    assert snapshot is not None
    assert snapshot.entity_id == go.id
    assert snapshot.name == "ByName"
    assert snapshot.position == (4.0, 5.0, 6.0)


def test_get_entity_snapshot_by_name_failure(scene):
    assert get_entity_snapshot_by_name("MissingName") is None


def test_get_entity_activity_summary_basic_statistics(monkeypatch):
    entity_id = 7
    events = [
        {"type": "PlayModeStart", "source_entity_id": None, "target_entity_id": None, "payload": {}},
        {"type": "InputInjected", "source_entity_id": entity_id, "target_entity_id": None, "payload": {"action": "move"}},
        {"type": "CollisionEnter", "source_entity_id": 8, "target_entity_id": entity_id, "payload": {}},
        {"type": "TriggerExit", "source_entity_id": 9, "target_entity_id": 10, "payload": {}},
    ]

    monkeypatch.setattr(entity_observation._event_stream, "get_recent_events", lambda ms: list(events))
    monkeypatch.setattr(
        entity_observation,
        "get_entity_snapshot",
        lambda eid: EntitySnapshot(
            entity_id=eid,
            name="Observed",
            position=(1.0, 0.0, 0.0),
            velocity=(0.25, 0.0, 0.0),
            component_types=["Transform", "Rigidbody"],
        ),
    )

    summary = get_entity_activity_summary(entity_id, 2000)

    assert isinstance(summary, EntityActivitySummary)
    assert summary.entity_id == entity_id
    assert summary.event_count == 2
    assert summary.collision_count == 1
    assert summary.moved is True

