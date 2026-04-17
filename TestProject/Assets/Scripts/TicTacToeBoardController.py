from __future__ import annotations

from Infernux.ai_adapters.tictactoe import TicTacToeAdapter
from Infernux.ai_runtime.control_signal import clear_control, get_control_state, submit_control
from Infernux.components import FieldType, InxComponent, list_field, serialized_field
from Infernux.components.ref_wrappers import GameObjectRef
from Infernux.debug import Debug
from Infernux.ui import UIButton, UIText, UICanvas
from Infernux.ui.enums import TextAlignH, TextAlignV
from Infernux.ui.ui_event_entry import UIEventArgument, UIEventEntry
from Infernux.tictactoe_logic import (
    AI_MARK,
    HUMAN_MARK,
    EMPTY,
    BoardState,
    board_from_flat,
    choose_ai_move,
    format_board,
    state_from_board,
    winner_for,
)


_ADAPTER = TicTacToeAdapter()
_ = UICanvas
_CELL_NAMES = (
    "Cell_0_0",
    "Cell_0_1",
    "Cell_0_2",
    "Cell_1_0",
    "Cell_1_1",
    "Cell_1_2",
    "Cell_2_0",
    "Cell_2_1",
    "Cell_2_2",
)

_HUMAN_COLOR = [1.0, 0.2, 0.2, 1.0]
_AI_COLOR = [1.0, 0.9, 0.2, 1.0]
_EMPTY_COLOR = [1.0, 1.0, 1.0, 0.0]
_TURN_HUMAN_COLOR = [1.0, 0.35, 0.35, 1.0]
_TURN_AI_COLOR = [1.0, 0.9, 0.2, 1.0]
_RESULT_PLAYER_COLOR = [1.0, 0.35, 0.35, 1.0]
_RESULT_AI_COLOR = [1.0, 0.9, 0.2, 1.0]
_RESULT_DRAW_COLOR = [0.9, 0.9, 0.9, 1.0]


