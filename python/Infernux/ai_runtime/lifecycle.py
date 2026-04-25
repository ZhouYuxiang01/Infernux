from __future__ import annotations

from typing import Callable


def _safe_call(label: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:
        try:
            from Infernux.debug import Debug
            Debug.log_suppressed(label, exc)
        except Exception:
            pass


def _clear_control_state() -> None:
    from Infernux.ai_runtime.control_signal import clear_control
    clear_control()


def _clear_legacy_actions() -> None:
    try:
        from Infernux.ai_runtime.input_api import clear_actions
        clear_actions()
    except Exception:
        pass


def _get_event_collector():
    try:
        from Infernux.lib import RuntimeEventCollector
        return RuntimeEventCollector.instance()
    except Exception:
        return None


def clear_runtime_control_state() -> None:
    """Clear all AI-injected control state.

    This is called from lifecycle hooks so level-triggered AI input cannot leak
    across Play Mode sessions or scene boundaries.
    """
    _safe_call("ai_runtime.lifecycle.clear_control_state", _clear_control_state)
    _safe_call("ai_runtime.lifecycle.clear_legacy_actions", _clear_legacy_actions)


def on_enter_play_mode() -> None:
    """Called before the native runtime enters Play Mode."""
    clear_runtime_control_state()


def on_exit_play_mode() -> None:
    """Called when the native runtime exits Play Mode."""
    clear_runtime_control_state()


def on_scene_loaded() -> None:
    """Called after a scene transition when AI control state must not leak."""
    clear_runtime_control_state()


def on_scene_unloaded() -> None:
    """Called before/after a scene unload when AI control state must not leak."""
    clear_runtime_control_state()


def on_frame_begin() -> None:
    """Advance the native AI event frame counter, when available."""
    collector = _get_event_collector()
    if collector is None:
        return
    _safe_call("ai_runtime.lifecycle.on_frame_begin", collector.begin_frame)


__all__ = [
    "clear_runtime_control_state",
    "on_enter_play_mode",
    "on_exit_play_mode",
    "on_frame_begin",
    "on_scene_loaded",
    "on_scene_unloaded",
]
