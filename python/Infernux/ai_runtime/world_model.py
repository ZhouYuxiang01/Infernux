from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from . import world_state
from ._coercion import coerce_vec3_tuple
from .capabilities import ALLOWED_COMPONENT_FIELDS


_UNSAFE = object()


@dataclass(frozen=True, slots=True)
class FieldSchema:
    name: str
    type: str
    readable: bool = True
    engine_writable: bool = False
    core_writable: bool = False
    default: Any = None
    range: Any = None
    readonly: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ComponentSchema:
    type: str
    builtin: bool
    fields: dict[str, FieldSchema] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ComponentSnapshot:
    type: str
    component_id: int | None
    enabled: bool | None
    python: bool
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class EntityWorldSnapshot:
    id: int | str
    name: str
    parent_id: int | str | None
    children_ids: list[int | str]
    path: str
    active: bool
    active_in_hierarchy: bool
    layer: int
    components: list[ComponentSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    scene_name: str
    structure_version: int
    play_mode: str
    entities: list[EntityWorldSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class EntityChange:
    entity_id: int | str
    name: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ComponentChange:
    entity_id: int | str
    component_type: str
    component_id: int | None

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class FieldValueChange:
    entity_id: int | str
    component_type: str
    field_path: str
    old_value: Any
    new_value: Any

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class WorldDiff:
    entities_added: list[EntityChange] = field(default_factory=list)
    entities_removed: list[EntityChange] = field(default_factory=list)
    components_added: list[ComponentChange] = field(default_factory=list)
    components_removed: list[ComponentChange] = field(default_factory=list)
    fields_changed: list[FieldValueChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


_FALLBACK_SCHEMAS: dict[str, dict[str, tuple[str, bool, Any]]] = {
    "Transform": {
        "position": ("VEC3", True, (0.0, 0.0, 0.0)),
        "local_position": ("VEC3", True, (0.0, 0.0, 0.0)),
        "euler_angles": ("VEC3", True, (0.0, 0.0, 0.0)),
        "local_euler_angles": ("VEC3", True, (0.0, 0.0, 0.0)),
        "local_scale": ("VEC3", True, (1.0, 1.0, 1.0)),
    },
    "Rigidbody": {
        "mass": ("FLOAT", True, 1.0),
        "velocity": ("VEC3", True, (0.0, 0.0, 0.0)),
        "use_gravity": ("BOOL", True, True),
        "is_kinematic": ("BOOL", True, False),
    },
}


def safe_project_value(value: Any) -> Any:
    projected = _safe_project_value(value)
    return None if projected is _UNSAFE else projected


def get_component_schema(component_type: str) -> ComponentSchema | None:
    component_name = world_state.normalize_type_name(component_type)
    if not component_name:
        return None

    fields: dict[str, FieldSchema] = {}
    builtin = False

    cls = _component_class_for_name(component_name)
    if cls is not None:
        builtin = _is_builtin_component_class(cls)
        fields.update(_fields_from_component_class(component_name, cls))

    if component_name in _FALLBACK_SCHEMAS:
        builtin = True
        fields.update(_fallback_fields(component_name, fields))

    _add_core_writable_fields(component_name, fields)
    if not fields:
        return None

    return ComponentSchema(type=component_name, builtin=builtin, fields=fields)


def get_component_fields(entity_id: int | str, component_name: str) -> dict[str, Any] | None:
    component_type = world_state.normalize_type_name(component_name)
    if component_type not in ALLOWED_COMPONENT_FIELDS:
        return None

    obj = _get_scene_object(entity_id)
    if obj is None:
        return None

    comp = _find_component(obj, component_type)
    if comp is None:
        return None

    result: dict[str, Any] = {}
    for key in sorted(ALLOWED_COMPONENT_FIELDS.get(component_type, set())):
        value = _safe_project_value(getattr(comp, key, None))
        if value is not _UNSAFE:
            result[key] = value
    return result


def get_world_snapshot(
    *,
    include_components: bool = True,
    include_fields: bool = True,
) -> WorldSnapshot:
    scene = world_state.get_active_scene()
    if scene is None:
        return WorldSnapshot(scene_name="", structure_version=0, play_mode=_play_mode_state(), entities=[])

    entities: list[EntityWorldSnapshot] = []
    try:
        objects = list(scene.get_all_objects() or [])
    except Exception:
        objects = []

    for obj in objects:
        entity = _entity_snapshot(obj, include_components=include_components, include_fields=include_fields)
        if entity is not None:
            entities.append(entity)

    return WorldSnapshot(
        scene_name=str(getattr(scene, "name", "") or ""),
        structure_version=_coerce_int(getattr(scene, "structure_version", 0), 0),
        play_mode=_play_mode_state(),
        entities=entities,
    )


def diff_world_snapshots(before: WorldSnapshot | dict[str, Any], after: WorldSnapshot | dict[str, Any]) -> WorldDiff:
    before_snapshot = world_snapshot_from_dict(before) if isinstance(before, dict) else before
    after_snapshot = world_snapshot_from_dict(after) if isinstance(after, dict) else after

    before_entities = {entity.id: entity for entity in before_snapshot.entities}
    after_entities = {entity.id: entity for entity in after_snapshot.entities}

    added = [
        EntityChange(entity_id=entity.id, name=entity.name, path=entity.path)
        for entity_id, entity in after_entities.items()
        if entity_id not in before_entities
    ]
    removed = [
        EntityChange(entity_id=entity.id, name=entity.name, path=entity.path)
        for entity_id, entity in before_entities.items()
        if entity_id not in after_entities
    ]

    components_added: list[ComponentChange] = []
    components_removed: list[ComponentChange] = []
    fields_changed: list[FieldValueChange] = []

    for entity_id in sorted(set(before_entities).intersection(after_entities), key=str):
        old_entity = before_entities[entity_id]
        new_entity = after_entities[entity_id]
        old_components = _component_map(old_entity)
        new_components = _component_map(new_entity)

        for key, component in new_components.items():
            if key not in old_components:
                components_added.append(
                    ComponentChange(entity_id=entity_id, component_type=component.type, component_id=component.component_id)
                )

        for key, component in old_components.items():
            if key not in new_components:
                components_removed.append(
                    ComponentChange(entity_id=entity_id, component_type=component.type, component_id=component.component_id)
                )

        for key in sorted(set(old_components).intersection(new_components), key=str):
            old_component = old_components[key]
            new_component = new_components[key]
            for field_name in sorted(set(old_component.fields).union(new_component.fields)):
                old_value = old_component.fields.get(field_name)
                new_value = new_component.fields.get(field_name)
                if old_value != new_value:
                    fields_changed.append(
                        FieldValueChange(
                            entity_id=entity_id,
                            component_type=new_component.type,
                            field_path=field_name,
                            old_value=old_value,
                            new_value=new_value,
                        )
                    )

    return WorldDiff(
        entities_added=added,
        entities_removed=removed,
        components_added=components_added,
        components_removed=components_removed,
        fields_changed=fields_changed,
    )


def world_snapshot_from_dict(value: dict[str, Any]) -> WorldSnapshot:
    entities = []
    for entity in value.get("entities", []) or []:
        components = [
            ComponentSnapshot(
                type=str(component.get("type", "")),
                component_id=_optional_int(component.get("component_id")),
                enabled=_optional_bool(component.get("enabled")),
                python=bool(component.get("python", False)),
                fields=dict(component.get("fields", {}) or {}),
            )
            for component in entity.get("components", []) or []
            if isinstance(component, dict)
        ]
        entities.append(
            EntityWorldSnapshot(
                id=entity.get("id"),
                name=str(entity.get("name", "")),
                parent_id=entity.get("parent_id"),
                children_ids=list(entity.get("children_ids", []) or []),
                path=str(entity.get("path", "")),
                active=bool(entity.get("active", True)),
                active_in_hierarchy=bool(entity.get("active_in_hierarchy", True)),
                layer=_coerce_int(entity.get("layer"), 0),
                components=components,
            )
        )

    return WorldSnapshot(
        scene_name=str(value.get("scene_name", "")),
        structure_version=_coerce_int(value.get("structure_version"), 0),
        play_mode=str(value.get("play_mode", "")),
        entities=entities,
    )


def _entity_snapshot(obj: Any, *, include_components: bool, include_fields: bool) -> EntityWorldSnapshot | None:
    entity_id = getattr(obj, "id", None)
    if entity_id is None:
        return None

    parent = _safe_parent_id(obj)
    children = _safe_children_ids(obj)
    components = _component_snapshots(obj, include_fields=include_fields) if include_components else []

    return EntityWorldSnapshot(
        id=entity_id,
        name=str(getattr(obj, "name", "") or ""),
        parent_id=parent,
        children_ids=children,
        path=_object_path(obj),
        active=bool(getattr(obj, "active", True)),
        active_in_hierarchy=_active_in_hierarchy(obj),
        layer=_coerce_int(getattr(obj, "layer", 0), 0),
        components=components,
    )


def _component_snapshots(obj: Any, *, include_fields: bool) -> list[ComponentSnapshot]:
    items: list[ComponentSnapshot] = []
    seen: set[tuple[str, int | None]] = set()

    def append(comp: Any, *, is_python: bool) -> None:
        type_name = _component_type_name(comp)
        component_id = _optional_int(getattr(comp, "component_id", None))
        key = (type_name, component_id)
        if component_id is not None and key in seen:
            return
        if component_id is not None:
            seen.add(key)
        items.append(
            ComponentSnapshot(
                type=type_name,
                component_id=component_id,
                enabled=_optional_bool(getattr(comp, "enabled", None)),
                python=is_python,
                fields=_component_read_fields(comp, type_name) if include_fields else {},
            )
        )

    try:
        for comp in obj.get_components() or []:
            append(comp, is_python=False)
    except Exception:
        pass

    try:
        for comp in obj.get_py_components() or []:
            append(comp, is_python=True)
    except Exception:
        pass

    return items


def _component_read_fields(comp: Any, component_type: str) -> dict[str, Any]:
    schema = get_component_schema(component_type)
    if schema is None:
        return {}

    fields: dict[str, Any] = {}
    for key, field_schema in schema.fields.items():
        if not field_schema.readable:
            continue
        try:
            raw = getattr(comp, key)
        except Exception:
            continue
        value = _safe_project_value(raw)
        if value is not _UNSAFE:
            fields[key] = value
    return fields


def _find_component(obj: Any, component_type: str) -> Any:
    try:
        comp = obj.get_component(component_type)
        if comp is not None:
            return comp
    except Exception:
        pass

    for getter_name in ("get_components", "get_py_components"):
        try:
            for comp in getattr(obj, getter_name)() or []:
                if _component_type_name(comp) == component_type or type(comp).__name__ == component_type:
                    return comp
        except Exception:
            pass
    return None


def _component_type_name(comp: Any) -> str:
    return world_state.normalize_type_name(getattr(comp, "type_name", type(comp).__name__))


def _component_class_for_name(component_name: str) -> Any:
    try:
        import Infernux.components.builtin  # noqa: F401
        from Infernux.components.builtin_component import BuiltinComponent

        if component_name in BuiltinComponent._builtin_registry:
            return BuiltinComponent._builtin_registry[component_name]
        for name, cls in BuiltinComponent._builtin_registry.items():
            if cls.__name__ == component_name or name.lower() == component_name.lower():
                return cls
    except Exception:
        pass

    try:
        from Infernux.components.registry import get_type

        return get_type(component_name)
    except Exception:
        return None


def _is_builtin_component_class(cls: Any) -> bool:
    return bool(getattr(cls, "_cpp_type_name", ""))


def _fields_from_component_class(component_name: str, cls: Any) -> dict[str, FieldSchema]:
    try:
        from Infernux.components.serialized_field import get_serialized_fields
    except Exception:
        return {}

    fields: dict[str, FieldSchema] = {}
    try:
        metadata = get_serialized_fields(cls)
    except Exception:
        return {}

    for name, meta in metadata.items():
        field_type = getattr(getattr(meta, "field_type", None), "name", str(getattr(meta, "field_type", "")))
        readonly = bool(getattr(meta, "readonly", False))
        fields[str(name)] = FieldSchema(
            name=str(name),
            type=str(field_type or "UNKNOWN"),
            readable=True,
            engine_writable=not readonly,
            core_writable=_is_core_writable(component_name, str(name)),
            default=safe_project_value(getattr(meta, "default", None)),
            range=safe_project_value(getattr(meta, "range", None)),
            readonly=readonly,
        )
    return fields


def _fallback_fields(component_name: str, existing: dict[str, FieldSchema]) -> dict[str, FieldSchema]:
    fields: dict[str, FieldSchema] = {}
    for name, (field_type, writable, default) in _FALLBACK_SCHEMAS[component_name].items():
        if name in existing:
            continue
        fields[name] = FieldSchema(
            name=name,
            type=field_type,
            readable=True,
            engine_writable=writable,
            core_writable=_is_core_writable(component_name, name),
            default=default,
            readonly=not writable,
        )
    return fields


def _add_core_writable_fields(component_name: str, fields: dict[str, FieldSchema]) -> None:
    for name in sorted(ALLOWED_COMPONENT_FIELDS.get(component_name, set())):
        if name in fields:
            existing = fields[name]
            fields[name] = FieldSchema(
                name=existing.name,
                type=existing.type,
                readable=existing.readable,
                engine_writable=existing.engine_writable,
                core_writable=True,
                default=existing.default,
                range=existing.range,
                readonly=existing.readonly,
            )
            continue
        fields[name] = FieldSchema(
            name=name,
            type="VEC3" if name in {"position", "velocity"} else "FLOAT",
            readable=True,
            engine_writable=True,
            core_writable=True,
            default=(0.0, 0.0, 0.0) if name in {"position", "velocity"} else 1.0,
            readonly=False,
        )


def _is_core_writable(component_name: str, field_name: str) -> bool:
    return field_name in ALLOWED_COMPONENT_FIELDS.get(component_name, set())


def _get_scene_object(entity_id: int | str) -> Any:
    scene = world_state.get_active_scene()
    if scene is None:
        return None
    finder = getattr(scene, "find_by_id", None)
    if not callable(finder):
        return None
    try:
        return finder(entity_id)
    except Exception:
        return None


def _safe_parent_id(obj: Any) -> int | str | None:
    try:
        parent = obj.get_parent()
    except Exception:
        parent = None
    return getattr(parent, "id", None) if parent is not None else None


def _safe_children_ids(obj: Any) -> list[int | str]:
    children: list[int | str] = []
    try:
        raw_children = obj.get_children() or []
    except Exception:
        return children
    for child in raw_children:
        child_id = getattr(child, "id", None)
        if child_id is not None:
            children.append(child_id)
    return children


def _object_path(obj: Any) -> str:
    parts: list[str] = []
    current = obj
    while current is not None:
        parts.append(str(getattr(current, "name", "") or ""))
        try:
            current = current.get_parent()
        except Exception:
            current = None
    return "/".join(reversed([part for part in parts if part]))


def _active_in_hierarchy(obj: Any) -> bool:
    checker = getattr(obj, "is_active_in_hierarchy", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            pass
    return bool(getattr(obj, "active_in_hierarchy", getattr(obj, "active", True)))


def _play_mode_state() -> str:
    try:
        from Infernux.engine.play_mode import PlayModeManager

        manager = PlayModeManager.instance()
        if manager is not None:
            state = getattr(manager, "state", None)
            name = getattr(state, "name", None)
            if name:
                return str(name).lower()
            if bool(getattr(manager, "is_paused", False)):
                return "paused"
            if bool(getattr(manager, "is_playing", False)):
                return "playing"
    except Exception:
        pass
    return "edit"


def _safe_project_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    vec3 = coerce_vec3_tuple(value)
    if vec3 is not None:
        return vec3

    if hasattr(value, "name") and hasattr(value, "value"):
        try:
            return {"name": str(value.name), "value": int(value.value)}
        except Exception:
            return _UNSAFE

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            projected = _safe_project_value(item)
            if projected is not _UNSAFE:
                result[str(key)] = projected
        return result

    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            projected = _safe_project_value(item)
            if projected is _UNSAFE:
                return _UNSAFE
            result.append(projected)
        return result

    return _UNSAFE


def _component_map(entity: EntityWorldSnapshot) -> dict[tuple[str, int | None, int], ComponentSnapshot]:
    result: dict[tuple[str, int | None, int], ComponentSnapshot] = {}
    ordinal_by_type: dict[str, int] = {}
    for component in entity.components:
        ordinal = ordinal_by_type.get(component.type, 0)
        ordinal_by_type[component.type] = ordinal + 1
        result[(component.type, component.component_id, ordinal if component.component_id is None else -1)] = component
    return result


def _dataclass_to_dict(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        return {}
    return asdict(value)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        return bool(value)
    except Exception:
        return None


__all__ = [
    "ComponentChange",
    "ComponentSchema",
    "ComponentSnapshot",
    "EntityChange",
    "EntityWorldSnapshot",
    "FieldSchema",
    "FieldValueChange",
    "WorldDiff",
    "WorldSnapshot",
    "diff_world_snapshots",
    "get_component_fields",
    "get_component_schema",
    "get_world_snapshot",
    "safe_project_value",
    "world_snapshot_from_dict",
]
