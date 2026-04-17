"""Minimum Adapter protocol (spec §2.2).

Every concrete adapter must implement the two methods declared by
``Adapter``. Anything beyond this (e.g. ``detect_jump``, ``expect_move``) is
project-specific and not part of the universal contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from Infernux.ai_runtime.control_signal import ControlSignal

__all__ = [
    "Adapter",
    "AdapterProtocolError",
]


class AdapterProtocolError(RuntimeError):
    """Raised when an adapter is asked to resolve a role or action it does
    not know how to express."""


@runtime_checkable
class Adapter(Protocol):
    """The universal adapter contract.

    Concrete adapters (e.g. ``PlatformerAdapter``) may expose additional
    project-specific methods, but these two are the floor every adapter
    must provide so that Core or Agent code can rely on them uniformly.
    """

    def resolve_semantic_entity(self, scene: Any, role: str) -> int | None:
        """Resolve a semantic role (``"player"`` / ``"enemy"`` / ...) to a
        concrete entity id, or ``None`` if no such entity exists in ``scene``.

        Role vocabulary is adapter-defined; the Engine Core never inspects
        these strings.
        """
        ...

    def translate_action(self, name: str, **kwargs: Any) -> ControlSignal:
        """Translate a semantic action (``"jump"``, ``"dash"``, ...) into a
        Core ``ControlSignal``. Unknown action names should raise
        ``AdapterProtocolError``.
        """
        ...
