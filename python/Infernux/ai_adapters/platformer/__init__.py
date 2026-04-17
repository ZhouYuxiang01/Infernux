"""Platformer adapter (spec §2.2 example).

This package hosts the platformer-specific translation of semantic actions
and entity roles. It is where the v1.1 "jump / attack / move / Player"
vocabulary officially lives now that Engine Core has disowned it.
"""

from .adapter import PlatformerAdapter

__all__ = [
    "PlatformerAdapter",
]
