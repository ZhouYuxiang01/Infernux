"""Adapter Layer (spec §2.2).

The Adapter Layer translates game-specific semantics ("player", "jump",
"attack", ...) into the semantics-free primitives provided by
``Infernux.ai_runtime``. Adapters live here so that Engine Core can remain
free of project-specific concepts.

Dependency rule: adapters may import from ``Infernux.ai_runtime``. The Core
MUST NOT import from ``Infernux.ai_adapters`` (enforced by the semantic
boundary guard under ``python/test/test_ai_runtime_semantic_boundary.py``).
"""

from .protocol import Adapter, AdapterProtocolError
from .tictactoe import TicTacToeAdapter

__all__ = [
    "Adapter",
    "AdapterProtocolError",
    "TicTacToeAdapter",
]
