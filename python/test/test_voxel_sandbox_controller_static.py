from pathlib import Path


CONTROLLER = Path("TestProject/Assets/Scripts/VoxelSandboxController.py")


def test_controller_has_embedded_layout_fallback():
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "EMBEDDED_WORLD_LAYOUT" in source
    assert "\"..@.R.....T.....\"" in source
    assert "WORLD_LAYOUT = EMBEDDED_WORLD_LAYOUT" in source


def test_controller_declares_first_person_camera_and_arm_contract():
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "camera_mode = serialized_field(default=\"first_person\"" in source
    assert "camera_pitch = serialized_field" in source
    assert "arm_action = serialized_field" in source
    assert "arm_action_count = serialized_field" in source
    assert "VoxelSandbox_Arm" in source
    assert "def _look_direction(" in source
    assert "def _animate_arm(" in source
    assert "def _trigger_arm_action(" in source
    assert "def _ray_cells(" in source
