"""Game View visual observation helpers for external agents."""

from __future__ import annotations

import math
import struct
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


def capture_game_render_target(output_path: str = "", engine: Any | None = None) -> dict[str, Any]:
    """Capture the engine-owned Game Render Target to a PNG file.

    This path does not use desktop/window capture. It reads pixels through the
    native engine binding and converts the returned render-target bytes to PNG.
    """
    payload = _read_engine_render_target(engine)
    if not payload.get("available"):
        return payload

    path = Path(output_path) if output_path else _default_render_target_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        image = _image_from_render_target(payload)
        image.save(str(path), format="PNG")
    except Exception as exc:
        return {
            "available": False,
            "reason": "engine_render_target_save_failed",
            "message": str(exc),
        }

    return {
        "available": True,
        "source": "engine_render_target",
        "image_path": str(path.resolve()),
        "width": int(payload.get("width", 0) or 0),
        "height": int(payload.get("height", 0) or 0),
        "format": "rgba8",
        "native_format": str(payload.get("format", "")),
    }


def _default_capture_path() -> Path:
    root = Path(tempfile.gettempdir()) / "infernux_agent_observations"
    return root / f"game_view_{int(time.time() * 1000)}.png"


def _default_render_target_path() -> Path:
    root = Path(tempfile.gettempdir()) / "infernux_agent_observations"
    return root / f"game_render_target_{int(time.time() * 1000)}.png"


def _grab_image(bbox: tuple[int, int, int, int]):
    from PIL import ImageGrab

    return ImageGrab.grab(bbox=bbox)


def _read_engine_render_target(engine: Any | None = None) -> dict[str, Any]:
    target = engine if engine is not None else _current_engine()
    if target is None:
        return {
            "available": False,
            "reason": "engine_unavailable",
            "hint": "Run inside an active editor/player session before calling runtime_capture_game_render_target.",
        }

    reader = getattr(target, "read_game_render_target_pixels", None)
    if callable(reader):
        return dict(reader())

    native_getter = getattr(target, "get_native_engine", None)
    native = native_getter() if callable(native_getter) else target
    reader = getattr(native, "read_game_render_target_pixels", None)
    if callable(reader):
        return dict(reader())

    return {
        "available": False,
        "reason": "engine_render_target_readback_unavailable",
        "hint": "The loaded native Infernux binding does not expose read_game_render_target_pixels.",
    }


def _current_engine():
    try:
        from Infernux.engine.ui.editor_services import EditorServices

        services = EditorServices.instance()
        if services.engine is not None:
            return services.engine
        return services.native_engine
    except Exception:
        return None


def _image_from_render_target(payload: dict[str, Any]):
    from PIL import Image

    width = int(payload.get("width", 0) or 0)
    height = int(payload.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        raise ValueError("render target payload has invalid dimensions")

    pixels = payload.get("pixels", b"")
    if isinstance(pixels, str):
        pixels = pixels.encode("latin1")
    pixels = bytes(pixels)

    fmt = str(payload.get("format", "")).lower()
    if fmt == "rgba8":
        expected = width * height * 4
        if len(pixels) < expected:
            raise ValueError("rgba8 render target payload is truncated")
        return Image.frombytes("RGBA", (width, height), pixels[:expected])

    if fmt == "rgba16f":
        return Image.frombytes("RGBA", (width, height), _rgba16f_to_rgba8(pixels, width, height))

    raise ValueError(f"unsupported render target pixel format: {fmt}")


def _rgba16f_to_rgba8(pixels: bytes, width: int, height: int) -> bytes:
    expected = width * height * 8
    if len(pixels) < expected:
        raise ValueError("rgba16f render target payload is truncated")
    out = bytearray(width * height * 4)
    src = 0
    dst = 0
    for _ in range(width * height):
        r, g, b, a = struct.unpack_from("<4e", pixels, src)
        out[dst] = _float_channel_to_u8(r, gamma=True)
        out[dst + 1] = _float_channel_to_u8(g, gamma=True)
        out[dst + 2] = _float_channel_to_u8(b, gamma=True)
        out[dst + 3] = _float_channel_to_u8(a, gamma=False)
        src += 8
        dst += 4
    return bytes(out)


def _float_channel_to_u8(value: float, *, gamma: bool) -> int:
    value = max(0.0, min(float(value), 1.0))
    if gamma:
        value = value ** (1.0 / 2.2)
    return int(round(value * 255.0))
