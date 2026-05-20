from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AI_RUNTIME_DIR = ROOT / "Infernux" / "ai_runtime"


def _ensure_package(monkeypatch, name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_module(monkeypatch, module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, AI_RUNTIME_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


class _Vec3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _FakeComponent:
    def __init__(self, type_name: str, component_id: int, **fields):
        self.type_name = type_name
        self.component_id = component_id
        self.enabled = True
        for key, value in fields.items():
            setattr(self, key, value)


class _FakeTransform(_FakeComponent):
    def __init__(self, component_id: int = 100):
        super().__init__(
            "Transform",
            component_id,
            position=_Vec3(),
            local_position=_Vec3(),
            euler_angles=_Vec3(),
            local_euler_angles=_Vec3(),
            local_scale=_Vec3(1.0, 1.0, 1.0),
        )


class _FakeGameObject:
    def __init__(self, entity_id: int, name: str):
        self.id = entity_id
        self.name = name
        self.active = True
        self.layer = 0
        self.transform = _FakeTransform(entity_id * 10)
        self._parent = None
        self._children = []
        self._components = []
        self._py_components = []

    def set_parent(self, parent):
        self._parent = parent
        parent._children.append(self)

    def get_parent(self):
        return self._parent

    def get_children(self):
        return list(self._children)

    def get_component(self, component_type):
        if component_type == "Transform":
            return self.transform
        for comp in [*self._components, *self._py_components]:
            if comp.type_name == component_type or type(comp).__name__ == component_type:
                return comp
        return None

    def get_components(self):
        return [self.transform, *self._components]

    def get_py_components(self):
        return list(self._py_components)

    def is_active_in_hierarchy(self):
        if not self.active:
            return False
        return self._parent.is_active_in_hierarchy() if self._parent is not None else True


class _FakeScene:
    name = "fake_scene"
    structure_version = 12

    def __init__(self, objects):
        self._objects = list(objects)

    def get_all_objects(self):
        return list(self._objects)

    def find_by_id(self, entity_id):
        for obj in self._objects:
            if obj.id == entity_id:
                return obj
        return None


def _load_world_model(monkeypatch, scene):
    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")

    fake_scene_manager = types.SimpleNamespace(
        instance=lambda: types.SimpleNamespace(get_active_scene=lambda: scene)
    )
    monkeypatch.setitem(
        sys.modules,
        "Infernux.lib",
        types.SimpleNamespace(SceneManager=fake_scene_manager),
    )

    _load_module(monkeypatch, "Infernux.ai_runtime._coercion", "_coercion.py")
    _load_module(monkeypatch, "Infernux.ai_runtime.capabilities", "capabilities.py")
    _load_module(monkeypatch, "Infernux.ai_runtime.types", "types.py")
    _load_module(monkeypatch, "Infernux.ai_runtime.world_state", "world_state.py")
    return _load_module(monkeypatch, "Infernux.ai_runtime.world_model", "world_model.py")


def test_get_world_snapshot_returns_scene_structure_and_component_fields(monkeypatch):
    root = _FakeGameObject(1, "WorldRoot")
    root.transform.position = _Vec3(1.0, 2.0, 3.0)
    root.layer = 3
    root._components.append(
        _FakeComponent(
            "Rigidbody",
            200,
            mass=4.5,
            velocity=_Vec3(0.0, 0.0, 0.0),
            use_gravity=True,
            world_center_of_mass=_Vec3(9.0, 9.0, 9.0),
        )
    )
    child = _FakeGameObject(2, "WorldChild")
    child.set_parent(root)
    world_model = _load_world_model(monkeypatch, _FakeScene([root, child]))

    snapshot = world_model.get_world_snapshot()

    assert isinstance(snapshot, world_model.WorldSnapshot)
    assert snapshot.scene_name == "fake_scene"
    assert snapshot.structure_version == 12

    root_entity = next(entity for entity in snapshot.entities if entity.name == "WorldRoot")
    child_entity = next(entity for entity in snapshot.entities if entity.name == "WorldChild")
    assert root_entity.id == 1
    assert root_entity.parent_id is None
    assert root_entity.children_ids == [2]
    assert root_entity.path == "WorldRoot"
    assert root_entity.layer == 3
    assert child_entity.parent_id == 1
    assert child_entity.path == "WorldRoot/WorldChild"

    transform = next(component for component in root_entity.components if component.type == "Transform")
    assert transform.fields["position"] == (1.0, 2.0, 3.0)
    assert transform.fields["local_scale"] == (1.0, 1.0, 1.0)

    rigidbody = next(component for component in root_entity.components if component.type == "Rigidbody")
    assert rigidbody.enabled is True
    assert rigidbody.fields["mass"] == 4.5
    assert rigidbody.fields["use_gravity"] is True
    assert "world_center_of_mass" not in rigidbody.fields
    assert snapshot.to_dict()["entities"][0]["components"][0]["type"] == "Transform"


def test_get_component_schema_marks_core_writable_fields_from_capabilities_allowlist(monkeypatch):
    world_model = _load_world_model(monkeypatch, _FakeScene([]))

    transform_schema = world_model.get_component_schema("Transform")
    rigidbody_schema = world_model.get_component_schema("Rigidbody")

    assert isinstance(transform_schema, world_model.ComponentSchema)
    assert transform_schema.fields["position"].core_writable is True
    assert transform_schema.fields["local_scale"].core_writable is False

    assert isinstance(rigidbody_schema, world_model.ComponentSchema)
    assert rigidbody_schema.fields["mass"].core_writable is True
    assert rigidbody_schema.fields["velocity"].core_writable is True
    assert rigidbody_schema.fields["use_gravity"].core_writable is False


def test_capabilities_defines_core_writable_fields_without_native_import(monkeypatch):
    _ensure_package(monkeypatch, "Infernux")
    _ensure_package(monkeypatch, "Infernux.ai_runtime")
    module = _load_module(monkeypatch, "Infernux.ai_runtime.capabilities", "capabilities.py")

    assert module.ALLOWED_COMPONENT_FIELDS == {
        "Transform": {"position"},
        "Rigidbody": {"velocity", "mass"},
    }


def test_get_component_fields_reads_only_core_allowlisted_values(monkeypatch):
    body = _FakeGameObject(7, "Body")
    body._components.append(
        _FakeComponent(
            "Rigidbody",
            70,
            mass=2.25,
            velocity=_Vec3(1.0, 0.0, 0.0),
            use_gravity=False,
        )
    )
    world_model = _load_world_model(monkeypatch, _FakeScene([body]))

    fields = world_model.get_component_fields(7, "Rigidbody")

    assert fields == {
        "mass": 2.25,
        "velocity": (1.0, 0.0, 0.0),
    }


def test_diff_world_snapshots_reports_entities_components_and_field_changes(monkeypatch):
    world_model = _load_world_model(monkeypatch, _FakeScene([]))

    before = world_model.WorldSnapshot(
        scene_name="fake",
        structure_version=1,
        play_mode="edit",
        entities=[],
    )
    after_create = world_model.WorldSnapshot(
        scene_name="fake",
        structure_version=2,
        play_mode="edit",
        entities=[
            world_model.EntityWorldSnapshot(
                id=9,
                name="DiffMover",
                parent_id=None,
                children_ids=[],
                path="DiffMover",
                active=True,
                active_in_hierarchy=True,
                layer=0,
                components=[
                    world_model.ComponentSnapshot(
                        type="Transform",
                        component_id=90,
                        enabled=True,
                        python=False,
                        fields={"position": (0.0, 0.0, 0.0)},
                    )
                ],
            )
        ],
    )
    after_update = world_model.WorldSnapshot(
        scene_name="fake",
        structure_version=3,
        play_mode="edit",
        entities=[
            world_model.EntityWorldSnapshot(
                id=9,
                name="DiffMover",
                parent_id=None,
                children_ids=[],
                path="DiffMover",
                active=True,
                active_in_hierarchy=True,
                layer=0,
                components=[
                    world_model.ComponentSnapshot(
                        type="Transform",
                        component_id=90,
                        enabled=True,
                        python=False,
                        fields={"position": (5.0, 0.0, 0.0)},
                    ),
                    world_model.ComponentSnapshot(
                        type="Rigidbody",
                        component_id=91,
                        enabled=True,
                        python=False,
                        fields={"mass": 1.0},
                    ),
                ],
            )
        ],
    )

    create_diff = world_model.diff_world_snapshots(before, after_create)
    update_diff = world_model.diff_world_snapshots(after_create, after_update)

    assert any(change.entity_id == 9 for change in create_diff.entities_added)
    assert any(
        change.entity_id == 9 and change.component_type == "Rigidbody"
        for change in update_diff.components_added
    )
    assert any(
        change.entity_id == 9
        and change.component_type == "Transform"
        and change.field_path == "position"
        and change.old_value == (0.0, 0.0, 0.0)
        and change.new_value == (5.0, 0.0, 0.0)
        for change in update_diff.fields_changed
    )
