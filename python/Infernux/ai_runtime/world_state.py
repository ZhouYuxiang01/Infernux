from __future__ import annotations

from typing import Any, Iterable

from .types import EntityRecord


def _get_active_scene():
    try:
        from Infernux.lib import SceneManager
    except Exception:
        return None

    try:
        return SceneManager.instance().get_active_scene()
    except Exception:
        return None


def get_active_scene():
    return _get_active_scene()


def _normalize_type_name(type_name: Any) -> str:
    if not type_name:
        return ""

    raw_name = getattr(type_name, "__name__", type_name)
    name = str(raw_name).strip()
    if not name:
        return ""

    if name.startswith("<class '") and name.endswith("'>"):
        name = name[8:-2]

    if "::" in name:
        name = name.rsplit("::", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[-1]

    return name


normalize_type_name = _normalize_type_name


def _iter_component_types(game_object: Any) -> list[str]:
    seen: set[str] = set()
    types: list[str] = []

    def add(type_name: Any) -> None:
        name = _normalize_type_name(type_name)
        if not name:
            return
        if name in seen:
            return
        seen.add(name)
        types.append(name)

    add("Transform")

    try:
        for comp in game_object.get_components():
            add(getattr(comp, "type_name", comp.__class__.__name__))
    except Exception:
        pass

    try:
        for comp in game_object.get_py_components():
            add(getattr(comp, "type_name", comp.__class__.__name__))
    except Exception:
        pass

    return types


def _build_entity_record(game_object: Any) -> EntityRecord:
    parent = None
    children_ids: list[int | str] = []

    try:
        parent_obj = game_object.get_parent()
        if parent_obj is not None:
            parent = getattr(parent_obj, "id", None)
    except Exception:
        parent = None

    try:
        for child in game_object.get_children():
            child_id = getattr(child, "id", None)
            if child_id is not None:
                children_ids.append(child_id)
    except Exception:
        pass

    entity_id = getattr(game_object, "id", None)
    if entity_id is None:
        raise ValueError("GameObject is missing a valid id")

    return EntityRecord(
        id=entity_id,
        name=getattr(game_object, "name", ""),
        parent_id=parent,
        children_ids=children_ids,
        component_types=_iter_component_types(game_object),
    )


def list_entities() -> list[EntityRecord]:
    scene = _get_active_scene()
    if scene is None:
        return []

    records: list[EntityRecord] = []
    try:
        game_objects: Iterable[Any] = scene.get_all_objects()
    except Exception:
        return []

    for game_object in game_objects:
        try:
            records.append(_build_entity_record(game_object))
        except Exception:
            continue
    return records


def get_entity(entity_id: int | str) -> EntityRecord | None:
    scene = _get_active_scene()
    if scene is None:
        return None

    try:
        found = scene.find_by_id(entity_id)
    except Exception:
        return None

    if found is None:
        return None
    try:
        return _build_entity_record(found)
    except Exception:
        return None


class WorldStateProjection:
    @staticmethod
    def list_entities() -> list[EntityRecord]:
        return list_entities()

    @staticmethod
    def get_entity(entity_id: int | str) -> EntityRecord | None:
        return get_entity(entity_id)


__all__ = [
    "EntityRecord",
    "WorldStateProjection",
    "get_active_scene",
    "get_entity",
    "list_entities",
    "normalize_type_name",
]
