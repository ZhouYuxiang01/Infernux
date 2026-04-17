from __future__ import annotations

import pytest

import Infernux.ai_runtime.control_api as control_api
import Infernux.ai_runtime.observation_api as observation_api
import Infernux.ai_runtime.world_state as world_state


class _FakePlayModeManager:
    def __init__(self, *, playing=False, paused=False):
        self.is_playing = playing
        self.is_paused = paused
        self.enter_calls = 0
        self.pause_calls = 0
        self.resume_calls = 0
        self.step_calls = 0

    def enter_play_mode(self):
        self.enter_calls += 1
        self.is_playing = True
        self.is_paused = False
        return True

    def pause(self):
        self.pause_calls += 1
        self.is_playing = True
        self.is_paused = True
        return True

    def resume(self):
        self.resume_calls += 1
        self.is_playing = True
        self.is_paused = False
        return True

    def step_frame(self):
        self.step_calls += 1


def test_control_api_uses_play_mode_manager(monkeypatch):
    manager = _FakePlayModeManager()
    monkeypatch.setattr(control_api, "_get_play_mode_manager", lambda: manager)

    assert control_api.enter_play_mode() is True
    assert manager.enter_calls == 1

    manager = _FakePlayModeManager(playing=True, paused=False)
    monkeypatch.setattr(control_api, "_get_play_mode_manager", lambda: manager)

    assert control_api.enter_play_mode() is True
    assert manager.enter_calls == 0


def test_control_api_pause_resume_and_step_are_safe(monkeypatch):
    manager = _FakePlayModeManager(playing=True, paused=False)
    monkeypatch.setattr(control_api, "_get_play_mode_manager", lambda: manager)

    assert control_api.pause() is True
    assert manager.pause_calls == 1

    assert control_api.step(1) == 0
    assert manager.step_calls == 0

    assert control_api.resume() is True
    assert manager.resume_calls == 1

    manager.is_paused = True
    assert control_api.step(1) == 1
    assert manager.step_calls == 1

    assert control_api.step(0) == 0
    assert control_api.step(-3) == 0
    assert manager.step_calls == 1

    manager = _FakePlayModeManager(playing=False, paused=False)
    monkeypatch.setattr(control_api, "_get_play_mode_manager", lambda: manager)

    assert control_api.pause() is False
    assert control_api.resume() is False
    assert control_api.step(1) == 0


class _FakeTransform:
    def __init__(self, position):
        self.position = position


class _FakeController:
    def __init__(self, grounded=None):
        self.grounded = grounded


class _FakeRigidbody:
    def __init__(self, velocity):
        self.velocity = velocity


class _FakeGameObject:
    def __init__(self, object_id, *, tag=None, position=None, controller=None, rigidbody=None):
        self.id = object_id
        self.tag = tag
        self.transform = _FakeTransform(position) if position is not None else None
        self._controller = controller
        self._rigidbody = rigidbody

    def get_component(self, component_type):
        if component_type == "CharacterController":
            return self._controller
        if component_type == "Rigidbody":
            return self._rigidbody
        return None


class _FakeScene:
    def __init__(self, *, tagged=None, objects=None):
        self._tagged = tagged
        self._objects = list(objects or [])

    def find_with_tag(self, tag):
        if tag == "Player":
            return self._tagged
        return None

    def get_all_objects(self):
        return list(self._objects)