class TicTacToeBoardController(InxComponent):
    cells: list = list_field(element_type=FieldType.STRING, default=[EMPTY] * 9, group="State")
    current_turn: str = serialized_field(default=HUMAN_MARK, group="State")
    winner: str = serialized_field(default="", group="State")
    terminal: bool = serialized_field(default=False, group="State")
    draw: bool = serialized_field(default=False, group="State")
    human_mark: str = serialized_field(default=HUMAN_MARK, group="State")
    ai_mark: str = serialized_field(default=AI_MARK, group="State")

    def awake(self):
        self._ensure_button_cache()
        self._ensure_text_cache()
        self._refresh_visual_targets()

    def on_after_deserialize(self):
        self._ensure_button_cache()
        self._ensure_text_cache()
        self._refresh_visual_targets()
        self._bind_buttons()
        self._bind_status_labels()

    def start(self):
        self._ensure_button_cache()
        self._ensure_text_cache()
        self._refresh_visual_targets()
        self._bind_buttons()
        self._bind_status_labels()
        self.reset_board_state()
        Debug.log("TicTacToeBoardController ready")

    def snapshot_board_state(self) -> BoardState:
        board = board_from_flat(self.cells)
        return state_from_board(board, current_turn=self.current_turn)

    def request_place(self, row: int, col: int) -> bool:
        Debug.log(f"TicTacToe click -> request_place({row}, {col}) turn={self.current_turn} terminal={self.terminal}")
        self._ensure_button_cache()
        self._ensure_text_cache()
        self._refresh_visual_targets()
        if self.terminal:
            Debug.log("TicTacToe request_place rejected: terminal")
            return False
        if not (0 <= row < 3 and 0 <= col < 3):
            Debug.log("TicTacToe request_place rejected: out of range")
            return False
        index = row * 3 + col
        if self.cells[index] != EMPTY:
            Debug.log(f"TicTacToe request_place rejected: occupied index={index} value={self.cells[index]}")
            return False
        signal = _ADAPTER.translate_action("place", row=row, col=col)
        submit_control(signal)
        return True

    def apply_control(self, signal) -> bool:
        Debug.log(f"TicTacToe apply_control buttons={getattr(signal, 'buttons', None)} turn={self.current_turn} terminal={self.terminal}")
        row, col = self._decode_place_signal(signal)
        if row is None or col is None:
            Debug.log("TicTacToe apply_control rejected: no place signal")
            return False
        if self.terminal:
            Debug.log("TicTacToe apply_control rejected: terminal")
            return False
        if not (0 <= row < 3 and 0 <= col < 3):
            Debug.log("TicTacToe apply_control rejected: out of range")
            return False
        index = row * 3 + col
        if self.cells[index] != EMPTY:
            Debug.log(f"TicTacToe apply_control rejected: occupied index={index} value={self.cells[index]}")
            return False

        mark = self.current_turn or self.human_mark
        if mark not in {self.human_mark, self.ai_mark}:
            mark = self.human_mark

        self.cells[index] = mark
        self.winner = winner_for(board_from_flat(self.cells)) or ""
        self.draw = self.winner == "" and all(cell != EMPTY for cell in self.cells)
        self.terminal = bool(self.winner or self.draw)
        self.current_turn = "" if self.terminal else (self.ai_mark if mark == self.human_mark else self.human_mark)
        self._sync_visuals()
        Debug.log(f"TicTacToe apply_control accepted: row={row} col={col} mark={mark} next_turn={self.current_turn}")
        return True

    def late_update(self, delta_time: float):
        signal = get_control_state()
        if signal is None:
            return
        try:
            self.apply_control(signal)
        finally:
            clear_control(signal.channel_id)

    def choose_ai_move(self) -> tuple[int, int] | None:
        state = self.snapshot_board_state()
        if state.terminal or state.current_turn != self.ai_mark:
            return None
        return choose_ai_move(state, ai_mark=self.ai_mark, human_mark=self.human_mark)

    def _bind_buttons(self) -> None:
        self._ensure_button_cache()
        scene = getattr(self.game_object, "scene", None)
        if scene is None:
            return
        board_ref = GameObjectRef(self.game_object)
        for index, name in enumerate(_CELL_NAMES):
            go = scene.find(name) if hasattr(scene, "find") else None
            if go is None:
                continue
            btn = self._get_button(go)
            if btn is None:
                continue
            row = index // 3
            col = index % 3
            btn.on_click.remove_all_listeners()
            btn.font_size = 92.0
            btn.on_click_entries = [
                UIEventEntry(
                    target=board_ref,
                    component_name="TicTacToeBoardController",
                    method_name="request_place",
                    arguments=[
                        UIEventArgument(kind="int", name="row", int_value=row),
                        UIEventArgument(kind="int", name="col", int_value=col),
                    ],
                )
            ]
            self._buttons[index] = btn
            Debug.log(
                f"TicTacToe bind button {name} listeners={btn.on_click.listener_count} "
                f"persistent_entries={len(btn.on_click_entries)} row={row} col={col}"
            )

    def _bind_status_labels(self) -> None:
        self._ensure_text_cache()
        scene = getattr(self.game_object, "scene", None)
        if scene is None:
            return
        turn = self._get_text(scene.find("TurnLabel") if hasattr(scene, "find") else None)
        result = self._get_text(scene.find("ResultLabel") if hasattr(scene, "find") else None)
        if turn is not None:
            turn.raycast_target = False
            turn.font_size = 36.0
            turn.font_path = "Library/Resources/fonts/PingFangTC-Regular.otf"
            turn.x = 0.0
            turn.y = 196.0
            turn.width = 542.0
            turn.height = 40.0
            turn.text_align_h = TextAlignH.Center
            turn.text_align_v = TextAlignV.Top
            self._turn_label = turn
        if result is not None:
            result.raycast_target = False
            result.font_size = 32.0
            result.font_path = "Library/Resources/fonts/PingFangTC-Regular.otf"
            result.x = 0.0
            result.y = 236.0
            result.width = 542.0
            result.height = 36.0
            result.text_align_h = TextAlignH.Center
            result.text_align_v = TextAlignV.Top
            self._result_label = result
        self._update_status_labels()

    def _refresh_visual_targets(self) -> None:
        scene = getattr(self.game_object, "scene", None)
        if scene is None:
            return
        self._ensure_button_cache()
        for index, name in enumerate(_CELL_NAMES):
            go = scene.find(name) if hasattr(scene, "find") else None
            btn = self._get_button(go) if go is not None else None
            if btn is not None:
                self._buttons[index] = btn

    def _ensure_button_cache(self) -> None:
        buttons = getattr(self, "_buttons", None)
        if not isinstance(buttons, list) or len(buttons) != 9:
            self._buttons = [None] * 9

    def _ensure_text_cache(self) -> None:
        if not hasattr(self, "_turn_label"):
            self._turn_label = None
        if not hasattr(self, "_result_label"):
            self._result_label = None

    def _get_button(self, game_object):
        for comp in game_object.get_py_components():
            if isinstance(comp, UIButton):
                return comp
        return None

    def _get_text(self, game_object):
        if game_object is None:
            return None
        for comp in game_object.get_py_components():
            if isinstance(comp, UIText):
                return comp
        return None

    def reset_board_state(self) -> None:
        self.cells = [EMPTY] * 9
        self.current_turn = self.human_mark
        self.winner = ""
        self.terminal = False
        self.draw = False
        self._sync_visuals()

    def _decode_place_signal(self, signal):
        buttons = getattr(signal, "buttons", {}) or {}
        for key, active in buttons.items():
            if not active:
                continue
            key = str(key)
            if not key.startswith("place:"):
                continue
            parts = key.split(":")
            if len(parts) != 3:
                continue
            try:
                return int(parts[1]), int(parts[2])
            except ValueError:
                continue
        return None, None

    def _sync_visuals(self) -> None:
        self._ensure_button_cache()
        self._ensure_text_cache()
        self._refresh_visual_targets()
        Debug.log(f"TicTacToe _sync_visuals entered board=\n{format_board(self.snapshot_board_state())}")
        for index, btn in enumerate(self._buttons):
            if btn is None:
                continue
            value = self.cells[index]
            before_label = getattr(btn, "label", "")
            before_color = list(getattr(btn, "label_color", []) or [])
            if value == EMPTY:
                btn.label = ""
                btn.label_color = _EMPTY_COLOR
            else:
                btn.label = value
                btn.label_color = _HUMAN_COLOR if value == self.human_mark else _AI_COLOR
            btn.interactable = (not self.terminal) and (value == EMPTY)
            after_label = getattr(btn, "label", "")
            after_color = list(getattr(btn, "label_color", []) or [])
            if before_label != after_label or before_color != after_color:
                Debug.log(
                    f"TicTacToe visual cell[{index}] label {before_label!r} -> {after_label!r} "
                    f"color {before_color} -> {after_color}"
                )
        if self.terminal:
            for btn in self._buttons:
                if btn is not None:
                    btn.interactable = False
        self._update_status_labels()

    def _update_status_labels(self) -> None:
        turn_label = getattr(self, "_turn_label", None)
        if turn_label is not None:
            if self.terminal:
                turn_label.text = "Turn: -"
                turn_label.color = [0.85, 0.85, 0.85, 1.0]
            else:
                turn_label.text = f"Turn: {self.current_turn}"
                turn_label.color = _TURN_HUMAN_COLOR if self.current_turn == self.human_mark else _TURN_AI_COLOR
        result_label = getattr(self, "_result_label", None)
        if result_label is not None:
            if not self.terminal:
                result_label.text = ""
                result_label.color = [1.0, 1.0, 1.0, 0.0]
            elif self.draw:
                result_label.text = "Draw"
                result_label.color = _RESULT_DRAW_COLOR
            elif self.winner == self.human_mark:
                result_label.text = "Player wins"
                result_label.color = _RESULT_PLAYER_COLOR
            elif self.winner == self.ai_mark:
                result_label.text = "AI wins"
                result_label.color = _RESULT_AI_COLOR
            else:
                result_label.text = "Game over"
                result_label.color = [0.9, 0.9, 0.9, 1.0]
        if self.terminal:
            if self.winner:
                Debug.log(f"TicTacToe result: {self.winner} wins")
            else:
                Debug.log("TicTacToe result: draw")
        else:
            Debug.log(f"TicTacToe turn: {self.current_turn}")


__all__ = [
    "TicTacToeBoardController",
]
