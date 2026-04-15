from __future__ import annotations

from typing import Any

from .event_stream import clear_events, get_recent_events


class Recorder:
    def get_recent_events(self, ms: int | float) -> list[dict[str, Any]]:
        return get_recent_events(ms)

    def clear(self) -> None:
        clear_events()
