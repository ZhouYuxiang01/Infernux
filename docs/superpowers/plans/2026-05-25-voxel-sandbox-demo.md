# Voxel Sandbox Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small Minecraft-like voxel sandbox demo that an external agent can create, operate, visually inspect, and validate through Infernux runtime APIs.

**Architecture:** The demo uses a native-free Python helper for the world layout and scripted control route, a runtime `InxComponent` that generates and simulates a cube-based voxel scene, and an MCP runner that creates the scene, enters Play Mode, submits `ControlSignal` input, captures the engine render target, and validates structured state. Assets are CC0/public-domain style block textures stored under `TestProject/Assets/ThirdParty`.

**Tech Stack:** Infernux Python runtime, C++ primitive cube rendering through `PrimitiveType.Cube`, Python `InxComponent`, MCP tools, Pillow for generated texture assets, pytest for helper contract tests.

---

### Task 1: Native-Free Demo Contract

**Files:**
- Create: `scripts/voxel_sandbox_demo_support.py`
- Create: `python/test/test_voxel_sandbox_demo_support.py`

- [ ] **Step 1: Write failing contract tests**

```python
from scripts.voxel_sandbox_demo_support import (
    BLOCK_TYPES,
    CONTROL_ROUTE,
    WORLD_LAYOUT,
    cell_key,
    find_spawn_cell,
    is_solid_block,
)


def test_layout_contains_spawn_and_solid_blocks():
    assert find_spawn_cell(WORLD_LAYOUT) == (2, 2, 3)
    assert any(is_solid_block(block) for layer in WORLD_LAYOUT for row in layer for block in row)


def test_block_types_cover_core_materials():
    assert {"grass", "dirt", "stone", "wood", "leaf", "water"}.issubset(BLOCK_TYPES)
    assert not is_solid_block("air")
    assert not is_solid_block("water")
    assert is_solid_block("grass")


def test_control_route_exercises_agent_actions():
    actions = {step.action for step in CONTROL_ROUTE}
    assert {"move", "turn", "mine", "place", "slot"}.issubset(actions)


def test_cell_key_is_stable():
    assert cell_key((1, 2, 3)) == "1,2,3"
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.\venv\Scripts\python.exe -m pytest python\test\test_voxel_sandbox_demo_support.py -q --noconftest`

Expected: import failure because `scripts.voxel_sandbox_demo_support` does not exist.

- [ ] **Step 3: Implement helper**

Create a small declarative world contract with `BLOCK_TYPES`, `WORLD_LAYOUT`, `ControlStep`, `CONTROL_ROUTE`, `cell_key`, `find_spawn_cell`, and `is_solid_block`. Keep it native-free so Codex/Claude-style agents can inspect it without loading `_Infernux.pyd`.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `.\venv\Scripts\python.exe -m pytest python\test\test_voxel_sandbox_demo_support.py -q --noconftest`

Expected: all tests pass.

### Task 2: CC0-Style Block Assets

**Files:**
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/README.md`
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/grass.png`
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/dirt.png`
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/stone.png`
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/wood.png`
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/leaf.png`
- Create: `TestProject/Assets/ThirdParty/VoxelSandbox/water.png`
- Create: matching `.meta` files through engine asset refresh.

- [ ] **Step 1: Generate texture assets**

Use Pillow to generate simple 32x32 pixel-art PNGs for each block material. The README must state that these are generated CC0-compatible placeholder assets and list optional external sources inspected for later replacement: Kenney Voxel Pack and OpenGameArt CC0 block texture sets.

- [ ] **Step 2: Verify files exist**

Run: `Get-ChildItem TestProject\Assets\ThirdParty\VoxelSandbox`

Expected: six PNG files plus README.

### Task 3: Runtime Controller

**Files:**
- Create: `TestProject/Assets/Scripts/VoxelSandboxController.py`

- [ ] **Step 1: Implement scene generation**

The controller creates cube primitives for all non-air blocks in `WORLD_LAYOUT`, assigns block names like `Voxel_Block_x_y_z_type`, attaches box colliders when available, and positions a player marker plus camera.

- [ ] **Step 2: Implement runtime actions**

The controller reads generic agent input through virtual input state and exposes actions: movement, yaw turn, mine selected cell, place selected block, and inventory slot switch. Public fields must include `player_cell`, `selected_cell`, `selected_block_type`, `blocks_placed`, `blocks_removed`, `inventory_slot`, and `status`.

- [ ] **Step 3: Compile script**

Run: `.\venv\Scripts\python.exe -m py_compile TestProject\Assets\Scripts\VoxelSandboxController.py`

Expected: exit code 0.

### Task 4: Agent Demo Runner

**Files:**
- Create: `scripts/agent_voxel_sandbox_demo.py`

- [ ] **Step 1: Implement MCP runner**

The runner launches the editor if MCP is not alive, creates `Assets/Scenes/VoxelSandbox.scene`, resolves block textures, attaches `VoxelSandboxController`, enters Play Mode, calls `runtime_experiment_begin`, marks health check, submits the scripted control route, captures `runtime_capture_game_render_target`, and reads controller state.

- [ ] **Step 2: Validate agent-observable success**

The runner fails if the player never moves, no block is mined, no block is placed, selected cell is empty when it should not be, capture is unavailable, or runtime errors are present.

- [ ] **Step 3: Compile runner**

Run: `.\venv\Scripts\python.exe -m py_compile scripts\agent_voxel_sandbox_demo.py scripts\voxel_sandbox_demo_support.py`

Expected: exit code 0.

### Task 5: Documentation

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Document demo purpose**

Describe the voxel sandbox as an agent-operated world editing/control demo, not a Minecraft clone.

- [ ] **Step 2: Document verification command**

Add `scripts/agent_voxel_sandbox_demo.py` to local verification sections and agent operating docs.

### Task 6: Full Verification

**Files:**
- No direct code changes.

- [ ] **Step 1: Run native-free tests**

Run: `.\venv\Scripts\python.exe -m pytest python\test\test_voxel_sandbox_demo_support.py python\test\test_visual_observation.py python\test\test_mcp_runtime_world_model_tools.py -q --noconftest`

Expected: all selected tests pass.

- [ ] **Step 2: Run native/editor demo**

Run:

```powershell
$env:PYTHONPATH="C:\Users\zyx62\Documents\GitHub\Infernux\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_voxel_sandbox_demo.py
```

Expected: validation passes and writes `TestProject/Logs/agent_observations/voxel_sandbox_render_target.png`.

- [ ] **Step 3: Check git diff**

Run: `git diff --check`

Expected: no whitespace errors.
