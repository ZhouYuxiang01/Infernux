"""Prefab actions and clipboard operations for the Hierarchy panel."""
from __future__ import annotations

from Infernux.debug import Debug
from Infernux.engine.bootstrap_hierarchy._helpers import _get_children_safe


def _resolve_prefab(guid):
    """Resolve a prefab GUID to a file path, or ``None``."""
    if not guid:
        return None
    try:
        from Infernux.lib import AssetRegistry
        registry = AssetRegistry.instance()
        if registry:
            adb = registry.get_asset_database()
            if adb:
                return adb.get_path_from_guid(guid)
    except Exception as _exc:
        Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
    return None


def wire_prefab_actions(ctx):
    """Wire all prefab-related callbacks onto the hierarchy panel."""
    hp = ctx.hp
    EditorEventBus = ctx.EditorEventBus

    def _save_as_prefab(oid):
        from Infernux.lib import SceneManager, AssetRegistry
        from Infernux.engine.project_context import get_project_root
        from Infernux.engine.prefab_manager import save_prefab, PREFAB_EXTENSION
        import os
        scene = SceneManager.instance().get_active_scene()
        if not scene:
            return
        go = scene.find_by_id(oid)
        if not go:
            return
        root = get_project_root()
        if not root:
            return
        assets_dir = os.path.join(root, "Assets")
        os.makedirs(assets_dir, exist_ok=True)
        adb = None
        registry = AssetRegistry.instance()
        if registry:
            adb = registry.get_asset_database()
        from Infernux.engine.ui.project_file_ops import get_unique_name
        prefab_name = get_unique_name(assets_dir, go.name, PREFAB_EXTENSION)
        file_path = os.path.join(assets_dir, prefab_name + PREFAB_EXTENSION)
        if save_prefab(go, file_path, asset_database=adb):
            Debug.log_internal(f"Prefab saved: {file_path}")

    def _prefab_select_asset(oid):
        from Infernux.lib import SceneManager
        scene = SceneManager.instance().get_active_scene()
        go = scene.find_by_id(oid) if scene else None
        if not go:
            return
        guid = getattr(go, 'prefab_guid', '')
        path = _resolve_prefab(guid)
        if path:
            EditorEventBus.instance().emit("select_asset", path)

    def _prefab_open_asset(oid):
        from Infernux.lib import SceneManager
        scene = SceneManager.instance().get_active_scene()
        go = scene.find_by_id(oid) if scene else None
        if not go:
            return
        guid = getattr(go, 'prefab_guid', '')
        path = _resolve_prefab(guid)
        if path:
            EditorEventBus.instance().emit("open_asset", path)

    def _prefab_apply_overrides(oid):
        from Infernux.lib import SceneManager
        scene = SceneManager.instance().get_active_scene()
        go = scene.find_by_id(oid) if scene else None
        if not go:
            return
        guid = getattr(go, 'prefab_guid', '')
        path = _resolve_prefab(guid)
        if path:
            from Infernux.engine.prefab_overrides import apply_overrides_to_prefab
            apply_overrides_to_prefab(go, path)

    def _prefab_revert_overrides(oid):
        from Infernux.lib import SceneManager
        scene = SceneManager.instance().get_active_scene()
        go = scene.find_by_id(oid) if scene else None
        if not go:
            return
        guid = getattr(go, 'prefab_guid', '')
        path = _resolve_prefab(guid)
        if path:
            from Infernux.engine.prefab_overrides import revert_overrides
            revert_overrides(go, path)

    def _prefab_unpack(oid):
        from Infernux.lib import SceneManager
        scene = SceneManager.instance().get_active_scene()
        go = scene.find_by_id(oid) if scene else None
        if not go:
            return
        _unpack_recursive(go)
        Debug.log_internal(f"Unpacked prefab instance: {go.name}")

    def _unpack_recursive(obj):
        try:
            obj.prefab_guid = ""
            obj.prefab_root = False
        except Exception as _exc:
            Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
        try:
            for child in _get_children_safe(obj):
                _unpack_recursive(child)
        except Exception as _exc:
            Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")

    hp.save_as_prefab = _save_as_prefab
    hp.prefab_select_asset = _prefab_select_asset
    hp.prefab_open_asset = _prefab_open_asset
    hp.prefab_apply_overrides = _prefab_apply_overrides
    hp.prefab_revert_overrides = _prefab_revert_overrides
    hp.prefab_unpack = _prefab_unpack


