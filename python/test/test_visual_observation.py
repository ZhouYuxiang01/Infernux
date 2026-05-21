from __future__ import annotations

import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_OBSERVATION_PATH = ROOT / "Infernux" / "ai_runtime" / "visual_observation.py"


class _Viewport:
    image_min_x = 10.4
    image_min_y = 20.2
    image_max_x = 110.6
    image_max_y = 70.8
    is_hovered = True


class _Image:
    def __init__(self):
        self.saved = None

    def save(self, path, format=None):
        self.saved = (str(path), format)


def _load_visual_observation():
    spec = importlib.util.spec_from_file_location("Infernux.ai_runtime.visual_observation", VISUAL_OBSERVATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capture_game_view_uses_last_recorded_viewport_bbox(tmp_path, monkeypatch):
    module = _load_visual_observation()
    image = _Image()
    captured = {}

    def _grab(bbox):
        captured["bbox"] = bbox
        return image

    monkeypatch.setattr(module, "_grab_image", _grab)
    module.record_game_viewport(_Viewport(), render_width=640, render_height=480, texture_id=42)

    output = tmp_path / "game_view.png"
    result = module.capture_game_view(str(output))

    assert result["available"] is True
    assert result["source"] == "window_capture"
    assert result["image_path"] == str(output)
    assert result["viewport"]["bbox"] == [10, 20, 111, 71]
    assert result["viewport"]["render_size"] == [640, 480]
    assert result["viewport"]["texture_id"] == 42
    assert captured["bbox"] == (10, 20, 111, 71)
    assert image.saved == (str(output), "PNG")


def test_capture_game_view_reports_unavailable_without_viewport():
    module = _load_visual_observation()

    result = module.capture_game_view("C:/Temp/missing.png")

    assert result["available"] is False
    assert result["reason"] == "game_viewport_not_recorded"


def test_capture_game_render_target_saves_internal_engine_pixels(tmp_path, monkeypatch):
    module = _load_visual_observation()
    payload = {
        "available": True,
        "source": "engine_render_target",
        "width": 2,
        "height": 1,
        "format": "rgba8",
        "pixels": bytes([255, 0, 0, 255, 0, 0, 255, 255]),
    }

    def _fail_if_window_capture_is_used(*args, **kwargs):
        raise AssertionError("internal render target capture must not use window capture")

    monkeypatch.setattr(module, "_grab_image", _fail_if_window_capture_is_used)
    monkeypatch.setattr(module, "_read_engine_render_target", lambda engine=None: payload)

    output = tmp_path / "internal.png"
    result = module.capture_game_render_target(str(output), engine=object())

    assert result["available"] is True
    assert result["source"] == "engine_render_target"
    assert result["image_path"] == str(output)
    assert result["width"] == 2
    assert result["height"] == 1
    assert output.exists()


def test_capture_game_render_target_converts_rgba16f_payload(tmp_path, monkeypatch):
    module = _load_visual_observation()
    pixels = struct.pack("<4e", 1.0, 0.0, 0.0, 1.0)
    monkeypatch.setattr(
        module,
        "_read_engine_render_target",
        lambda engine=None: {
            "available": True,
            "source": "engine_render_target",
            "width": 1,
            "height": 1,
            "format": "rgba16f",
            "pixels": pixels,
        },
    )

    output = tmp_path / "rgba16f.png"
    result = module.capture_game_render_target(str(output), engine=object())

    assert result["available"] is True
    assert result["format"] == "rgba8"
    assert output.exists()