def test_get_player_snapshot_prefers_player_tag_then_falls_back(monkeypatch):
    tagged = _FakeGameObject(
        101,
        position=(1, 2, 3),
        controller=None,
        rigidbody=_FakeRigidbody((9, 9, 9)),
    )
    controller_obj = _FakeGameObject(
        202,
        position=(4, 5, 6),
        controller=_FakeController(grounded=True),
        rigidbody=_FakeRigidbody((1, 1, 1)),
    )
    rigidbody_obj = _FakeGameObject(
        303,
        position=(7, 8, 9),
        rigidbody=_FakeRigidbody((2, 2, 2)),
    )

    monkeypatch.setattr(observation_api, "_get_active_scene", lambda: _FakeScene(tagged=tagged, objects=[controller_obj, rigidbody_obj]))

    snapshot = observation_api.get_player_snapshot()

    assert snapshot is not None
    assert snapshot.entity_id == 101
    assert snapshot.position == (1, 2, 3)
    assert snapshot.velocity == (9, 9, 9)
    assert snapshot.grounded is None

    monkeypatch.setattr(observation_api, "_get_active_scene", lambda: _FakeScene(tagged=None, objects=[controller_obj, rigidbody_obj]))

    snapshot = observation_api.get_player_snapshot()

    assert snapshot is not None
    assert snapshot.entity_id == 202
    assert snapshot.position == (4, 5, 6)
    assert snapshot.velocity == (1, 1, 1)
    assert snapshot.grounded is True


def test_get_player_snapshot_emits_deprecation_warning(monkeypatch):
    player = _FakeGameObject(404, position=(0, 0, 0))
    monkeypatch.setattr(observation_api, "_get_active_scene", lambda: _FakeScene(tagged=player, objects=[player]))

    with pytest.warns(DeprecationWarning, match="deprecated"):
        snapshot = observation_api.get_player_snapshot()

    assert snapshot is not None
    assert snapshot.entity_id == 404


def test_observation_uses_world_state_scene_source():
    assert observation_api._get_active_scene is world_state.get_active_scene


def test_get_player_snapshot_handles_missing_fields_and_no_player(monkeypatch):
    player = _FakeGameObject(404, position=(0, 0, 0))
    monkeypatch.setattr(observation_api, "_get_active_scene", lambda: _FakeScene(tagged=player, objects=[player]))

    snapshot = observation_api.get_player_snapshot()

    assert snapshot is not None
    assert snapshot.entity_id == 404
    assert snapshot.position == (0, 0, 0)
    assert snapshot.velocity is None
    assert snapshot.grounded is None

    monkeypatch.setattr(observation_api, "_get_active_scene", lambda: _FakeScene(tagged=None, objects=[]))

    assert observation_api.get_player_snapshot() is None


def test_observation_api_recent_events_and_activity_summary(monkeypatch):
    events = [
        {"type": "InputInjected", "payload": {"action": "jump"}},
        {"type": "CollisionEnter", "payload": {"body_a": "1", "body_b": "2"}},
        {"type": "InputInjected", "payload": {"action": "attack"}},
    ]
    monkeypatch.setattr(observation_api._event_stream, "get_recent_events", lambda ms: list(events))

    recent = observation_api.get_recent_events(250)
    assert recent == events

    summary = observation_api.get_activity_summary(250)
    assert summary.event_count == 3
    assert summary.jumped is True
    assert summary.attacked is True

    monkeypatch.setattr(
        observation_api._event_stream,
        "get_recent_events",
        lambda ms: [{"type": "CollisionEnter", "payload": {"body_a": "1", "body_b": "2"}}],
    )
    summary = observation_api.get_activity_summary(250)
    assert summary.event_count == 1
    assert summary.jumped is False
    assert summary.attacked is False


def test_observation_api_activity_summary_handles_jump_and_attack_separately(monkeypatch):
    monkeypatch.setattr(
        observation_api._event_stream,
        "get_recent_events",
        lambda ms: [{"type": "InputInjected", "payload": {"action": "jump"}}],
    )
    summary = observation_api.get_activity_summary(250)
    assert summary.event_count == 1
    assert summary.jumped is True
    assert summary.attacked is False

    monkeypatch.setattr(
        observation_api._event_stream,
        "get_recent_events",
        lambda ms: [{"type": "InputInjected", "payload": {"action": "attack"}}],
    )
    summary = observation_api.get_activity_summary(250)
    assert summary.event_count == 1
    assert summary.jumped is False
    assert summary.attacked is True
