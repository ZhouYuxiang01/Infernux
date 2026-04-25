"""Generic control signal API (spec section 3.3).

This module provides the channel-based, semantics-free control primitive
that supersedes the legacy action-name input path. The signal type carries
only opaque identifiers (string keys) and numeric values; interpretation is
the backend's concern.

Execution semantics (spec section 3.3):

- level-trigger: ``buttons[key] = True`` means "held", not "edge".
- last-write-wins on the same ``channel_id``.
- ``step()`` does NOT implicitly clear signals.
- ``axes`` values are clamped to ``[-1.0, 1.0]``.
- ``duration_ms`` is a hint; when set, backends may auto-clear the channel
  on expiry. When ``None`` the signal persists until overwritten or cleared.

Backend dispatch:

Dispatch prefers the native C++ ``InputChannel`` binding when available.
The legacy bridge remains as a fallback for older runtimes, but the public
contract below does not change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import _legacy_input_bridge

__all__ = [
    "ControlSignal",
    "clear_control",
    "get_control_state",
    "submit_control",
]


_AXIS_MIN = -1.0
_AXIS_MAX = 1.0

# Channel index reserved for the default / single-agent case (spec section 3.6:
# "single agent => agent_id=0"). Multi-channel arbitration is out of scope
# for v1.
_DEFAULT_CHANNEL_ID = 0


@dataclass
class ControlSignal:
    """Generic input signal carried on a logical channel.

    Fields mirror spec section 3.3 exactly. All values are semantics-free:
    button and axis names are opaque strings interpreted by the input
    backend.
    """

    channel_id: int = _DEFAULT_CHANNEL_ID
    axes: dict[str, float] = field(default_factory=dict)
    buttons: dict[str, bool] = field(default_factory=dict)
    duration_ms: int | None = None
    timestamp_ms: int | None = None


# --- channel state cache ------------------------------------------------------

# ``_channel_state`` holds the last-write-wins snapshot for each channel. It
# is the authoritative Python-side state; backends read from it lazily. A
# module-level dict is acceptable in v1 because the runtime hosts a single
# process with cooperative agents. Multi-process sharing is out of scope for
# v1 (spec section 6).
_channel_state: dict[int, ControlSignal] = {}


def _clamp_axis(value: float) -> float:
    if value != value:  # NaN
        return 0.0
    if value < _AXIS_MIN:
        return _AXIS_MIN
    if value > _AXIS_MAX:
        return _AXIS_MAX
    return value


def _normalize_signal(signal: ControlSignal) -> ControlSignal:
    axes: dict[str, float] = {}
    for key, raw in signal.axes.items():
        try:
            axes[str(key)] = _clamp_axis(float(raw))
        except (TypeError, ValueError):
            continue

    buttons: dict[str, bool] = {}
    for key, raw in signal.buttons.items():
        buttons[str(key)] = bool(raw)

    duration_ms = signal.duration_ms
    if duration_ms is not None:
        try:
            duration_ms = int(duration_ms)
        except (TypeError, ValueError):
            duration_ms = None
        else:
            if duration_ms < 0:
                duration_ms = 0

    timestamp_ms = signal.timestamp_ms
    if timestamp_ms is None:
        timestamp_ms = int(time.monotonic() * 1000)
    else:
        try:
            timestamp_ms = int(timestamp_ms)
        except (TypeError, ValueError):
            timestamp_ms = int(time.monotonic() * 1000)

    return ControlSignal(
        channel_id=int(signal.channel_id),
        axes=axes,
        buttons=buttons,
        duration_ms=duration_ms,
        timestamp_ms=timestamp_ms,
    )


def _get_input_manager():
    try:
        from Infernux.lib import InputManager
    except Exception:
        return None

    try:
        return InputManager.instance()
    except Exception:
        return None


def _build_native_channel(signal: ControlSignal):
    try:
        from Infernux.lib import InputChannel
    except Exception:
        return None

    native = InputChannel()
    native.channel_id = int(signal.channel_id)
    native.axes = dict(signal.axes)
    native.buttons = dict(signal.buttons)
    native.duration_ms = -1 if signal.duration_ms is None else int(signal.duration_ms)
    native.timestamp_ms = -1 if signal.timestamp_ms is None else int(signal.timestamp_ms)
    return native


def _submit_native_signal(signal: ControlSignal) -> bool:
    manager = _get_input_manager()
    if manager is None:
        return False

    submit = getattr(manager, "submit_channel_signal", None)
    if not callable(submit):
        return False

    native_signal = _build_native_channel(signal)
    if native_signal is None:
        return False

    try:
        submit(native_signal)
    except Exception:
        return False
    return True


def _clear_native_channel(channel_id: int | None) -> bool:
    manager = _get_input_manager()
    if manager is None:
        return False

    clear_channel = getattr(manager, "clear_channel", None)
    if not callable(clear_channel):
        return False

    try:
        clear_channel(-1 if channel_id is None else int(channel_id))
    except Exception:
        return False
    return True


def _native_to_control_signal(native) -> ControlSignal:
    duration_ms = int(native.duration_ms)
    timestamp_ms = int(native.timestamp_ms)
    return ControlSignal(
        channel_id=int(native.channel_id),
        axes=dict(native.axes),
        buttons=dict(native.buttons),
        duration_ms=None if duration_ms < 0 else duration_ms,
        timestamp_ms=None if timestamp_ms < 0 else timestamp_ms,
    )


def get_control_state(channel_id: int = _DEFAULT_CHANNEL_ID) -> ControlSignal | None:
    """Return the last submitted control signal for a channel, if any."""
    try:
        cid = int(channel_id)
    except Exception:
        cid = _DEFAULT_CHANNEL_ID

    manager = _get_input_manager()
    if manager is not None:
        getter = getattr(manager, "get_channel_state", None)
        if callable(getter):
            try:
                native = getter(cid)
            except Exception:
                native = None
            if native is not None:
                try:
                    return _native_to_control_signal(native)
                except Exception:
                    pass

    return _channel_state.get(cid)


# --- public API ---------------------------------------------------------------


def submit_control(signal: ControlSignal) -> None:
    """Submit a generic control signal (spec section 3.3).

    The signal is clamped to the axis value domain, stamped with a timestamp
    if the caller did not provide one, then stored as the authoritative state
    for its ``channel_id`` (last-write-wins).
    """
    if not isinstance(signal, ControlSignal):
        raise TypeError("submit_control expects a ControlSignal instance")

    normalized = _normalize_signal(signal)
    _channel_state[normalized.channel_id] = normalized
    if not _submit_native_signal(normalized):
        _legacy_input_bridge.apply_signal(normalized)


def clear_control(channel_id: int | None = None) -> None:
    """Clear a channel (spec section 3.3).

    ``channel_id=None`` clears all channels. Otherwise only the named channel
    is cleared. Flushing the default channel also clears the backend's
    transient input state.
    """
    if channel_id is None:
        _channel_state.clear()
        if not _clear_native_channel(None):
            _legacy_input_bridge.clear()
        return

    cid = int(channel_id)
    _channel_state.pop(cid, None)
    if not _clear_native_channel(cid) and cid == _DEFAULT_CHANNEL_ID:
        _legacy_input_bridge.clear()


def _get_channel_state(channel_id: int = _DEFAULT_CHANNEL_ID) -> ControlSignal | None:
    """Package-private accessor for tests and the transitional bridge."""
    return get_control_state(channel_id)
