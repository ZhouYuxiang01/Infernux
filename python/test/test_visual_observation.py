from __future__ import annotations

import importlib.util
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
