"""Game View visual observation helpers for external agents."""

from __future__ import annotations

import math
import tempfile
import time
from pathlib import Path
from typing import Any


_LAST_GAME_VIEWPORT: dict[str, Any] | None = None


def record_game_viewport(viewport_info: Any, render_width: int, render_height: int, texture_id: int = 0) -> dict[str, Any]:
    """Record the last on-screen Game View image bounds.

    The GameViewPanel calls this immediately after drawing the game render
    target. MCP tools can then crop the real desktop pixels for that viewport.
    """
    global _LAST_GAME_VIEWPORT
    min_x = int(math.floor(float(getattr(viewport_info, "image_min_x", 0.0))))
    min_y = int(math.floor(float(getattr(viewport_info, "image_min_y", 0.0))))
    max_x = int(math.ceil(float(getattr(viewport_info, "image_max_x", 0.0))))
    max_y = int(math.ceil(float(getattr(viewport_info, "image_max_y", 0.0))))
    _LAST_GAME_VIEWPORT = {
        "bbox": [min_x, min_y, max_x, max_y],
        "render_size": [int(render_width), int(render_height)],
        "texture_id": int(texture_id or 0),
        "hovered": bool(getattr(viewport_info, "is_hovered", False)),
        "recorded_at": time.time(),
    }
    return dict(_LAST_GAME_VIEWPORT)


def last_game_viewport() -> dict[str, Any] | None:
    """Return the last recorded Game View viewport metadata."""
    return dict(_LAST_GAME_VIEWPORT) if _LAST_GAME_VIEWPORT is not None else None


def capture_game_view(output_path: str = "") -> dict[str, Any]:
    """Capture the visible Game View viewport to a PNG file.

    This captures the actual desktop pixels currently occupied by the Game View
    image region. It is intentionally different from a semantic world snapshot:
    agents can use it to inspect what a human would see in the editor window.
    """
    viewport = last_game_viewport()
    if viewport is None:
        return {
            "available": False,
            "reason": "game_viewport_not_recorded",
            "hint": "Open or focus the Game panel and let one frame render before calling runtime_capture_game_view.",
        }

    bbox = tuple(int(v) for v in viewport.get("bbox", []))
    if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return {
            "available": False,
            "reason": "invalid_game_viewport_bbox",
            "viewport": viewport,
        }

    path = Path(output_path) if output_path else _default_capture_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        image = _grab_image(bbox)
        image.save(str(path), format="PNG")
    except Exception as exc:
        return {
            "available": False,
            "reason": "window_capture_failed",
            "message": str(exc),
            "viewport": viewport,
        }

    return {
        "available": True,
        "source": "window_capture",
        "image_path": str(path.resolve()),
        "viewport": viewport,
    }


def _default_capture_path() -> Path:
    root = Path(tempfile.gettempdir()) / "infernux_agent_observations"
    return root / f"game_view_{int(time.time() * 1000)}.png"


def _grab_image(bbox: tuple[int, int, int, int]):
    from PIL import ImageGrab

    return ImageGrab.grab(bbox=bbox)
