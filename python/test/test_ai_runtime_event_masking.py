from __future__ import annotations

from dataclasses import dataclass

import Infernux.ai_runtime.event_stream as event_stream


@dataclass
class _FakeCollector:
    events: list[dict]
    event_types: list[str] | None = None
    source_entity_ids: list[int] | None = None
    target_entity_ids: list[int] | None = None

    def set_event_filter(self, event_types=None, source_entity_ids=None, target_entity_ids=None):
        self.event_types = None if event_types is None else list(event_types)
        self.source_entity_ids = None if source_entity_ids is None else list(source_entity_ids)
        self.target_entity_ids = None if target_entity_ids is None else list(target_entity_ids)

    def clear_event_filter(self):
        self.event_types = None
        self.source_entity_ids = None
        self.target_entity_ids = None

    def get_recent_events(self, window_ms):
        _ = window_ms
        result = []
        for event in self.events:
            if self.event_types is not None and event["type"] not in self.event_types:
                continue
            if self.source_entity_ids is not None and event.get("source_entity_id") not in self.source_entity_ids:
                continue
            if self.target_entity_ids is not None and event.get("target_entity_id") not in self.target_entity_ids:
                continue
            result.append(event)
        return result


def _make_events():
    return [
        {
            "frame": 1,
            "timestamp": 10,
            "sequence": 0,
            "type": "PlayModeStart",
            "source_entity_id": None,
            "target_entity_id": None,
            "payload": {"state": "playing"},
        },
        {
            "frame": 2,
            "timestamp": 20,
            "sequence": 0,
            "type": "InputInjected",
            "source_entity_id": None,
            "target_entity_id": None,
            "payload": {"action": "jump"},
        },
        {
            "frame": 3,
            "timestamp": 30,
            "sequence": 0,
            "type": "CollisionEnter",
            "source_entity_id": 10,
            "target_entity_id": 20,
            "payload": {},
        },
        {
            "frame": 4,
            "timestamp": 40,
            "sequence": 0,
            "type": "CollisionEnter",
            "source_entity_id": 11,
            "target_entity_id": 20,
            "payload": {},
        },
        {
            "frame": 5,
            "timestamp": 50,
            "sequence": 0,
            "type": "CollisionEnter",
            "source_entity_id": 10,
            "target_entity_id": 21,
            "payload": {},
        },
    ]


def test_get_recent_events_without_filter(monkeypatch):
    collector = _FakeCollector(_make_events())
    monkeypatch.setattr(event_stream, "_get_native_collector", lambda: collector)

    events = event_stream.get_recent_events(100)

    assert [event["type"] for event in events] == [
        "PlayModeStart",
        "InputInjected",
        "CollisionEnter",
        "CollisionEnter",
        "CollisionEnter",
    ]


def test_filter_by_event_types(monkeypatch):
    collector = _FakeCollector(_make_events())
    monkeypatch.setattr(event_stream, "_get_native_collector", lambda: collector)

    event_stream.set_event_filter(event_types=["CollisionEnter"])

    events = event_stream.get_recent_events(100)
    assert [event["type"] for event in events] == ["CollisionEnter", "CollisionEnter", "CollisionEnter"]


def test_filter_by_source_entity_ids(monkeypatch):
    collector = _FakeCollector(_make_events())
    monkeypatch.setattr(event_stream, "_get_native_collector", lambda: collector)

    event_stream.set_event_filter(source_entity_ids=[10])

    events = event_stream.get_recent_events(100)
    assert [event["source_entity_id"] for event in events] == [10, 10]


def test_filter_by_target_entity_ids(monkeypatch):
    collector = _FakeCollector(_make_events())
    monkeypatch.setattr(event_stream, "_get_native_collector", lambda: collector)

    event_stream.set_event_filter(target_entity_ids=[20])

    events = event_stream.get_recent_events(100)
    assert [event["target_entity_id"] for event in events] == [20, 20]


def test_combined_filter(monkeypatch):
    collector = _FakeCollector(_make_events())
    monkeypatch.setattr(event_stream, "_get_native_collector", lambda: collector)

    event_stream.set_event_filter(
        event_types=["CollisionEnter"],
        source_entity_ids=[10],
        target_entity_ids=[20],
    )

    events = event_stream.get_recent_events(100)
    assert len(events) == 1
    assert events[0]["source_entity_id"] == 10
    assert events[0]["target_entity_id"] == 20


def test_clear_event_filter_restores_full_read(monkeypatch):
    collector = _FakeCollector(_make_events())
    monkeypatch.setattr(event_stream, "_get_native_collector", lambda: collector)

    event_stream.set_event_filter(event_types=["CollisionEnter"])
    assert len(event_stream.get_recent_events(100)) == 3

    event_stream.clear_event_filter()
    events = event_stream.get_recent_events(100)
    assert len(events) == 5


def test_native_collector_smoke():
    collector = event_stream._get_native_collector()
    assert collector is not None
    assert hasattr(collector, "set_event_filter")
    assert hasattr(collector, "clear_event_filter")
    assert hasattr(collector, "get_recent_events")
