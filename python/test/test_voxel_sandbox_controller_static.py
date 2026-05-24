from pathlib import Path


CONTROLLER = Path("TestProject/Assets/Scripts/VoxelSandboxController.py")


def test_controller_has_embedded_layout_fallback():
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "EMBEDDED_WORLD_LAYOUT" in source
    assert "\"..@.R.....T.....\"" in source
    assert "WORLD_LAYOUT = EMBEDDED_WORLD_LAYOUT" in source
