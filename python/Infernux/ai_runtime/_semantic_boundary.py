"""Semantic boundary metadata (REFACTOR §10).

Keywords in ``FORBIDDEN_TOKENS`` must not appear as identifiers or string
literals in new Engine Core code. Adapter layer code is free to use them.

``GRANDFATHERED_MODULES`` lists files that are known to still carry v1.1
legacy semantic vocabulary. These are exempted from the guard for Phase 1
(v1.3) and Phase 2 (v1.4 前半). The set shrinks to empty over Phase 3
(v1.4 后半) as the observation surface migrates to entity-centric, and
finally at Phase 4 (v2.0) when the legacy API is removed.

This file is consumed by ``python/test/test_ai_runtime_semantic_boundary.py``.
It deliberately lives under ``ai_runtime/`` so the exemptions are versioned
alongside the code they cover.
"""

from __future__ import annotations

# Tokens that trigger the guard (case-insensitive, word-boundary match).
FORBIDDEN_TOKENS: frozenset[str] = frozenset(
    {
        "player",
        "jump",
        "attack",
        "enemy",
        "platform",
    }
)

# Modules allowed to still reference the forbidden tokens during the v1.3 /
# v1.4 transition. Filenames (not full paths) relative to
# ``python/Infernux/ai_runtime/``.
GRANDFATHERED_MODULES: frozenset[str] = frozenset(
    {
        "input_api.py",  # ActionType.Jump/Attack/Move — removed in Phase 4
        "observation_api.py",  # PlayerSnapshot / jumped / attacked — removed in Phase 3
        "entity_observation.py",  # heuristic jump / ground detection — removed in Phase 3
        "_semantic_boundary.py",  # this file itself enumerates the tokens
    }
)

# Line-level escape hatch: any line ending in this comment is skipped.
ESCAPE_HATCH_MARKER: str = "noqa: semantic-boundary"
