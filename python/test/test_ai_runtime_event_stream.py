from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AI_RUNTIME_DIR = ROOT / "Infernux" / "ai_runtime"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_module(monkeypatch, module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, AI_RUNTIME_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


class _FakeCollector:
    def __init__(self):
        self.cleared = False
        self.calls: list[float] = []

    def get_recent_events(self, window_ms):
        self.calls.append(window_ms)
        return [
            types.SimpleNamespace(
                frame=3,
                timestamp=1000,
                sequence=1,
                type="PlayModeStart",
                source_entity_id=None,
                target_entity_id=None,
                payload={"state": "playing"},
            ),
            {
                "frame": 3,
                "timestamp": 1001,
                "sequence": 2,
                "type": "InputInjected",
                "source_entity_id": None,
                "target_entity_id": None,
                "payload": {"action": "move", "active": "true", "x": "1.0", "y": "0.0"},
            },
            types.SimpleNamespace(
                frame=3,
                timestamp=1002,
                sequence=3,
                type="CollisionEnter",
                source_entity_id=12,
                target_entity_id=34,
                payload={"body_a": "7", "body_b": "8", "trigger": "false"},
            ),
            types.SimpleNamespace(
                frame=3,
                timestamp=1003,
                sequence=4,
                type="TriggerExit",
                source_entity_id=56,
                target_entity_id=78,
                payload={"body_a": "9", "body_b": "10", "trigger": "true"},
            ),
        ]

    def clear_events(self):
        self.cleared = True


def test_event_stream_query_and_recorder_facade(monkeypatch):
    fake_collector = _FakeCollector()

    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")

    fake_scene_manager = types.SimpleNamespace(instance=lambda: types.SimpleNamespace(get_active_scene=lambda: None))
    fake_lib = types.SimpleNamespace(
        RuntimeEventCollector=types.SimpleNamespace(instance=lambda: fake_collector),
        SceneManager=fake_scene_manager,
    )
    fake_physics = types.SimpleNamespace(Physics=types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "Infernux.lib", fake_lib)
    monkeypatch.setitem(sys.modules, "Infernux.physics", fake_physics)

    _load_module(monkeypatch, "Infernux.ai_runtime.types", "types.py")
    _load_module(monkeypatch, "Infernux.ai_runtime.world_state", "world_state.py")
    event_stream = _load_module(monkeypatch, "Infernux.ai_runtime.event_stream", "event_stream.py")
    recorder_mod = _load_module(monkeypatch, "Infernux.ai_runtime.recorder", "recorder.py")
    query_api = _load_module(monkeypatch, "Infernux.ai_runtime.query_api", "query_api.py")

    events = event_stream.get_recent_events(250)
    assert fake_collector.calls == [250.0]
    assert len(events) == 4
    assert events[0]["type"] == "PlayModeStart"
    assert events[1]["payload"]["action"] == "move"
    assert events[2]["type"] == "CollisionEnter"
    assert events[3]["type"] == "TriggerExit"

    queried = query_api.get_recent_events(250)
    assert queried[0]["type"] == "PlayModeStart"
    assert queried[1]["payload"]["x"] == "1.0"

    recorder = recorder_mod.Recorder()
    assert recorder.get_recent_events(250)[2]["type"] == "CollisionEnter"
    recorder.clear()
    assert fake_collector.cleared is True


def test_event_stream_handles_invalid_windows(monkeypatch):
    fake_collector = _FakeCollector()

    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")

    fake_scene_manager = types.SimpleNamespace(instance=lambda: types.SimpleNamespace(get_active_scene=lambda: None))
    fake_lib = types.SimpleNamespace(
        RuntimeEventCollector=types.SimpleNamespace(instance=lambda: fake_collector),
        SceneManager=fake_scene_manager,
    )
    fake_physics = types.SimpleNamespace(Physics=types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "Infernux.lib", fake_lib)
    monkeypatch.setitem(sys.modules, "Infernux.physics", fake_physics)

    _load_module(monkeypatch, "Infernux.ai_runtime.types", "types.py")
    _load_module(monkeypatch, "Infernux.ai_runtime.world_state", "world_state.py")
    event_stream = _load_module(monkeypatch, "Infernux.ai_runtime.event_stream", "event_stream.py")

    assert event_stream.get_recent_events(0) == []
    assert event_stream.get_recent_events(-1) == []
    assert event_stream.get_recent_events("bad") == []
