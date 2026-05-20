"""Self-description and workflow documentation MCP tools."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from Infernux.mcp import capabilities, server
from Infernux.mcp.threading import MainThreadCommandQueue
from Infernux.mcp.tools.common import (
    MCP_PROTOCOL_VERSION,
    MCP_SERVER_VERSION,
    get_asset_database,
    get_tool_metadata,
    list_tool_metadata,
    main_thread,
    ok,
    register_tool_metadata,
    scene_status,
)


CONCEPTS: dict[str, dict[str, Any]] = {
    "Scene": {
        "summary": "A loaded world containing root GameObjects and their children.",
        "notes": [
            "Scene object IDs are editor-session IDs; reacquire them after reload.",
            "Use scene_inspect for a compact map and scene_get_hierarchy for nested structure.",
        ],
        "tools": ["scene_inspect", "scene_get_hierarchy", "scene_save", "scene_open", "scene_new"],
    },
    "GameObject": {
        "summary": "A scene entity with a Transform and zero or more Components.",
        "notes": [
            "Every GameObject has a Transform.",
            "Use stable names and hierarchy paths for generated content so agents can find it later.",
        ],
        "tools": ["hierarchy_create_object", "gameobject_find", "gameobject_get", "gameobject_set_parent"],
    },
    "Transform": {
        "summary": "Position, rotation, scale, and hierarchy relationship for a GameObject.",
        "notes": [
            "World fields: position/euler_angles.",
            "Local fields: local_position/local_euler_angles/local_scale.",
        ],
        "tools": ["transform_set", "gameobject_set_parent", "camera_attach_to_target"],
    },
    "Component": {
        "summary": "Behavior or data attached to a GameObject.",
        "notes": [
            "Built-in components are backed by C++ wrappers.",
            "Python components inherit InxComponent and can expose serialized_field metadata.",
        ],
        "tools": ["component_list_types", "component_describe_type", "gameobject_add_component"],
    },
    "Python Component": {
        "summary": "User-authored gameplay script inheriting from Infernux.components.InxComponent.",
        "notes": [
            "Lifecycle methods include awake, start, update, late_update, on_enable, on_disable, on_destroy.",
            "Use asset_write_text to create scripts, asset_refresh to import them, and gameobject_add_component with script_path to attach.",
        ],
        "tools": ["asset_write_text", "asset_refresh", "gameobject_add_component", "runtime_read_errors"],
    },
    "Builtin Component": {
        "summary": "A C++ engine component exposed through Python wrapper metadata.",
        "notes": [
            "Examples: Camera, Light, MeshRenderer, Rigidbody, BoxCollider.",
            "Use component_describe_type before setting fields.",
        ],
        "tools": ["component_list_types", "component_describe_type", "component_set_field"],
    },
    "AssetDatabase": {
        "summary": "Tracks Assets/ files and maps project paths to GUIDs.",
        "notes": [
            "Generated or agent-authored files should follow the user's requested path or the existing project/module structure.",
            "Call asset_refresh after external writes if the editor does not auto-import immediately.",
        ],
        "tools": ["asset_list", "asset_search", "asset_resolve", "asset_refresh"],
    },
    "PlayMode": {
        "summary": "Runtime simulation mode with editor-scene isolation.",
        "notes": [
            "Use editor_play, runtime_wait, runtime_read_errors, then editor_stop for validation.",
            "Script load errors can block entering Play Mode.",
        ],
        "tools": ["editor_play", "runtime_wait", "runtime_run_for", "runtime_read_errors", "editor_stop"],
    },
    "Camera": {
        "summary": "Rendering view for Game View. Agents should reuse Main Camera when present.",
        "notes": [
            "Use camera_ensure_main instead of blindly creating another camera.",
            "Card games usually want an orthographic camera; third-person games usually attach camera to a target.",
        ],
        "tools": ["camera_find_main", "camera_ensure_main", "camera_setup_2d_card_game", "camera_setup_third_person"],
    },
    "UI Canvas": {
        "summary": "Root object for UI elements such as text and buttons.",
        "notes": [
            "UI tools are planned as semantic wrappers; low-level creation can use hierarchy_create_object with ui.* kinds.",
        ],
        "tools": ["hierarchy_create_object", "workflow_help"],
    },
    "Input": {
        "summary": "Runtime input facade used by Python components.",
        "notes": [
            "Use Infernux.input.Input.get_axis('Horizontal') and get_axis('Vertical') for WASD movement.",
            "Physical keyboard and mouse input are Game View focus-gated.",
            "Generic AI ControlSignal axes remain readable by Input.get_axis even when the Game View is not focused.",
        ],
        "tools": ["runtime_submit_control", "runtime_clear_control", "asset_write_text", "runtime_run_for"],
    },
    "AI Runtime Core": {
        "summary": "Semantics-free runtime surface for external agents.",
        "notes": [
            "The engine is not the agent; it is the world runtime that agents observe, control, edit, and verify.",
            "Gameplay semantics belong in adapters or external agent policy, not in Infernux.ai_runtime core.",
            "Use observation/schema/diff APIs before mutation and runtime_read_errors after execution.",
        ],
        "tools": ["agent_bootstrap", "runtime_explain_current_scene", "runtime_get_world_snapshot", "runtime_experiment_begin"],
    },
    "World Model": {
        "summary": "Structured active-scene snapshot, component schema, field reads, and diffs.",
        "notes": [
            "Use runtime_get_world_snapshot to establish current state.",
            "Use runtime_get_component_schema before field edits.",
            "Use runtime_diff_world_snapshots to verify what actually changed.",
        ],
        "tools": ["runtime_get_world_snapshot", "runtime_get_component_schema", "runtime_diff_world_snapshots"],
    },
    "ControlSignal": {
        "summary": "Generic input signal with opaque axes/buttons, channel_id, duration_ms, and agent_id.",
        "notes": [
            "Axes and buttons are not gameplay actions; adapters or scripts decide how to interpret them.",
            "Use duration_ms for self-releasing runtime input.",
            "Call runtime_clear_control after experiments or on failure.",
        ],
        "tools": ["runtime_submit_control", "runtime_clear_control", "runtime_run_for"],
    },
    "Runtime Experiment Guard": {
        "summary": "Executable guard for agent runtime experiments.",
        "notes": [
            "Begin a guarded experiment before Play Mode control when repeatability matters.",
            "Mark the health check before submitting guarded control.",
            "Do not mix different control paths inside one active experiment.",
        ],
        "tools": [
            "runtime_experiment_begin",
            "runtime_experiment_mark_health_check",
            "runtime_experiment_status",
            "runtime_experiment_end",
        ],
    },
    "World Edit Transaction": {
        "summary": "Preview, validate, commit, or rollback bounded Core world edits.",
        "notes": [
            "Transactions wrap the same bounded move/set allowlist as Infernux.ai_runtime.world_edit.",
            "Preview before commit and verify with runtime_diff_world_snapshots.",
            "Rollback is best-effort and depends on old values being readable before commit.",
        ],
        "tools": ["runtime_edit_transaction_preview", "runtime_edit_transaction_commit", "runtime_diff_world_snapshots"],
    },
    "Undo": {
        "summary": "Editor undo/dirty tracking layer for hierarchy and inspector changes.",
        "notes": [
            "MCP mutation tools should mark scenes/assets dirty or call editor undo helpers when available.",
        ],
        "tools": ["gameobject_set", "component_set_field", "scene_save"],
    },
}


WORKFLOWS: dict[str, dict[str, Any]] = {
    "physics_test_scene": {
        "summary": "Create a ground plane, dynamic cube, collider, rigidbody, light, and camera.",
        "steps": [
            "Call camera_ensure_main or camera_setup_third_person rather than creating duplicate cameras.",
            "Create primitive.plane and add BoxCollider.",
            "Create primitive.cube, add BoxCollider and Rigidbody.",
            "Run editor_play, runtime_wait, runtime.read_errors.",
        ],
        "tools": ["hierarchy_create_object", "gameobject_add_component", "transform_set", "editor_play"],
    },
    "third_person_controller": {
        "summary": "Create a controllable character with a following camera.",
        "steps": [
            "Write an InxComponent script with Input.get_axis and Rigidbody.velocity.",
            "Create or reuse a player GameObject.",
            "Use camera_ensure_main, then camera_attach_to_target or camera.setup_third_person.",
            "Enter Play Mode and validate with runtime.get_object_state.",
        ],
        "tools": ["asset_write_text", "gameobject_add_component", "camera_setup_third_person", "runtime_read_errors"],
    },
    "card_game_shell": {
        "summary": "Create folders, scripts, JSON data, orthographic camera, and UI roots for a Balatro-style prototype.",
        "steps": [
            "Create project folders under the user-requested feature/module path, such as Assets/<FeatureName>/Scripts, Data, Materials, Scenes.",
            "Write data model and controller scripts.",
            "Use camera.setup_2d_card_game.",
            "Create UI Canvas hierarchy for menu, run screen, hand, shop, and game over.",
            "Run Play Mode and validate console/runtime state.",
        ],
        "tools": ["asset_write_text", "asset_write_json", "camera_setup_2d_card_game", "runtime_read_errors"],
    },
    "script_attach_play_validate": {
        "summary": "Write a gameplay script, attach it, play, read errors, stop.",
        "steps": [
            "asset_write_text(path='Assets/.../MyComponent.py')",
            "asset_refresh",
            "gameobject_add_component(component_type='MyComponent', script_path='Assets/.../MyComponent.py')",
            "editor_play",
            "runtime_wait(play_state='playing')",
            "runtime_read_errors",
        ],
        "tools": ["asset_write_text", "asset_refresh", "gameobject_add_component", "editor_play", "runtime_read_errors"],
    },
    "agent_first_contact": {
        "summary": "First sequence for a model or coding agent that has never seen Infernux.",
        "steps": [
            "Call agent_bootstrap to learn the boundary, rules, startup sequence, and recipes.",
            "Call mcp_health to confirm the editor, scene, queue, and asset database are ready.",
            "Call runtime_experiment_begin and runtime_experiment_mark_health_check before Play Mode experiments.",
            "Call runtime_explain_current_scene for a compact current-scene brief.",
            "Call runtime_get_world_snapshot before mutating anything.",
            "Choose the smallest recipe that matches the task and verify with diff/assert/errors.",
        ],
        "tools": [
            "agent_bootstrap",
            "mcp_health",
            "runtime_experiment_begin",
            "runtime_experiment_mark_health_check",
            "runtime_explain_current_scene",
            "runtime_get_world_snapshot",
            "runtime_read_errors",
        ],
    },
    "agent_control_loop": {
        "summary": "Observe the world, submit generic runtime control, run briefly, and verify the result.",
        "steps": [
            "runtime_experiment_begin(mode='run')",
            "runtime_experiment_mark_health_check() after mcp_health succeeds",
            "runtime_get_world_snapshot(include_components=true, include_fields=true)",
            "runtime_submit_control(channel_id=0, axes={...}, duration_ms=<short>, agent_id=0)",
            "runtime_run_for(seconds=<small>, stop_on_error=true)",
            "runtime_get_object_state or runtime_get_world_snapshot",
            "runtime_clear_control(channel_id=0)",
            "runtime_experiment_end()",
            "runtime_read_errors(include_warnings=false)",
        ],
        "tools": [
            "runtime_experiment_begin",
            "runtime_experiment_mark_health_check",
            "runtime_get_world_snapshot",
            "runtime_submit_control",
            "runtime_run_for",
            "runtime_clear_control",
            "runtime_experiment_end",
            "runtime_read_errors",
        ],
    },
    "agent_world_edit_verify": {
        "summary": "Perform a bounded world edit and verify it with snapshots and diff.",
        "steps": [
            "runtime_get_world_snapshot before the edit.",
            "Use schema/query tools to resolve exact targets.",
            "Preview one bounded transaction with runtime_edit_transaction_preview.",
            "Commit only the previewed bounded transaction with runtime_edit_transaction_commit.",
            "runtime_get_world_snapshot after the edit.",
            "runtime_diff_world_snapshots to verify the intended change.",
            "scene_save only when the edit should persist.",
        ],
        "tools": [
            "runtime_get_world_snapshot",
            "runtime_get_component_schema",
            "runtime_edit_transaction_preview",
            "runtime_edit_transaction_commit",
            "runtime_diff_world_snapshots",
            "scene_save",
        ],
    },
}


INTENT_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "camera_frame_subject": {
        "match": ["camera", "frame", "view", "visible", "subject", "target", "照全", "相机", "主体", "看不全"],
        "summary": "Diagnose the main camera view and frame likely subject objects.",
        "tools": [
            "mcp_catalog_search",
            "scene_query_summary",
            "scene_query_subjects",
            "camera_find_main",
            "camera_visibility_report",
            "camera_frame_targets",
        ],
    },
    "find_scene_objects": {
        "match": ["find", "query", "object", "name", "component", "gameobject", "查找", "物体", "名字"],
        "summary": "Find GameObjects by name, path, component, tag, layer, or activity.",
        "tools": ["scene_query_objects", "gameobject_get", "gameobject_describe_spatial"],
    },
    "renderstack_postprocess": {
        "match": ["renderstack", "render stack", "postprocess", "bloom", "pipeline", "渲染", "后处理"],
        "summary": "Inspect and edit the scene RenderStack pipeline and effects.",
        "tools": [
            "renderstack_find_or_create",
            "renderstack_inspect",
            "renderstack_list_pipelines",
            "renderstack_list_passes",
            "renderstack_add_pass",
            "renderstack_set_pass_params",
        ],
    },
    "shader_authoring": {
        "match": ["shader", "glsl", "material", "fragment", "vertex", "shadingmodel", "着色器", "材质"],
        "summary": "Discover shader architecture, annotations, property declarations, and material binding rules.",
        "tools": ["shader_guide", "shader_catalog", "shader_describe", "api_get", "material_create", "asset_create_builtin_resource"],
    },
    "audio_authoring": {
        "match": ["audio", "sound", "music", "sfx", "listener", "audiosource", "audioclip", "音频", "声音"],
        "summary": "Understand AudioSource multi-track playback, AudioClip loading, and AudioListener placement.",
        "tools": ["audio_guide", "api_get", "component_describe_type", "gameobject_add_component"],
    },
}


def register_docs_tools(mcp, project_path: str, config: dict[str, Any] | None = None) -> None:
    config = config or capabilities.current_config()
    _register_metadata()

    @mcp.tool(name="mcp_ping")
    def mcp_ping() -> dict:
        """Return a lightweight MCP liveness response."""
        return ok({"pong": True, "endpoint": server.endpoint_url()})

    @mcp.tool(name="mcp_version")
    def mcp_version() -> dict:
        """Return MCP server version and protocol information."""
        return ok({
            "server": "Infernux Editor",
            "mcp_server_version": MCP_SERVER_VERSION,
            "protocol_version": MCP_PROTOCOL_VERSION,
            "endpoint": server.endpoint_url(),
        })

    @mcp.tool(name="mcp_discovery")
    def mcp_discovery() -> dict:
        """Return connection info and project-local discovery file locations."""
        info = server.connection_info()
        return ok({
            **info,
            "project_root": project_path,
            "files": {
                name: client["file"]
                for name, client in info.get("clients", {}).items()
            },
            "config_snippets": {
                name: client.get("config") or client.get("toml")
                for name, client in info.get("clients", {}).items()
            },
        })

    @mcp.tool(name="mcp_capabilities")
    def mcp_capabilities() -> dict:
        """Return high-level capability groups and known tool names."""
        return ok({
            "agent_guidance": [
                "If you are a new agent, call agent_bootstrap first, then runtime_explain_current_scene.",
                "Infernux APIs are new and engine-specific. Do not guess unfamiliar Python, component, shader, audio, or UI APIs.",
                "Use api_search(query) and api_get(name) for Python/stub-backed APIs before writing scripts.",
                "Use component_describe_type(component_type) before mutating component fields.",
                "Use shader_guide, shader_catalog, and shader_describe before creating or binding shaders.",
                "Some write tools require a knowledge_token from the matching guide, e.g. shader_guide, audio_guide, or api_get('ui').",
                "Use mcp_catalog_search or mcp_catalog_recommend before selecting MCP tools.",
            ],
            "catalog": _catalog_tree(),
            "groups": {
                "foundation": ["agent_bootstrap", "runtime_explain_current_scene", "mcp_ping", "mcp_version", "mcp_discovery", "mcp_health", "mcp_help", "mcp_catalog_list"],
                "api": ["api_subsystems", "api_search", "api_get", "shader_guide", "audio_guide"],
                "shader": ["shader_guide", "shader_catalog", "shader_describe"],
                "audio": ["audio_guide", "component_describe_type"],
                "self_description": ["engine_concepts", "engine_concept_get", "workflow_list", "workflow_help"],
                "scene": ["scene_status", "scene_inspect", "scene_get_hierarchy", "scene_query_summary", "scene_query_objects"],
                "scene_lifecycle": ["scene_save", "scene_open", "scene_new"],
                "gameobject": ["hierarchy_create_object", "gameobject_find", "gameobject_get", "gameobject_describe_spatial"],
                "component": ["component_list_types", "component_describe_type", "component_set_field"],
                "asset": ["asset_ensure_folder", "asset_list", "asset_search", "asset_read_text", "asset_write_text", "asset_refresh"],
                "camera": ["camera_find_main", "camera_describe_view", "camera_visibility_report", "camera_frame_targets"],
                "renderstack": ["renderstack_inspect", "renderstack_list_pipelines", "renderstack_add_pass", "renderstack_set_pass_params"],
                "runtime": [
                    "editor_play",
                    "runtime_wait",
                    "runtime_experiment_begin",
                    "runtime_experiment_mark_health_check",
                    "runtime_experiment_status",
                    "runtime_experiment_end",
                    "runtime_get_world_snapshot",
                    "runtime_submit_control",
                    "runtime_clear_control",
                    "runtime_run_for",
                    "runtime_read_errors",
                ],
                "project_tools": ["project_tools_list", "project_tools_reload", "project_tools_validate", "project_tools_audit"],
                "trace": ["mcp_trace_start", "mcp_trace_stop", "mcp_trace_current", "mcp_trace_list"],
                "session_log": ["mcp_session_log_info", "mcp_session_log_read", "mcp_session_log_clear"],
                "transactions": [
                    "runtime_edit_transaction_preview",
                    "runtime_edit_transaction_commit",
                    "transaction_begin",
                    "transaction_status",
                    "transaction_commit",
                    "transaction_rollback",
                ],
                "research": ["mcp_config_get", "mcp_contracts_list", "mcp_contracts_validate", "mcp_evolution_suggest_tools"],
            },
            "tools": [meta["name"] for meta in list_tool_metadata() if capabilities.tool_enabled(meta["name"])],
            "config": capabilities.current_config(),
        })

    @mcp.tool(name="mcp_health")
    def mcp_health() -> dict:
        """Report editor, scene, asset database, and queue readiness."""

        def _health():
            from Infernux.engine.deferred_task import DeferredTaskRunner
            from Infernux.engine.play_mode import PlayModeManager
            from Infernux.engine.scene_manager import SceneFileManager
            from Infernux.lib import SceneManager

            try:
                from Infernux.ai_runtime import mark_health_check

                mark_health_check()
            except Exception:
                pass

            scene = SceneManager.instance().get_active_scene()
            sfm = SceneFileManager.instance()
            pmm = PlayModeManager.instance()
            runner = DeferredTaskRunner.instance()
            adb = get_asset_database()
            return {
                "server_running": server.is_running(),
                "endpoint": server.endpoint_url(),
                "main_thread_queue_ready": MainThreadCommandQueue.instance().wait_until_ready(0.01),
                "active_scene": {
                    "available": scene is not None,
                    "name": getattr(scene, "name", ""),
                    "path": getattr(sfm, "current_scene_path", "") if sfm else "",
                    "dirty": bool(getattr(sfm, "is_dirty", False)) if sfm else False,
                    "loading": bool(getattr(sfm, "is_loading", False)) if sfm else False,
                },
                "play_state": getattr(getattr(pmm, "state", None), "name", "edit").lower() if pmm else "edit",
                "deferred_task_busy": bool(getattr(runner, "is_busy", False)),
                "asset_database_ready": adb is not None,
                "project_root": project_path,
            }

        return main_thread("mcp_health", _health)

    @mcp.tool(name="agent_bootstrap")
    def agent_bootstrap(agent_name: str = "", task_intent: str = "") -> dict:
        """Return the operating manual for a new external agent."""
        return ok(_agent_bootstrap_payload(project_path, agent_name=agent_name, task_intent=task_intent))

    @mcp.tool(name="runtime_explain_current_scene")
    def runtime_explain_current_scene(include_objects: bool = True, limit: int = 12) -> dict:
        """Explain the active scene in compact agent-operating terms."""

        def _explain():
            status = scene_status()
            object_summary = _current_scene_object_summary(limit=int(limit or 12)) if include_objects else {
                "available": False,
                "object_count": 0,
                "objects": [],
            }
            return {
                "status": status,
                "object_summary": object_summary,
                "recommended_next_tools": _scene_recommendations(status, object_summary),
                "operating_loop": _operating_loop(),
                "safety_notes": [
                    "Observe before mutating: take a snapshot or query exact targets first.",
                    "Do editor-scene mutations in Edit Mode; use runtime control tools in Play Mode.",
                    "After any run or script change, call runtime_read_errors.",
                    "Scene object IDs are session-local; reacquire IDs after scene reload.",
                ],
                "recipes": _agent_recipe_index(),
            }

        return main_thread(
            "runtime_explain_current_scene",
            _explain,
            arguments={"include_objects": include_objects, "limit": limit},
        )

    @mcp.tool(name="mcp_list_tools_verbose")
    def mcp_list_tools_verbose() -> dict:
        """Return registered tool metadata."""
        return ok({"tools": _visible_metadata()})

    @mcp.tool(name="mcp_help")
    def mcp_help(tool_name: str = "") -> dict:
        """Return detailed help for one tool or all tool groups."""
        if tool_name:
            return ok({"tool": get_tool_metadata(tool_name)})
        return ok({"tools": _visible_metadata(), "workflows": list(WORKFLOWS), "concepts": list(CONCEPTS)})

    @mcp.tool(name="mcp_catalog_list")
    def mcp_catalog_list() -> dict:
        """Return the hierarchical MCP tool catalog."""
        return ok({
            "catalog": _catalog_tree(),
            "categories": _catalog_categories(),
            "recommend": "Use mcp_catalog_search(query) or mcp_catalog_recommend(intent) before choosing tools.",
        })

    @mcp.tool(name="mcp_catalog_get")
    def mcp_catalog_get(category: str = "") -> dict:
        """Return tools under a category such as camera/framing or scene/query."""
        needle = str(category or "").strip().lower()
        tools = []
        for meta in _visible_metadata():
            meta_category = str(meta.get("category", ""))
            lower = meta_category.lower()
            if not needle or lower == needle or lower.startswith(needle + "/"):
                tools.append(meta)
        return ok({"category": category, "tools": tools, "count": len(tools), "categories": _catalog_categories()})

    @mcp.tool(name="mcp_catalog_search")
    def mcp_catalog_search(query: str, category: str = "", limit: int = 20) -> dict:
        """Search tools by name, category, summary, tags, aliases, and concepts."""
        matches = _search_catalog(str(query or ""), category=str(category or ""), limit=int(limit or 20))
        return ok({"query": query, "category": category, "matches": matches})

    @mcp.tool(name="mcp_catalog_recommend")
    def mcp_catalog_recommend(intent: str, limit: int = 12) -> dict:
        """Recommend a tool chain for a natural-language intent."""
        lowered = str(intent or "").lower()
        recommendations = []
        for key, item in INTENT_RECOMMENDATIONS.items():
            score = sum(1 for token in item.get("match", []) if str(token).lower() in lowered)
            if score:
                recommendations.append({
                    "intent": key,
                    "score": score,
                    "summary": item["summary"],
                    "tools": [get_tool_metadata(tool) for tool in item["tools"] if capabilities.tool_enabled(tool)],
                })
        recommendations.sort(key=lambda item: item["score"], reverse=True)
        if not recommendations:
            recommendations.append({
                "intent": "catalog_search",
                "score": 0,
                "summary": "No intent template matched; use search results as candidates.",
                "tools": _search_catalog(str(intent or ""), limit=int(limit or 12)),
            })
        return ok({"intent": intent, "recommendations": recommendations[: max(int(limit or 12), 1)]})

    if capabilities.feature_enabled("batch_execution"):
        @mcp.tool(name="mcp_batch")
        def mcp_batch(steps: list[dict[str, Any]], continue_on_error: bool = False) -> dict:
            """Execute a list of MCP tool calls and return an operation trace.

            Each step is {"tool": "...", "arguments": {...}, "label": "..."}.
            This intentionally goes through the MCP transport so the batch path
            observes the same envelope and main-thread behavior as external agents.
            """
            max_steps = int(capabilities.limit("batch_max_steps", 100) or 100)
            trace = []
            client = _NestedMCPClient(server.endpoint_url())
            for index, step in enumerate((steps or [])[:max_steps]):
                tool_name = str(step.get("tool", ""))
                arguments = step.get("arguments", {}) or {}
                label = str(step.get("label", "")) or tool_name
                try:
                    result = client.call(tool_name, arguments)
                    ok_flag = bool(result.get("ok", True)) if isinstance(result, dict) else True
                    trace.append({
                        "index": index,
                        "label": label,
                        "tool": tool_name,
                        "ok": ok_flag,
                        "result": result,
                    })
                    if not ok_flag and not continue_on_error:
                        break
                except Exception as exc:
                    trace.append({
                        "index": index,
                        "label": label,
                        "tool": tool_name,
                        "ok": False,
                        "error": {"code": "error.batch_step", "message": str(exc)},
                    })
                    if not continue_on_error:
                        break
            truncated = len(steps or []) > max_steps
            return ok({"ok": all(item.get("ok") for item in trace), "trace": trace, "truncated": truncated}, trace=trace)

    @mcp.tool(name="engine_concepts")
    def engine_concepts() -> dict:
        """List Infernux concepts exposed to agents."""
        return ok({"concepts": [{"name": key, "summary": value["summary"]} for key, value in sorted(CONCEPTS.items())]})

    @mcp.tool(name="engine_concept_get")
    def engine_concept_get(name: str) -> dict:
        """Return a single concept page."""
        key = _lookup_key(CONCEPTS, name)
        if not key:
            return ok({"found": False, "available": sorted(CONCEPTS)})
        return ok({"name": key, **CONCEPTS[key]})

    @mcp.tool(name="workflow_list")
    def workflow_list() -> dict:
        """List documented workflows."""
        return ok({"workflows": [{"name": key, "summary": value["summary"]} for key, value in sorted(WORKFLOWS.items())]})

    @mcp.tool(name="workflow_help")
    def workflow_help(name: str) -> dict:
        """Return detailed workflow guidance."""
        key = _lookup_key(WORKFLOWS, name)
        if not key:
            return ok({"found": False, "available": sorted(WORKFLOWS)})
        return ok({"name": key, **WORKFLOWS[key]})

    @mcp.tool(name="workflow_examples")
    def workflow_examples(name: str = "") -> dict:
        """Return compact workflow examples."""
        if name:
            key = _lookup_key(WORKFLOWS, name)
            if not key:
                return ok({"found": False, "available": sorted(WORKFLOWS)})
            return ok({"examples": [{key: WORKFLOWS[key]}]})
        return ok({"examples": WORKFLOWS})

def _lookup_key(mapping: dict[str, Any], name: str) -> str:
    lowered = str(name).strip().lower()
    for key in mapping:
        if key.lower() == lowered:
            return key
    return ""


def _agent_bootstrap_payload(project_path: str, *, agent_name: str = "", task_intent: str = "") -> dict[str, Any]:
    return {
        "identity": {
            "project": "Infernux AI-Native Engine Layer",
            "agent_name": str(agent_name or ""),
            "task_intent": str(task_intent or ""),
            "engine_role": "agent-operable runtime operating system",
            "one_sentence": "Infernux is not the agent; it is the observable, controllable, verifiable world runtime used by external agents.",
        },
        "core_boundary": {
            "engine_is_not_agent": True,
            "core_may_do": ["query", "observation", "control", "events", "evaluation", "bounded editing", "lifecycle"],
            "core_must_not_do": ["agent policy", "game strategy", "player/enemy semantics", "task planning"],
            "semantics_location": "Adapters or external agents translate domain intent into generic runtime operations.",
        },
        "startup_sequence": [
            {"tool": "agent_bootstrap", "why": "Read this operating manual first."},
            {"tool": "mcp_health", "why": "Confirm editor, queue, scene, and asset database readiness."},
            {"tool": "runtime_experiment_begin", "why": "Start a guarded session before Play Mode runtime control; use mode='run' before runtime_run_for."},
            {"tool": "runtime_experiment_mark_health_check", "why": "Record the successful health check for the active guard."},
            {"tool": "runtime_explain_current_scene", "why": "Get a compact current-scene brief and next-tool suggestions."},
            {"tool": "runtime_get_world_snapshot", "why": "Capture structured world state before acting."},
            {"tool": "mcp_catalog_search", "why": "Find task-specific tools instead of guessing APIs."},
            {"tool": "runtime_read_errors", "why": "Check runtime/script failures after every run or mutation."},
        ],
        "operating_loop": _operating_loop(),
        "rules": [
            {
                "id": "observe_before_mutate",
                "rule": "Before edits or control, identify exact targets through snapshot/query/schema tools.",
            },
            {
                "id": "separate_edit_and_play",
                "rule": "Use editor mutation tools in Edit Mode; use runtime control/run tools in Play Mode.",
            },
            {
                "id": "no_api_guessing",
                "rule": "Use api_search/api_get, component_describe_type, shader_guide, and workflow_help before unfamiliar APIs.",
            },
            {
                "id": "verify_after_action",
                "rule": "After action, read state, diff snapshots when relevant, assert, and read errors.",
            },
            {
                "id": "preview_before_commit",
                "rule": "Preview bounded world-edit transactions before committing them.",
            },
            {
                "id": "cleanup_control",
                "rule": "Clear control channels after experiments with runtime_clear_control.",
            },
        ],
        "mode_rules": {
            "edit_mode": [
                "Create/delete objects and set component fields here.",
                "Save the scene before editor_play if Play Mode preflight requires it.",
                "Use runtime_diff_world_snapshots to verify edit effects.",
            ],
            "play_mode": [
                "Drive runtime behavior with runtime_submit_control and runtime_run_for.",
                "Do not use editor-scene mutation tools while Play Mode is active unless a tool explicitly allows it.",
                "Stop with editor_stop before persistent scene cleanup.",
            ],
        },
        "recipes": _agent_recipe_index(),
        "docs": [
            "AGENTS.md",
            "docs/agent/README.md",
            "docs/agent/quickstart.md",
            "docs/agent/recipes/observe_scene.md",
            "docs/agent/recipes/control_runtime.md",
            "docs/agent/recipes/safe_world_edit.md",
            "docs/agent/recipes/debug_runtime_errors.md",
        ],
        "project_root": project_path,
    }


def _operating_loop() -> list[str]:
    return [
        "Observe: mcp_health, runtime_explain_current_scene, runtime_get_world_snapshot, scene_query_objects.",
        "Plan: choose the smallest recipe and exact targets; inspect schemas before field edits.",
        "Act: use guarded runtime_submit_control for Play Mode control or transaction-previewed editor tools for Edit Mode changes.",
        "Advance: runtime_run_for or editor_step when paused.",
        "Verify: read object/world state, diff snapshots, runtime_assert, runtime_read_errors.",
        "Recover: clear control, stop Play Mode, save or rollback generated changes as appropriate.",
    ]


def _agent_recipe_index() -> list[dict[str, Any]]:
    return [
        {
            "name": "observe_scene",
            "path": "docs/agent/recipes/observe_scene.md",
            "tools": ["mcp_health", "runtime_explain_current_scene", "runtime_get_world_snapshot", "scene_query_objects"],
        },
        {
            "name": "control_runtime",
            "path": "docs/agent/recipes/control_runtime.md",
            "tools": [
                "editor_play",
                "runtime_experiment_begin",
                "runtime_experiment_mark_health_check",
                "runtime_submit_control",
                "runtime_run_for",
                "runtime_clear_control",
                "runtime_experiment_end",
                "runtime_read_errors",
            ],
        },
        {
            "name": "safe_world_edit",
            "path": "docs/agent/recipes/safe_world_edit.md",
            "tools": [
                "runtime_get_world_snapshot",
                "runtime_get_component_schema",
                "runtime_edit_transaction_preview",
                "runtime_edit_transaction_commit",
                "runtime_diff_world_snapshots",
            ],
        },
        {
            "name": "debug_runtime_errors",
            "path": "docs/agent/recipes/debug_runtime_errors.md",
            "tools": ["runtime_read_errors", "console_read", "mcp_trace_current", "mcp_session_log_read"],
        },
    ]


def _current_scene_object_summary(*, limit: int = 12) -> dict[str, Any]:
    try:
        from Infernux.lib import SceneManager

        scene = SceneManager.instance().get_active_scene()
    except Exception:
        scene = None

    if scene is None:
        return {"available": False, "object_count": 0, "objects": []}

    try:
        objects = list(scene.get_all_objects() or [])
    except Exception:
        objects = []

    capped = objects[: max(int(limit or 12), 1)]
    return {
        "available": True,
        "scene_name": str(getattr(scene, "name", "")),
        "object_count": len(objects),
        "objects": [_object_summary(obj) for obj in capped],
        "truncated": len(objects) > len(capped),
    }


def _object_summary(obj) -> dict[str, Any]:
    transform = getattr(obj, "transform", None)
    position = getattr(transform, "position", None) if transform is not None else None
    return {
        "id": int(getattr(obj, "id", 0) or 0),
        "name": str(getattr(obj, "name", "")),
        "tag": str(getattr(obj, "tag", "")),
        "active": bool(getattr(obj, "active", True)),
        "position": _vec3_or_none(position),
        "components": _component_type_names(obj),
    }


def _component_type_names(obj) -> list[str]:
    names: list[str] = []
    for getter_name in ("get_components", "get_py_components"):
        getter = getattr(obj, getter_name, None)
        if not callable(getter):
            continue
        try:
            components = getter() or []
        except Exception:
            continue
        for comp in components:
            name = str(getattr(comp, "type_name", "") or type(comp).__name__)
            if name and name not in names:
                names.append(name)
    return names


def _vec3_or_none(value) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(value.x), float(value.y), float(value.z)]
    except Exception:
        return None


def _scene_recommendations(status: dict[str, Any], object_summary: dict[str, Any]) -> list[str]:
    recommendations = ["runtime_get_world_snapshot", "runtime_read_errors"]
    if status.get("loading"):
        return ["runtime_wait", "scene_status", *recommendations]
    if not status.get("scene"):
        return ["scene_open", "scene_inspect", *recommendations]
    if status.get("dirty"):
        recommendations.insert(0, "scene_save")
    play_state = str(status.get("play_state", "edit")).lower()
    if play_state in {"playing", "paused"}:
        recommendations = [
            "runtime_experiment_begin",
            "runtime_experiment_mark_health_check",
            "runtime_submit_control",
            "runtime_run_for",
            "runtime_clear_control",
            *recommendations,
        ]
    else:
        recommendations = ["scene_query_summary", "scene_query_objects", *recommendations, "editor_play"]
    if not object_summary.get("available") or not object_summary.get("object_count"):
        recommendations.insert(0, "hierarchy_create_object")
    return _dedupe(recommendations)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _visible_metadata() -> list[dict[str, Any]]:
    return [meta for meta in list_tool_metadata() if capabilities.tool_enabled(meta["name"])]


def _catalog_categories() -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for meta in _visible_metadata():
        category = str(meta.get("category", "") or "misc/other")
        parts = category.split("/")
        for idx in range(1, len(parts) + 1):
            key = "/".join(parts[:idx])
            counts[key] = counts.get(key, 0) + (1 if idx == len(parts) else 0)
    return [{"category": key, "tool_count": counts[key]} for key in sorted(counts)]


def _catalog_tree() -> dict[str, Any]:
    root: dict[str, Any] = {}
    for meta in _visible_metadata():
        category = str(meta.get("category", "") or "misc/other")
        node = root
        for part in [p for p in category.split("/") if p]:
            node = node.setdefault(part, {"tools": {}, "children": {}})["children"]
        leaf = root
        for part in [p for p in category.split("/") if p]:
            leaf = leaf[part]["children"]
        target = root
        parts = [p for p in category.split("/") if p]
        for part in parts[:-1]:
            target = target[part]["children"]
        if parts:
            target[parts[-1]].setdefault("tools", {})[meta["name"]] = {
                "summary": meta.get("summary", ""),
                "level": meta.get("level", "semantic"),
                "tags": meta.get("tags", []),
                "signature": meta.get("signature", ""),
                "parameters": meta.get("parameters", {}),
                "required_parameters": meta.get("required_parameters", []),
                "returns": meta.get("returns", {}),
            }
    return root


def _search_catalog(query: str, *, category: str = "", limit: int = 20) -> list[dict[str, Any]]:
    tokens = [token for token in str(query or "").lower().replace("/", " ").replace(".", " ").split() if token]
    category = str(category or "").lower().strip()
    scored = []
    for meta in _visible_metadata():
        meta_category = str(meta.get("category", ""))
        if category and not meta_category.lower().startswith(category):
            continue
        haystack_parts = [
            meta.get("name", ""),
            meta_category,
            meta.get("summary", ""),
            meta.get("doc", ""),
            meta.get("signature", ""),
            " ".join(str(key) for key in (meta.get("parameters", {}) or {}).keys()),
            " ".join(str(value.get("annotation", "")) for value in (meta.get("parameters", {}) or {}).values() if isinstance(value, dict)),
            " ".join(str(example.get("description", "")) for example in meta.get("examples", []) if isinstance(example, dict)),
            " ".join(str(item) for item in meta.get("tags", [])),
            " ".join(str(item) for item in meta.get("aliases", [])),
            " ".join(str(item) for item in (meta.get("concepts", {}) or {}).keys()),
        ]
        haystack = " ".join(str(part).lower() for part in haystack_parts)
        if not tokens:
            score = 1
        else:
            score = sum(3 if token in str(meta.get("name", "")).lower() else 1 for token in tokens if token in haystack)
        if score:
            scored.append((score, meta))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name", ""))))
    return [{**meta, "score": score} for score, meta in scored[: max(int(limit or 20), 1)]]


def _self_description_category(name: str) -> str:
    if name.startswith("mcp_catalog_"):
        return "foundation/catalog"
    if name.startswith("api_"):
        return "foundation/api"
    if name.startswith("shader_"):
        return "shader/guide"
    if name.startswith("audio_"):
        return "audio/guide"
    return "foundation/discovery"


def _self_description_tags(name: str) -> list[str]:
    if name.startswith("mcp_catalog_"):
        return ["catalog", "discover", "tools"]
    if name.startswith("api_"):
        return ["api", "script", "docs", "subsystem"]
    if name.startswith("shader_"):
        return ["shader", "glsl", "material", "docs"]
    if name.startswith("audio_"):
        return ["audio", "sound", "script", "docs"]
    return ["self-description", "help"]


def _register_metadata() -> None:
    for name, summary in {
        "project_info": "Return current project, active scene, play state, and selection.",
        "editor_get_state": "Return lightweight editor state.",
        "editor_play": "Enter Play Mode only after the active scene is saved, clean, and not loading.",
        "editor_stop": "Exit Play Mode; idempotent when already in edit mode.",
        "editor_step": "Step one frame only while Play Mode is paused.",
        "scene_status": "Return active scene path, dirty flag, and suggested save path.",
        "scene_inspect": "Return compact active scene summary.",
        "scene_get_hierarchy": "Return active scene hierarchy.",
        "scene_save": "Save the active scene through SceneFileManager; use this instead of asset tools for .scene files.",
        "scene_open": "Open a scene file only when not playing, not dirty, and not already loading.",
        "scene_new": "Create a new empty scene only with force=true and a reason.",
        "hierarchy_create_object": "Create a GameObject using registered HierarchyCreationService kinds.",
        "gameobject_add_component": "Attach a built-in or Python script component to a GameObject.",
        "component_describe_type": "Describe fields and metadata for a component type.",
        "asset_ensure_folder": "Ensure a project folder exists; succeeds when the folder already exists.",
        "asset_write_text": "Write a UTF-8 project file and notify AssetDatabase.",
        "console_read": "Read recent editor console entries.",
    }.items():
        register_tool_metadata(name, summary=summary)
    for name in ["scene_save", "scene_open", "scene_new", "editor_play", "editor_step"]:
        register_tool_metadata(
            name,
            summary=get_tool_metadata(name).get("summary", ""),
            recovery=[
                "Call scene_status before changing scenes or entering Play Mode.",
                "If scene.loading is true, wait and retry later.",
                "If scene.dirty is true, call scene_save before scene_open/scene_new/editor_play.",
                "Do not use asset_write_text/write_json/patch_text for .scene files.",
            ],
            next_suggested_tools=["scene_status", "runtime_wait", "mcp_health"],
            concepts={"Active Scene": "Only the currently open scene may be edited through MCP scene mutation tools."},
            side_effects=["May change editor scene state or Play Mode state."],
        )
    for name in [
        "agent_bootstrap", "runtime_explain_current_scene",
        "mcp_ping", "mcp_version", "mcp_discovery", "mcp_capabilities", "mcp_health", "mcp_help", "mcp_batch",
        "mcp_catalog_list", "mcp_catalog_get", "mcp_catalog_search", "mcp_catalog_recommend",
        "api_subsystems", "api_get", "api_search", "shader_guide", "shader_catalog", "shader_describe", "audio_guide",
        "engine_concepts", "engine_concept_get", "workflow_list", "workflow_help",
        "workflow_examples",
    ]:
        register_tool_metadata(
            name,
            summary=f"Self-description tool: {name}.",
            category=_self_description_category(name),
            tags=_self_description_tags(name),
            aliases=["tool menu", "categories", "search tools", "script api", "shader api", "audio api"] if name.startswith(("mcp_catalog_", "api_", "shader_", "audio_")) else [],
            level="foundation",
        )
    for name, summary in {
        "scene_query_objects": "Search scene objects with semantic filters.",
        "scene_query_summary": "Return grouped scene semantics for cameras, lights, renderers, UI, scripts, and subjects.",
        "scene_query_subjects": "Rank likely primary scene subjects.",
        "gameobject_describe_spatial": "Describe object transform, hierarchy path, components, and approximate bounds.",
    }.items():
        register_tool_metadata(
            name,
            summary=summary,
            category="scene/query",
            tags=["scene", "query", "gameobject", "subject", "bounds"],
            aliases=["find object", "scene semantics", "主体", "查找物体", "空间信息"],
            recovery=[
                "If data.stop_repeating is true, do not call the same query again.",
                "For fuzzy object lookup, prefer query.name_contains or query.path_contains.",
                "For exact matching, use query.name_exact or query.path_exact.",
                "If subjects is empty in a bootstrap scene, create or locate a renderable/gameplay object before camera framing.",
            ],
            next_suggested_tools=["camera_visibility_report", "gameobject_get", "component_get"],
        )


class _NestedMCPClient:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.request_id = 1
        self.session_id = ""
        self._initialize()

    def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        data = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        if "error" in data:
            raise RuntimeError(data["error"])
        result = data.get("result", {})
        if isinstance(result, dict):
            structured = result.get("structuredContent")
            if structured is not None:
                return structured
            content = result.get("content") or []
            if content and isinstance(content[0].get("text"), str):
                try:
                    return json.loads(content[0]["text"])
                except Exception:
                    return {"text": content[0]["text"]}
        return result

    def _initialize(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "infernux-nested-batch", "version": MCP_SERVER_VERSION},
            },
        }
        data, headers = self._post_raw(payload, include_headers=True)
        self.session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id") or ""
        if not self.session_id:
            raise RuntimeError(f"Nested MCP initialize did not return a session id: {data}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        data, _headers = self._post_raw(payload, include_headers=True)
        return data

    def _post_raw(self, payload: dict[str, Any], *, include_headers: bool = False):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
            parsed = self._parse_body(body)
            if include_headers:
                return parsed, dict(response.headers)
            return parsed

    def _parse_body(self, body: str) -> dict[str, Any]:
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return json.loads(body) if body.strip() else {}

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id
