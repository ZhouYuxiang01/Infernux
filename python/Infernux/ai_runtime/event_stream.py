from __future__ import annotations

from typing import Any


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


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    try:
        return dict(payload or {})
    except Exception:
        return {}


def _event_to_dict(event: Any) -> dict[str, Any]:
    if event is None:
        return {}

    if isinstance(event, dict):
        return {
            "frame": event.get("frame"),
            "timestamp": event.get("timestamp"),
            "sequence": event.get("sequence"),
            "type": event.get("type"),
            "source_entity_id": event.get("source_entity_id"),
            "target_entity_id": event.get("target_entity_id"),
            "payload": _normalize_payload(event.get("payload")),
        }

    return {
        "frame": getattr(event, "frame", None),
        "timestamp": getattr(event, "timestamp", None),
        "sequence": getattr(event, "sequence", None),
        "type": getattr(event, "type", None),
        "source_entity_id": getattr(event, "source_entity_id", None),
        "target_entity_id": getattr(event, "target_entity_id", None),
        "payload": _normalize_payload(getattr(event, "payload", None)),
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
) -> None:
    collector = _get_native_collector()
    if collector is None:
        return

    sources = _coerce_optional_id_list(source_entity_ids)
    targets = _coerce_optional_id_list(target_entity_ids)
    if source_entity_ids is not None and sources is None:
        return
    if target_entity_ids is not None and targets is None:
        return

    try:
        collector.set_event_filter(event_types, sources, targets)
    except Exception:
        pass


def clear_event_filter() -> None:
    collector = _get_native_collector()
    if collector is None:
        return

    try:
        collector.clear_event_filter()
    except Exception:
        pass


def clear_events() -> None:
    collector = _get_native_collector()
    if collector is None:
        return

    try:
        collector.clear_events()
    except Exception:
        pass


__all__ = [
    "clear_event_filter",
    "clear_events",
    "get_recent_events",
    "set_event_filter",
]
