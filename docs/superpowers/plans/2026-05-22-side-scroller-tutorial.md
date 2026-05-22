# Side Scroller Tutorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate an original Mario-like 2D side-scroller demo that exercises Infernux AI Runtime observation, control, visual capture, and runtime verification.

**Architecture:** Use a script-generated runtime level rather than a full tilemap editor. The external demo runner creates a scene, attaches `SideScrollerTutorialController`, enters Play Mode, drives the player with generic `ControlSignal`, reads runtime state, captures the internal Game Render Target, and validates score/movement/completion/errors.

**Tech Stack:** Python Infernux components, existing editor/runtime MCP tools, `ControlSignal`, internal render-target capture, CC0 Kenney platformer assets, pytest for native-free helper tests, CPython 3.14 for native/editor demo validation.

---

### Task 1: Native-Free Demo Helper Contract

**Files:**
- Create: `scripts/side_scroller_demo_support.py`
- Create: `python/test/test_side_scroller_demo_support.py`

- [ ] **Step 1: Write the failing tests**

Create tests that prove the level contract is deterministic and route planning exposes a rightward movement route with a jump pulse:

```python
from scripts.side_scroller_demo_support import (
    CONTROL_ROUTE,
    LAYOUT,
    find_layout_cells,
    is_solid_cell,
)


def test_layout_has_required_platformer_markers():
    cells = find_layout_cells(LAYOUT)

    assert cells.player == (7, 2)
    assert cells.finish[1] > cells.player[1]
    assert len(cells.collectibles) >= 6
    assert len(cells.enemies) >= 1
    assert len(cells.reward_blocks) >= 1


def test_solid_cell_policy_treats_bounds_and_reward_blocks_as_solid():
    assert is_solid_cell(LAYOUT, 999, 999) is True
    assert is_solid_cell(LAYOUT, 9, 0) is True
    assert is_solid_cell(LAYOUT, 5, 13) is True
    assert is_solid_cell(LAYOUT, 7, 2) is False


def test_control_route_contains_movement_and_jump():
    assert any(phase.axes.get("move_x", 0.0) > 0.0 for phase in CONTROL_ROUTE)
    assert any(phase.buttons.get("jump") for phase in CONTROL_ROUTE)
    assert sum(phase.seconds for phase in CONTROL_ROUTE) > 3.0
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_side_scroller_demo_support.py -q --noconftest
```

Expected: fail because `scripts.side_scroller_demo_support` does not exist.

- [ ] **Step 3: Implement the helper module**

Add `LAYOUT`, `CONTROL_ROUTE`, `LayoutCells`, `ControlPhase`, `find_layout_cells`, and `is_solid_cell`.

- [ ] **Step 4: Run the helper tests and verify they pass**

Run the same pytest command. Expected: all tests pass.

### Task 2: Controller And Asset Setup

**Files:**
- Create: `TestProject/Assets/Scripts/SideScrollerTutorialController.py`
- Create: `TestProject/Assets/ThirdParty/Kenney/README.md`
- Add downloaded or fallback PNG assets under `TestProject/Assets/ThirdParty/Kenney/abstract-platformer/`

- [ ] **Step 1: Add CC0 asset notes**

Download Kenney Abstract Platformer from:

```text
https://kenney.nl/media/pages/assets/abstract-platformer/a8f4badcb5-1677579172/kenney_abstract-platformer.zip
```

Record the source and CC0 license in `TestProject/Assets/ThirdParty/Kenney/README.md`.

- [ ] **Step 2: Implement `SideScrollerTutorialController`**

The component should:

- spawn the declarative level at Play Mode start
- read `Input.get_axis_raw("Horizontal")` for movement
- read `InputManager.channel_virtual_input_state.jump` and `virtual_input_state.jump` for jump
- simulate gravity and simple tile collision
- collect coins
- defeat or avoid simple enemies
- hit reward blocks from below
- update camera follow
- expose `score`, `coins_remaining`, `enemies_defeated`, `status`, `player_cell`, and `finished`

- [ ] **Step 3: Compile the controller**

Run:

```powershell
.\venv\Scripts\python.exe -m py_compile TestProject\Assets\Scripts\SideScrollerTutorialController.py
```

Expected: exit code 0.

### Task 3: External Agent Demo Runner

**Files:**
- Create: `scripts/agent_side_scroller_demo.py`

- [ ] **Step 1: Implement the runner**

Follow `scripts/agent_pellet_chase_demo.py` patterns:

- launch/connect to MCP
- `asset_refresh`
- resolve Kenney asset GUIDs
- create `Assets/Scenes/SideScrollerTutorial.scene`
- create `SideScrollerTutorial_Root`
- create `SideScrollerTutorial_Controller`
- attach `SideScrollerTutorialController`
- ensure orthographic camera
- save scene
- enter Play Mode
- begin guarded run experiment
- drive `CONTROL_ROUTE` using `runtime_submit_control`
- validate runtime fields and object movement
- capture `TestProject/Logs/agent_observations/side_scroller_render_target.png`
- clear control and end experiment

- [ ] **Step 2: Compile the runner**

Run:

```powershell
.\venv\Scripts\python.exe -m py_compile scripts\agent_side_scroller_demo.py scripts\side_scroller_demo_support.py
```

Expected: exit code 0.

### Task 4: Real Engine Validation

**Files:**
- Exercise: `scripts/agent_side_scroller_demo.py`
- Generated scene: `TestProject/Assets/Scenes/SideScrollerTutorial.scene`

- [ ] **Step 1: Stop stale demo processes**

Stop existing `agent_side_scroller_demo.py`, `agent_pellet_chase_demo.py`, or `--engine-child` Python processes.

- [ ] **Step 2: Run the native/editor demo**

Run:

```powershell
$env:PYTHONPATH="C:\Users\zyx62\Documents\GitHub\Infernux\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_side_scroller_demo.py
```

Expected output includes movement, score increase, guard status, render-target capture path, and no runtime errors.

- [ ] **Step 3: Inspect the rendered PNG**

Open:

```text
TestProject/Logs/agent_observations/side_scroller_render_target.png
```

Expected: side-scroller level is visible, camera framing is correct, player/tiles/coins/finish marker render.

### Task 5: Docs And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Document the new demo**

Add `scripts/agent_side_scroller_demo.py` as the platformer demo and explain that it validates agent-operated 2D platformer creation/control/visual capture.

- [ ] **Step 2: Run final checks**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_side_scroller_demo_support.py python\test\test_visual_observation.py python\test\test_mcp_runtime_world_model_tools.py -q --noconftest
.\venv\Scripts\python.exe -m py_compile scripts\side_scroller_demo_support.py scripts\agent_side_scroller_demo.py TestProject\Assets\Scripts\SideScrollerTutorialController.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Commit and push**

Commit the implementation and push the working branch for review.
