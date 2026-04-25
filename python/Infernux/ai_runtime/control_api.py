from __future__ import annotations

from typing import Any


def _get_play_mode_manager():
    from Infernux.engine.play_mode import PlayModeManager

    manager = PlayModeManager.instance()
    if manager is None:
        manager = PlayModeManager()
    return manager


def _drain_deferred_task_runner(max_ticks: int = 64) -> bool:
    try:
        from Infernux.engine.deferred_task import DeferredTaskRunner
    except Exception:
        return True

    runner = DeferredTaskRunner.instance()
    if runner is None:
        return True

    for _ in range(max(0, int(max_ticks))):
        if not getattr(runner, "is_busy", False):
            return True
        try:
            runner.tick()
        except Exception:
            return False

    return not getattr(runner, "is_busy", False)


def enter_play_mode() -> bool:
    manager = _get_play_mode_manager()
    if manager is None:
        return False
    if getattr(manager, "is_playing", False):
        return True
    try:
        if not bool(manager.enter_play_mode()):
            return False
    except Exception:
        return False

    if not _drain_deferred_task_runner():
        return False

    return bool(getattr(manager, "is_playing", False))


def exit_play_mode() -> bool:
    manager = _get_play_mode_manager()
    if manager is None:
        return False
    if not getattr(manager, "is_playing", False):
        return True
    try:
        if not bool(manager.exit_play_mode()):
            return False
    except Exception:
        return False

    if not _drain_deferred_task_runner():
        return False

    return not bool(getattr(manager, "is_playing", False))


def pause() -> bool:
    manager = _get_play_mode_manager()
    if manager is None:
        return False
    if getattr(manager, "is_paused", False):
        return True
    if not getattr(manager, "is_playing", False):
        return False
    try:
        return bool(manager.pause())
    except Exception:
        return False


def resume() -> bool:
    manager = _get_play_mode_manager()
    if manager is None:
        return False
    if getattr(manager, "is_playing", False) and not getattr(manager, "is_paused", False):
        return True
    if not getattr(manager, "is_paused", False):
        return False
    try:
        return bool(manager.resume())
    except Exception:
        return False


def step(n: int) -> int:
    try:
        count = int(n)
    except Exception:
        return 0
    if count <= 0:
        return 0

    manager = _get_play_mode_manager()
    if manager is None or not getattr(manager, "is_paused", False):
        return 0

    stepped = 0
    for _ in range(count):
        try:
            manager.step_frame()
            stepped += 1
        except Exception:
            break
    return stepped


__all__ = [
    "enter_play_mode",
    "exit_play_mode",
    "pause",
    "resume",
    "step",
]
