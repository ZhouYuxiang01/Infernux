"""UIButton — a clickable button UI element.

Hierarchy:
    InxComponent → InxUIComponent → InxUIScreenComponent → UISelectable → UIButton

Usage in a user script::

    class MyUI(InxComponent):
        def start(self):
            start_btn = GameObject.find("StartBtn")
            if start_btn is None:
                return
            btn = start_btn.get_component(UIButton)
            btn.on_click.add_listener(self.on_start)

        def on_start(self):
            print("Start clicked!")
"""

from __future__ import annotations

from Infernux.components import serialized_field, list_field, add_component_menu
from Infernux.components.serialized_field import FieldType
from Infernux.debug import Debug
from .enums import TextAlignH, TextAlignV
from .ui_selectable import UISelectable
from .ui_event import UIEvent
from .ui_event_entry import UIEventEntry, materialize_event_arguments, _get_serializable_raw_field


@add_component_menu("UI/Button")
class UIButton(UISelectable):
    """A clickable button with visual state feedback.

    Combines **Image** (background) and **Text** (label) capabilities:

    * Background can be a solid ``background_color`` or a ``texture_path`` image.
    * Label text supports full typography: alignment, line-height, letter-spacing.
    * Fires ``on_click`` when the user performs a full click (down + up).
    """

    # ── Content ──
    label: str = serialized_field(
        default="Button", tooltip="Button label text",
        group="Content",
    )
    font_size: float = serialized_field(
        default=20.0, tooltip="Label font size",
        group="Content", range=(4.0, 256.0), drag_speed=0.5,
    )
    font_path: str = serialized_field(
        default="", tooltip="Optional font asset path",
        group="Content",
    )
    label_color: list = serialized_field(
        default=[1.0, 1.0, 1.0, 1.0], field_type=FieldType.COLOR,
        hdr=True, tooltip="Label text colour", group="Content",
    )
    text_align_h: TextAlignH = serialized_field(
        default=TextAlignH.Center,
        tooltip="Horizontal text alignment",
        group="Content",
    )
    text_align_v: TextAlignV = serialized_field(
        default=TextAlignV.Center,
        tooltip="Vertical text alignment",
        group="Content",
    )
    line_height: float = serialized_field(
        default=1.2, tooltip="Line height multiplier",
        group="Content", range=(0.5, 5.0), drag_speed=0.01,
    )
    letter_spacing: float = serialized_field(
        default=0.0, tooltip="Extra letter spacing in pixels",
        group="Content", range=(-20.0, 100.0), drag_speed=0.1,
    )

    # ── Fill ──
    texture_path: str = serialized_field(
        default="", tooltip="Background image texture path",
        group="Fill",
    )
    background_color: list = serialized_field(
        default=[0.22, 0.56, 0.92, 1.0], field_type=FieldType.COLOR,
        hdr=True, tooltip="Background fill colour (RGBA)", group="Fill",
    )

    # ── Events ──
    on_click_entries: list = list_field(
        element_type=FieldType.SERIALIZABLE_OBJECT,
        element_class=UIEventEntry,
        tooltip="Persistent click handlers (GO → component → method)",
        group="Events",
    )

    def awake(self):
        super().awake()
        self._init_button_state()

    def _init_button_state(self):
        if not hasattr(self, "_on_click"):
            self._on_click: UIEvent = UIEvent()

    @property
    def on_click(self) -> UIEvent:
        self._init_button_state()
        return self._on_click

    # ------------------------------------------------------------------
    # Pointer hooks
    # ------------------------------------------------------------------

    def on_pointer_click(self, event_data):
        Debug.log(
            f"UIButton.on_pointer_click label={getattr(self, 'label', '')!r} "
            f"interactable={getattr(self, 'interactable', None)} "
            f"listeners={self.on_click.listener_count} "
            f"persistent_entries={len(self.on_click_entries or [])}"
        )
        if not self.interactable:
            return
        self._init_button_state()
        Debug.log("UIButton.on_pointer_click invoke transient listeners")
        self._on_click.invoke()
        Debug.log("UIButton.on_pointer_click dispatch persistent entries")
        self._dispatch_persistent_entries()

    # ------------------------------------------------------------------
    # Persistent event dispatch
    # ------------------------------------------------------------------

    def _dispatch_persistent_entries(self):
        """Resolve and invoke each on_click_entries binding."""
        entries = self.on_click_entries
        if not entries:
            return
        for entry in entries:
            target_ref = _get_serializable_raw_field(entry, "target")
            if target_ref is None:
                continue
            go = target_ref.resolve() if hasattr(target_ref, "resolve") else target_ref
            if go is None:
                continue
            comp_name = getattr(entry, "component_name", "") or ""
            method_name = getattr(entry, "method_name", "") or ""
            if not comp_name or not method_name:
                continue
            Debug.log(
                f"UIButton dispatch entry target={getattr(go, 'name', None)!r} "
                f"component={comp_name!r} method={method_name!r}"
            )
            comp = self._resolve_component(go, comp_name)
            if comp is None:
                continue
            fn = getattr(comp, method_name, None)
            if callable(fn):
                try:
                    Debug.log(f"UIButton dispatch call {comp_name}.{method_name}")
                    fn(*materialize_event_arguments(entry, comp))
                except Exception:
                    import traceback
                    traceback.print_exc()

    @staticmethod
    def _resolve_component(go, comp_name: str):
        """Find a Python component by class name on *go*."""
        for py_comp in go.get_py_components():
            if type(py_comp).__name__ == comp_name:
                return py_comp
        return None
