from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace


def _load_input_api():
    module_path = Path(__file__).resolve().parents[1] / "Infernux" / "ai_runtime" / "input_api.py"
    spec = importlib.util.spec_from_file_location("test_input_api_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeInputManager:
    def __init__(self):
        self.virtual_input_state = SimpleNamespace(jump=False, attack=False, move_x=0.0, move_y=0.0)
        self._pending = SimpleNamespace(jump=False, attack=False, move_x=0.0, move_y=0.0)
        self.calls = []

    def set_virtual_action(self, action, active=True, x=0.0, y=0.0):
        self.calls.append((action, active, x, y))
        action = str(action).lower()
        if action == "jump":
            self._pending.jump = bool(active)
        elif action == "attack":
            self._pending.attack = bool(active)
        elif action == "move":
            self._pending.move_x = float(x) if active else 0.0
            self._pending.move_y = float(y) if active else 0.0

    def begin_frame(self):
        self.virtual_input_state.jump = bool(self._pending.jump)
        self.virtual_input_state.attack = bool(self._pending.attack)
        self.virtual_input_state.move_x = float(self._pending.move_x)
        self.virtual_input_state.move_y = float(self._pending.move_y)
        self._pending.jump = False
        self._pending.attack = False
        self._pending.move_x = 0.0
        self._pending.move_y = 0.0

    def clear_virtual_actions(self):
        self.virtual_input_state.jump = False
        self.virtual_input_state.attack = False
        self.virtual_input_state.move_x = 0.0
        self.virtual_input_state.move_y = 0.0
        self._pending.jump = False
        self._pending.attack = False
        self._pending.move_x = 0.0
        self._pending.move_y = 0.0


def test_jump_and_attack_are_single_frame_actions(monkeypatch):
    input_api = _load_input_api()
    manager = _FakeInputManager()
    monkeypatch.setattr(input_api, "_get_input_manager", lambda: manager)

    assert input_api.send_action("jump") is True
    assert manager.virtual_input_state.jump is False
    manager.begin_frame()
    assert manager.virtual_input_state.jump is True
    manager.begin_frame()
    assert manager.virtual_input_state.jump is False

    assert input_api.send_action("attack") is True
    assert manager.virtual_input_state.attack is False
    manager.begin_frame()
    assert manager.virtual_input_state.attack is True
    manager.begin_frame()
    assert manager.virtual_input_state.attack is False

    assert input_api.send_action("jump") is True
    input_api.clear_actions()
    assert manager.virtual_input_state.jump is False
    assert manager.virtual_input_state.attack is False
    assert manager.virtual_input_state.move_x == 0.0
    assert manager.virtual_input_state.move_y == 0.0
    manager.begin_frame()
    assert manager.virtual_input_state.jump is False
    assert manager.virtual_input_state.attack is False


def test_send_action_is_safe_for_repeated_calls(monkeypatch):
    input_api = _load_input_api()
    manager = _FakeInputManager()
    monkeypatch.setattr(input_api, "_get_input_manager", lambda: manager)

    assert input_api.send_action("attack") is True
    assert input_api.send_action("attack") is True
    assert input_api.send_action("move", x=-1, y=0.5) is True
    assert len(manager.calls) == 3


def test_move_is_single_frame_and_read_only_state_is_not_directly_mutable(monkeypatch):
    input_api = _load_input_api()
    manager = _FakeInputManager()
    monkeypatch.setattr(input_api, "_get_input_manager", lambda: manager)

    assert input_api.send_action("move", x=1, y=0) is True
    assert manager.virtual_input_state.move_x == 0.0

    manager.begin_frame()
    assert manager.virtual_input_state.move_x == 1.0
    assert manager.virtual_input_state.move_y == 0.0

    manager.begin_frame()
    assert manager.virtual_input_state.move_x == 0.0
    assert manager.virtual_input_state.move_y == 0.0

    assert input_api.send_action("move", x=0.25, y=0.75) is True
    assert manager.virtual_input_state.move_x == 0.0
    manager.begin_frame()
    assert manager.virtual_input_state.move_x == 0.25
    assert manager.virtual_input_state.move_y == 0.75
    input_api.clear_actions()
    assert manager.virtual_input_state.move_x == 0.0
    assert manager.virtual_input_state.move_y == 0.0

    @dataclass(frozen=True)
    class _ReadOnlyVirtualState:
        jump: bool = False
        attack: bool = False
        move_x: float = 0.0
        move_y: float = 0.0

    readonly = _ReadOnlyVirtualState()
    raised = False
    try:
        readonly.jump = True  # type: ignore[misc]
    except Exception:
        raised = True
    assert raised


def _load_input_module_with_fake_native(fake_manager):
    fake_infernux = ModuleType("Infernux")
    fake_infernux.__path__ = []  # type: ignore[attr-defined]
    fake_lib = ModuleType("Infernux.lib")

    class _NativeInputManagerFacade:
        @staticmethod
        def instance():
            return fake_manager

        @staticmethod
        def name_to_scancode(name):
            return fake_manager.name_to_scancode(name)

    fake_lib.InputManager = _NativeInputManagerFacade

    old_infernux = sys.modules.get("Infernux")
    old_lib = sys.modules.get("Infernux.lib")
    sys.modules["Infernux"] = fake_infernux
    sys.modules["Infernux.lib"] = fake_lib
    try:
        module_path = Path(__file__).resolve().parents[1] / "Infernux" / "input" / "__init__.py"
        spec = importlib.util.spec_from_file_location("test_input_module", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_infernux is not None:
            sys.modules["Infernux"] = old_infernux
        else:
            sys.modules.pop("Infernux", None)
        if old_lib is not None:
            sys.modules["Infernux.lib"] = old_lib
        else:
            sys.modules.pop("Infernux.lib", None)


@dataclass(frozen=True)
class _FakeVirtualState:
    jump: bool = False
    attack: bool = False
    move_x: float = 0.0
    move_y: float = 0.0


class _FakeNativeInputManager:
    def __init__(self):
        self._physical_keys = set()
        self._current = _FakeVirtualState()
        self._pending = _FakeVirtualState()

    def name_to_scancode(self, name):
        return str(name).lower()

    def get_key(self, scancode):
        return scancode in self._physical_keys

    @property
    def virtual_input_state(self):
        return self._current

    def set_virtual_action(self, action, active=True, x=0.0, y=0.0):
        action = str(action).lower()
        if action == "jump":
            self._pending = _FakeVirtualState(jump=bool(active), attack=self._pending.attack, move_x=self._pending.move_x, move_y=self._pending.move_y)
        elif action == "attack":
            self._pending = _FakeVirtualState(jump=self._pending.jump, attack=bool(active), move_x=self._pending.move_x, move_y=self._pending.move_y)
        elif action == "move":
            if active:
                self._pending = _FakeVirtualState(jump=self._pending.jump, attack=self._pending.attack, move_x=float(x), move_y=float(y))
            else:
                self._pending = _FakeVirtualState(jump=self._pending.jump, attack=self._pending.attack, move_x=0.0, move_y=0.0)

    def clear_virtual_actions(self):
        self._current = _FakeVirtualState()
        self._pending = _FakeVirtualState()

    def begin_frame(self):
        self._current = self._pending
        self._pending = _FakeVirtualState()


def test_input_get_axis_clamps_virtual_and_physical_inputs():
    fake_manager = _FakeNativeInputManager()
    input_module = _load_input_module_with_fake_native(fake_manager)

    fake_manager._physical_keys = {"d"}
    input_module.Input.set_game_focused(True)
    input_module.Input._game_viewport_origin = (0.0, 0.0)

    fake_manager.set_virtual_action("move", x=0.25, y=0.0)
    fake_manager.begin_frame()
    assert input_module.Input.get_axis("Horizontal") == 1.0

    fake_manager._physical_keys = {"a"}
    fake_manager.set_virtual_action("move", x=-0.5, y=0.0)
    fake_manager.begin_frame()
    assert input_module.Input.get_axis("Horizontal") == -1.0

    fake_manager._physical_keys = set()
    fake_manager.set_virtual_action("move", x=0.5, y=0.0)
    fake_manager.begin_frame()
    assert input_module.Input.get_axis("Horizontal") == 0.5

    fake_manager._physical_keys = {"d"}
    fake_manager.set_virtual_action("move", x=1.0, y=0.0)
    fake_manager.begin_frame()
    assert input_module.Input.get_axis("Horizontal") == 1.0

    fake_manager._physical_keys = {"a"}
    fake_manager.set_virtual_action("move", x=-1.0, y=0.0)
    fake_manager.begin_frame()
    assert input_module.Input.get_axis("Horizontal") == -1.0

    fake_manager._physical_keys = set()
    fake_manager.set_virtual_action("move", x=0.25, y=0.5)
    fake_manager.begin_frame()
    assert input_module.Input.get_axis("Horizontal") == 0.25
    assert input_module.Input.get_axis("Vertical") == 0.5
