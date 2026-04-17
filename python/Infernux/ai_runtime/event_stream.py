"""Event stream surface (spec §3.6 + §3.10).

Events crossing the Python boundary keep their typed payload (int / float /
bool / str / Vec3 tuple). The previous convention of collapsing every payload
value to a string is explicitly forbidden by REFACTOR §8.

``agent_id`` is projected on every event. v1 convention (spec §3.6):

- single-agent sessions use ``agent_id = 0``
- ``agent_id = None`` marks a system-level event that is not attributable to
  any agent

The native collector is the source of truth; this module is a thin adapter
that coerces lists/ids and narrows payload value types when needed.
"""

from __future__ import annotations

from typing import Any


# Payload value types that survive the Python boundary. Anything outside this
# set is dropped rather than silently string-coerced (REFACTOR §8).
_ALLOWED_PAYLOAD_SCALARS = (int, float, bool, str)


def _get_native_collector():
    try:
        from Infernux.lib import RuntimeEventCollector
        return RuntimeEventCollector.instance()
    except Exception:
        return None


def _coerce_optional_id_list(values: Any) -> list[int] | None:
    if values is None:
        return None
    try:
        return [int(value) for value in values]
    except Exception:
        return None


def _coerce_vec3(value: Any) -> tuple[float, float, float] | None:
    if value is None or isinstance(value, (str, bytes)):
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        try:
            return (float(value.x), float(value.y), float(value.z))
        except Exception:
            return None
    try:
        items = list(value)
    except Exception:
        return None
    if len(items) != 3:
        return None
    try:
        return (float(items[0]), float(items[1]), float(items[2]))
    except Exception:
        return None


def _coerce_payload_value(value: Any) -> Any:
    """Narrow a payload value to the EventValue union (spec §3.6)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    vec3 = _coerce_vec3(value)
    if vec3 is not None:
        return vec3
    return None


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        try:
            payload = dict(payload or {})
        except Exception:
            return {}

    typed: dict[str, Any] = {}
    for key, raw in payload.items():
        coerced = _coerce_payload_value(raw)
        if coerced is None and raw is not None:
            # Drop rather than string-coerce; REFACTOR §8 forbids blanket
            # stringification. Callers that genuinely need a novel payload
            # type must extend this projection explicitly.
            continue
        typed[str(key)] = coerced if raw is not None else None
    return typed


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_to_dict(event: Any) -> dict[str, Any]:
    if event is None:
        return {}

    if isinstance(event, dict):
        getter = event.get
    else:
        def getter(key, default=None, _evt=event):
            return getattr(_evt, key, default)

    return {
        "frame": getter("frame"),
        "timestamp": getter("timestamp"),
        "timestamp_ms": _coerce_optional_int(getter("timestamp_ms")),
        "sequence": getter("sequence"),
        "type": getter("type"),
        "source_entity_id": _coerce_optional_int(getter("source_entity_id")),
        "target_entity_id": _coerce_optional_int(getter("target_entity_id")),
        "agent_id": _coerce_optional_int(getter("agent_id")),
        "payload": _normalize_payload(getter("payload")),
    }


def get_recent_events(ms: int | float) -> list[dict[str, Any]]:
    try:
        window_ms = float(ms)
    except Exception:
        return []

    if window_ms <= 0:
        return []

    collector = _get_native_collector()
    if collector is None:
        return []

    try:
        events = collector.get_recent_events(window_ms)
    except Exception:
        return []

    try:
        return [_event_to_dict(event) for event in list(events or [])]
    except Exception:
        return []


def set_event_filter(
    event_types: list[str] | None = None,
    source_entity_ids: list[int] | None = None,
    target_entity_ids: list[int] | None = None,
    agent_id: int | None = None,
) -> None:
    """Configure native-side event filtering (spec §3.10).

    ``agent_id=None`` means "do not filter by agent"; an explicit integer
    narrows the stream to events attributed to that agent. The native
    collector may ignore the ``agent_id`` kwarg if its binding predates spec
    §3.10; calls degrade gracefully in that case.
    """
    collector = _get_native_collector()
    if collector is None:
        return

    sources = _coerce_optional_id_list(source_entity_ids)
    targets = _coerce_optional_id_list(target_entity_ids)
    if source_entity_ids is not None and sources is None:
        return
    if target_entity_ids is not None and targets is None:
        return

    coerced_agent_id = _coerce_optional_int(agent_id) if agent_id is not None else None

    # Try the spec-compliant signature first (only when the caller actually
    # supplied an agent filter), then fall back to the legacy positional
    # form. This keeps the module working against both the current and the
    # post-§3.10 native binding.
    if coerced_agent_id is not None:
        try:
            collector.set_event_filter(
                event_types, sources, targets, agent_id=coerced_agent_id
            )
            return
        except TypeError:
            pass
        except Exception:
            return

    try:
        collector.set_event_filter(event_types, sources, targets)
    except Exception:
        return


def clear_event_filter() -> None:
    collector = _get_native_collector()
    if collector is None:
        return

    try:
        collector.clear_event_filter()
    except Exception:
        return


def clear_events() -> None:
    collector = _get_native_collector()
    if collector is None:
        return

    try:
        collector.clear_events()
    except Exception:
        return


__all__ = [
    "clear_event_filter",
    "clear_events",
    "get_recent_events",
    "set_event_filter",
]
