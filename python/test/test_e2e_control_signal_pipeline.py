"""End-to-end test for the v1.3 input pipeline.

Validates the full chain:

    PlatformerAdapter.translate_action("move", x=1.0)
        -> ai_runtime.submit_control(signal)
            -> _legacy_input_bridge -> InputManager.set_virtual_action
                -> SceneManager.step() promotes pending virtual input
                    -> Input.get_axis("Horizontal") returns 1.0
                        -> controller script moves the entity

Plus a legacy-path check that ``send_action("move", x=1.0)`` still drives the
same flow, so the v1.1 API remains usable during the v1.3 transition.

These are real-engine tests: no mocking, no monkeypatching. They rely on the
``scene`` fixture from ``conftest.py`` which owns the real SDL + Vulkan +
Jolt + input stack.
"""

from __future__ import annotations

from Infernux.ai_adapters.platformer import PlatformerAdapter
from Infernux.ai_runtime import (
    get_entity_snapshot,
    send_action,
    submit_control,
)
from Infernux.components import InxComponent
from Infernux.input import Input
from Infernux.lib import SceneManager, Vector3


class _HorizontalAxisMover(InxComponent):
    """Integrates the Horizontal virtual axis into transform.position.x.

    This is the minimum bridge needed so the test can observe a position
    change driven purely by the input pipeline — there is no other actor
    that would move the entity during ``step()``.
    """

    speed = 2.0

    def update(self, delta_time: float):
        move_x = Input.get_axis("Horizontal")
        if move_x == 0.0:
            return
        pos = self.transform.position
        self.transform.position = Vector3(
            pos.x + move_x * self.speed * delta_time,
            pos.y,
            pos.z,
        )


def _make_player(scene, name: str = "Player"):
    """Create a tagged GameObject that reacts to the Horizontal axis.

    The ``Player`` tag is what ``PlatformerAdapter.resolve_semantic_entity``
    looks for first, so tagging the object exercises the adapter's primary
    resolution path.
    """
    go = scene.create_game_object(name)
    go.tag = "Player"
    go.add_component(_HorizontalAxisMover)
    return go


def _step_frames(sm, count: int, dt: float = 1.0 / 60.0) -> None:
    for _ in range(count):
        sm.step(dt)


def test_e2e_adapter_submit_control_moves_entity(scene):
    """Full new-world chain: adapter + submit_control moves a real entity."""
    sm = SceneManager.instance()
    adapter = PlatformerAdapter()

    # Scene must be populated before entering play mode so the component is
    # ticked by the engine.
    go = _make_player(scene)

    sm.play()
    sm.pause()

    # Adapter resolves the player by tag — this is the entity the agent
    # "sees" through the semantic API.
    entity_id = adapter.resolve_semantic_entity(scene, "player")
    assert entity_id == go.id, "PlatformerAdapter must resolve the tagged player"

    # Baseline position via the generic observation surface.
    before = get_entity_snapshot(entity_id)
    assert before is not None
    x_before = before.position[0]

    # Translate a semantic action into a ControlSignal and submit it on the
    # generic Core API. No platformer-specific types cross this boundary.
    signal = adapter.translate_action("move", x=1.0)
    assert signal.axes.get("move_x") == 1.0
    submit_control(signal)

    # Advance ten frames so the legacy input bridge promotes the pending
    # virtual input and the controller script integrates it into position.
    _step_frames(sm, 10)

    after = get_entity_snapshot(entity_id)
    assert after is not None
    x_after = after.position[0]

    assert x_after > x_before, (
        f"Adapter + submit_control did not move the entity: "
        f"x_before={x_before}, x_after={x_after}"
    )


def test_e2e_legacy_send_action_still_moves_entity(scene):
    """Legacy v1.1 send_action path must keep working through v1.3."""
    sm = SceneManager.instance()

    go = _make_player(scene, name="LegacyPlayer")

    sm.play()
    sm.pause()

    before = get_entity_snapshot(go.id)
    assert before is not None
    x_before = before.position[0]

    # Legacy API: no adapter, no ControlSignal — send_action talks directly
    # to the input bridge the old way.
    assert send_action("move", x=1.0) is True

    _step_frames(sm, 10)

    after = get_entity_snapshot(go.id)
    assert after is not None
    x_after = after.position[0]

    assert x_after > x_before, (
        f"Legacy send_action did not move the entity: "
        f"x_before={x_before}, x_after={x_after}"
    )