def wire_clipboard(ctx):
    """Wire cut/copy/paste clipboard operations."""
    hp = ctx.hp
    bs = ctx.bs
    sel = ctx.sel

    _clipboard = {"entries": [], "cut": False}

    def _copy_selected(cut):
        from Infernux.lib import SceneManager
        scene = SceneManager.instance().get_active_scene()
        if not scene:
            return False
        ids = sel.get_ids()
        if not ids:
            return False
        selected_set = set(ids)
        roots = []
        for oid in ids:
            obj = scene.find_by_id(oid)
            if obj is None:
                continue
            parent = obj.get_parent()
            skip = False
            while parent is not None:
                if parent.id in selected_set:
                    skip = True
                    break
                parent = parent.get_parent()
            if not skip:
                roots.append(obj)
        if not roots:
            return False
        entries = []
        for obj in roots:
            parent = obj.get_parent()
            transform = getattr(obj, "transform", None)
            entries.append({
                "json": obj.serialize(),
                "source_parent_id": parent.id if parent else None,
                "source_sibling_index": transform.get_sibling_index() if transform else 0,
                "source_world_position": transform.position.to_tuple() if transform else None,
                "source_world_rotation": transform.rotation.to_tuple() if transform else None,
            })
        _clipboard["entries"] = entries
        _clipboard["cut"] = bool(cut)
        if cut:
            from Infernux.engine.undo import CompoundCommand, DeleteGameObjectCommand, UndoManager
            commands = [DeleteGameObjectCommand(obj.id, "Cut GameObject") for obj in roots]
            mgr = UndoManager.instance()
            if mgr:
                cmd = commands[0] if len(commands) == 1 else CompoundCommand(commands, "Cut GameObjects")
                mgr.execute(cmd)
            else:
                sfm2 = bs.scene_file_manager
                for obj in roots:
                    live = scene.find_by_id(obj.id)
                    if live:
                        scene.destroy_game_object(live)
                if sfm2:
                    sfm2.mark_dirty()
            sel.clear()
            if hp.on_selection_changed:
                hp.on_selection_changed(0)
        return True

    def _paste_clipboard():
        if not _clipboard["entries"]:
            return False
        from Infernux.lib import SceneManager, Vector3, quatf
        from Infernux.engine.undo import CompoundCommand, CreateGameObjectCommand, UndoManager
        from Infernux.engine.component_restore import restore_pending_py_components
        from Infernux.engine.prefab_manager import _strip_prefab_runtime_fields
        import json
        scene = SceneManager.instance().get_active_scene()
        if not scene:
            return False
        anchor = scene.find_by_id(sel.get_primary()) if sel.count() >= 1 else None
        anchor_parent = anchor.get_parent() if anchor else None
        anchor_index = anchor.transform.get_sibling_index() if anchor and getattr(anchor, "transform", None) else -1
        anchor_insert_index = anchor_index + 1 if anchor_index >= 0 else None
        per_parent_insert_offsets = {}
        created = []
        for entry in _clipboard["entries"]:
            src_parent = None
            src_pid = entry.get("source_parent_id")
            if src_pid is not None:
                src_parent = scene.find_by_id(src_pid)
            parent = anchor_parent if anchor is not None else src_parent
            try:
                obj_data = json.loads(entry["json"])
            except Exception as _exc:
                Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")
                continue
            _strip_prefab_runtime_fields(obj_data)
            new_obj = scene.instantiate_from_json(json.dumps(obj_data), src_parent)
            if new_obj:
                if new_obj.get_parent() is not parent:
                    new_obj.set_parent(parent, True)
                transform = getattr(new_obj, "transform", None)
                if transform is not None:
                    world_position = entry.get("source_world_position")
                    if world_position and len(world_position) == 3:
                        transform.position = Vector3(float(world_position[0]), float(world_position[1]), float(world_position[2]))
                    world_rotation = entry.get("source_world_rotation")
                    if world_rotation and len(world_rotation) == 4:
                        transform.rotation = quatf(float(world_rotation[0]), float(world_rotation[1]),
                                                   float(world_rotation[2]), float(world_rotation[3]))
                    if anchor_insert_index is not None:
                        base_index = anchor_insert_index
                    else:
                        base_index = int(entry.get("source_sibling_index", 0)) + 1
                    parent_key = parent.id if parent else 0
                    offset = per_parent_insert_offsets.get(parent_key, 0)
                    transform.set_sibling_index(max(0, base_index + offset))
                    per_parent_insert_offsets[parent_key] = offset + 1
                created.append(new_obj)
        if created and scene.has_pending_py_components():
            sfm2 = bs.scene_file_manager
            adb = getattr(sfm2, "_asset_database", None) if sfm2 else None
            restore_pending_py_components(scene, asset_database=adb)
        if not created:
            return False
        cids = [o.id for o in created]
        cmds = [CreateGameObjectCommand(cid, "Paste GameObject") for cid in cids]
        mgr = UndoManager.instance()
        if mgr:
            cmd = cmds[0] if len(cmds) == 1 else CompoundCommand(cmds, "Paste GameObjects")
            mgr.record(cmd)
        else:
            sfm2 = bs.scene_file_manager
            if sfm2:
                sfm2.mark_dirty()
        sel.set_ids(cids)
        if hp.on_selection_changed:
            hp.on_selection_changed(cids[-1] if cids else 0)
        if _clipboard["cut"]:
            _clipboard["entries"] = []
            _clipboard["cut"] = False
        return True

    hp.copy_selected = _copy_selected
    hp.paste_clipboard = _paste_clipboard
    hp.has_clipboard_data = lambda: bool(_clipboard["entries"])

    scene_view = getattr(bs, "scene_view", None)
    if scene_view is not None and hasattr(scene_view, "set_object_clipboard_handlers"):
        scene_view.set_object_clipboard_handlers(
            _copy_selected,
            _paste_clipboard,
            lambda: bool(_clipboard["entries"]),
        )

    engine = getattr(bs, "engine", None)
    if engine is not None:
        from Infernux.debug import Debug
        from Infernux.lib import InxGUIRenderable, InxGUIContext
        from Infernux.engine.ui.closable_panel import ClosablePanel
        from Infernux.engine.ui import imgui_keys as _keys

        class _SceneHierarchyClipboardShortcuts(InxGUIRenderable):
            def on_render(self, ctx: InxGUIContext):
                if ClosablePanel.get_active_panel_id() != "scene_view":
                    return
                if ctx.want_text_input():
                    return
                ctrl = ctx.is_key_down(_keys.KEY_LEFT_CTRL) or ctx.is_key_down(_keys.KEY_RIGHT_CTRL)
                if not ctrl:
                    return
                try:
                    if ctx.is_key_pressed(_keys.KEY_C):
                        _copy_selected(False)
                    elif ctx.is_key_pressed(_keys.KEY_X):
                        _copy_selected(True)
                    elif ctx.is_key_pressed(_keys.KEY_V) and _clipboard["entries"]:
                        _paste_clipboard()
                except Exception as _exc:
                    Debug.log(f"[Suppressed] {type(_exc).__name__}: {_exc}")

        bs._scene_hierarchy_clipboard_shortcuts = _SceneHierarchyClipboardShortcuts()
        engine.register_gui("scene_hierarchy_clipboard_shortcuts", bs._scene_hierarchy_clipboard_shortcuts)
