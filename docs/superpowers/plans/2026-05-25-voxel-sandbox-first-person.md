# Voxel Sandbox First-Person Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the voxel sandbox demo from a high third-person view to a Minecraft-like first-person view with visible mine/place arm animation feedback.

**Architecture:** Keep the existing `VoxelSandboxController` and MCP runner. Add first-person camera state, pitch-aware center-ray selection, a small right-hand/arm primitive rendered near the camera, and controller fields that let agents verify camera mode and animation state. The runner continues to drive the demo through generic `ControlSignal` and validates both structured state and engine-internal render-target capture.

**Tech Stack:** Infernux Python scripting, primitive cube rendering, MCP runtime tools, pytest native-free static/contract tests, CPython 3.14 editor/native verification.

---

### Task 1: Contract Tests

**Files:**
- Modify: `python/test/test_voxel_sandbox_demo_support.py`
- Modify: `python/test/test_voxel_sandbox_controller_static.py`

- [ ] **Step 1: Add failing support-route test**

Assert that `CONTROL_ROUTE` uses both `look_x` and `look_y` so first-person view pitch/yaw are exercised.

- [ ] **Step 2: Add failing controller static test**

Assert that `VoxelSandboxController.py` contains first-person fields and methods: `camera_mode`, `camera_pitch`, `arm_action`, `VoxelSandbox_Arm`, `_look_direction`, `_animate_arm`, `_trigger_arm_action`, and `_ray_cells`.

- [ ] **Step 3: Run RED tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_voxel_sandbox_demo_support.py python\test\test_voxel_sandbox_controller_static.py -q --noconftest
```

Expected: failures because the route and controller still represent the prior third-person version.

### Task 2: Controller First-Person Mode

**Files:**
- Modify: `scripts/voxel_sandbox_demo_support.py`
- Modify: `TestProject/Assets/Scripts/VoxelSandboxController.py`

- [ ] **Step 1: Update route**

Add `look_y` to the route and tune timing so the scripted agent centers the selected block from first person.

- [ ] **Step 2: Add first-person state**

Expose `camera_mode="first_person"`, `camera_pitch`, and `arm_action` as serialized agent-readable fields.

- [ ] **Step 3: Update camera**

Place the camera at player eye height, rotate/look-at from yaw/pitch, and remove third-person chase offset.

- [ ] **Step 4: Update selection**

Replace horizontal-only selection with a center-ray sampler based on yaw/pitch. Keep the ray grid-based and bounded to `selection_range`.

- [ ] **Step 5: Add arm animation**

Create `VoxelSandbox_Arm` as a primitive cube. Keep it near the camera's lower-right view area. On `mine`, animate a down/forward swing; on `place`, animate a short forward push. Update `arm_action` for structured verification.

- [ ] **Step 6: Run GREEN tests**

Run the RED test command again and expect pass.

### Task 3: Runner And Docs

**Files:**
- Modify: `scripts/agent_voxel_sandbox_demo.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Validate first-person state**

Update the runner to require `camera_mode == "first_person"` and a non-empty action history/state showing mine/place arm feedback occurred.

- [ ] **Step 2: Update docs**

Describe the demo as first-person and mention arm feedback in English and Chinese README sections.

### Task 4: Verification

**Files:**
- No direct code changes.

- [ ] **Step 1: Native-free tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_voxel_sandbox_demo_support.py python\test\test_voxel_sandbox_controller_static.py python\test\test_visual_observation.py python\test\test_mcp_runtime_world_model_tools.py -q --noconftest
```

Expected: all tests pass.

- [ ] **Step 2: Compile**

Run:

```powershell
.\venv\Scripts\python.exe -m py_compile scripts\voxel_sandbox_demo_support.py scripts\agent_voxel_sandbox_demo.py TestProject\Assets\Scripts\VoxelSandboxController.py
```

Expected: exit code 0.

- [ ] **Step 3: Real editor demo**

Run:

```powershell
$env:PYTHONPATH="C:\Users\zyx62\Documents\GitHub\Infernux\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_voxel_sandbox_demo.py --auto-close
```

Expected: validation passes and writes `TestProject/Logs/agent_observations/voxel_sandbox_render_target.png`.

- [ ] **Step 4: Whitespace and git state**

Run `git diff --check`, restore runtime-only editor noise, commit, and push `codex/voxel-sandbox-demo`.
