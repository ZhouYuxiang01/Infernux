# Side Scroller Tutorial Demo Design

## Purpose

Build an original Mario-like 2D side-scroller demo to test whether the current
Infernux AI Runtime Core v1 baseline can support an external agent creating,
running, observing, and validating a simple platform game.

The demo is not a Mario clone. It uses original naming, an original level
layout, and legally reusable art. It reproduces genre mechanics that are common
to 2D platformers: moving left/right, jumping, gravity, platforms, collectibles,
simple enemies, reward blocks, hazards, a finish marker, camera follow, and
runtime validation.

## Research Inputs

- [NintendoWiki: Super Mario Bros.](https://niwanetwork.org/wiki/Super_Mario_Bros.)
  describes the classic structure: a 2D side-scrolling platform game where the
  player runs and jumps through stages toward a level-ending flagpole, with
  blocks, coins, enemies, and power-ups.
- [World 1-1](https://en.wikipedia.org/wiki/World_1-1) is useful as a level
  design study because it teaches mechanics through the level itself: first
  enemy, blocks, rewards, vertical obstacles, pits, and replayable secrets.
- [Kenney Abstract Platformer](https://kenney.nl/assets/abstract-platformer),
  [OpenGameArt Platform Tile Set](https://opengameart.org/content/platform-tile-set-free),
  and [Tiny Platformer Pack](https://screamingbrainstudios.itch.io/tiny-platformer-pack)
  are candidate legal asset sources because they publish platformer assets with
  CC0 or public-domain terms.

## Copyright And IP Boundary

The demo must avoid Nintendo-owned names, characters, sprites, exact maps,
music, sound effects, logos, UI, and level layouts.

Allowed:

- generic side-scrolling platform mechanics
- original character and enemy names
- original tile layout
- CC0/public-domain or generated placeholder art
- source/license notes for every external asset used

Not allowed:

- Mario/Luigi/Goomba/Koopa/question-block branding or exact visual likeness
- exact World 1-1 layout reproduction
- ripped Nintendo sprites, music, sound effects, or level data
- using protected names in scene/object/script names except in documentation
  discussion of inspiration

## Demo Name

Working title: `SideScrollerTutorial`

Scene path:

```text
TestProject/Assets/Scenes/SideScrollerTutorial.scene
```

Main script path:

```text
TestProject/Assets/Scripts/SideScrollerTutorialController.py
```

Demo runner:

```text
scripts/agent_side_scroller_demo.py
```

## Target Experience

The level should be short and readable, with a left-to-right tutorial flow:

1. Safe start area.
2. First collectible line.
3. First low obstacle requiring a jump.
4. First simple walking enemy.
5. Reward block that can be hit from below.
6. Small gap or hazard with recovery-safe testing geometry.
7. Slightly higher platform teaching longer jump timing.
8. Finish marker.

The player should be able to complete the level in roughly 20-40 seconds of
manual play, or in a shorter scripted validation path.

## Core Mechanics

### Player

- Reads generic `ControlSignal` axes/buttons, not game-specific commands.
- `move_x` drives horizontal acceleration or velocity.
- `jump` starts a jump only while grounded.
- Holding jump for a short window may extend jump height if practical.
- Gravity pulls the player downward.
- Player faces movement direction visually.
- Player has basic states: alive, hurt/fail, finished.

### Collision

- Ground, platforms, walls, and reward blocks are solid.
- Collectibles are trigger-like pickups.
- Enemy side contact hurts/fails the player.
- Jumping onto an enemy from above defeats it.
- Falling below the level fails or resets the player.

### Collectibles And Score

- Collectibles increment score and disappear.
- Reward block can spawn one collectible or increment score once.
- Score is exposed through runtime state so the agent can verify it.

### Enemy

- Patrols between two bounds or reverses on wall/edge.
- Can be defeated by top contact.
- Is intentionally simple; enemy AI is not the focus of this demo.

### Finish

- Finish marker completes the level when touched.
- Completion state is exposed to runtime validation.

### Camera

- Camera follows the player horizontally.
- Vertical camera movement can be fixed or lightly damped.
- Camera framing must be verifiable through internal Game Render Target capture.

## Infernux-Specific Goals

This demo should exercise the current AI-native engine features:

- `agent_bootstrap` and MCP onboarding
- scene creation/open/save through MCP
- asset refresh/resolve for sprites or generated textures
- world/object creation through existing editor MCP tools
- Play Mode entry/exit
- `runtime_experiment_begin` and `runtime_experiment_mark_health_check`
- `runtime_submit_control` using generic `ControlSignal`
- `runtime_run_for`
- `runtime_get_world_snapshot`
- `runtime_diff_world_snapshots`
- `runtime_capture_game_render_target`
- `runtime_read_errors`
- validation that uses world state, events/errors, score, position, and pixels

## Architecture

### Demo Runner

`scripts/agent_side_scroller_demo.py` acts as the external agent client. It
should:

1. Launch or connect to the editor MCP server.
2. Refresh/resolve required assets.
3. Create/open `SideScrollerTutorial.scene`.
4. Create a root object and attach `SideScrollerTutorialController`.
5. Save the scene.
6. Enter Play Mode.
7. Begin a guarded runtime experiment.
8. Submit generic controls to move, jump, collect, and reach the finish.
9. Capture the internal Game Render Target.
10. Read world/runtime state and errors.
11. Print a compact validation summary.

### Scene Controller

`SideScrollerTutorialController.py` owns the demo gameplay. It should generate
the runtime level from declarative data instead of requiring a manual tilemap
editor.

Responsibilities:

- load sprite asset references or create simple fallback sprites
- generate static tile objects
- generate collectibles
- generate enemies
- create player runtime object
- update player movement and gravity
- resolve collisions against a grid/rect map
- update enemies
- update score/completion/failure state
- update camera position
- expose debug/runtime fields for world snapshots

This keeps the demo feasible with the current engine. It also makes the demo a
good measurement of what is still missing from agent-facing authoring APIs.

### Level Data

Use a compact declarative map inside the script, for example:

```text
############################
#.............C............F
#......?....................
#....###...........###......
#............E..............
#######..########..#########
```

The actual map must be original and should not copy World 1-1.

Tile symbols should map to generic meanings:

- `#` solid terrain
- `C` collectible
- `?` reward block, visually renamed in-game
- `E` simple patrol enemy
- `F` finish marker
- `.` empty space

### Assets

Preferred asset strategy:

1. Use CC0/public-domain platformer sprites if the asset can be downloaded and
   documented cleanly.
2. If external download or import friction blocks progress, generate simple
   original PNG placeholders locally.
3. Keep source notes under:

```text
TestProject/Assets/ThirdParty/<source>/README.md
```

No Nintendo assets should be used.

## Validation Plan

The demo is successful when the agent runner can prove:

- editor/MCP health check succeeds
- scene is created or opened
- Play Mode starts
- experiment guard is active and marked healthy
- player moves right through generic `ControlSignal`
- player jumps over or onto at least one obstacle/enemy
- score increases after collecting at least one collectible
- wall/ground collision prevents falling through solid terrain
- finish state is reached, or a smaller scripted route reaches a checkpoint if
  full completion is too brittle for the first pass
- internal render-target capture produces a PNG
- `runtime_read_errors` reports no blocking runtime errors

The validation output should include:

- start/end player position
- score before/after
- defeated enemy count if implemented
- completion/failure state
- capture path
- guard status
- runtime error summary

## Non-Goals For First Pass

- full Unity-style Tilemap editor
- full animation controller/state machine workflow
- pixel-perfect Mario physics
- exact World 1-1 layout
- multiple levels
- audio
- menus
- save/load progression
- packaged build output

## Known Risks

- The current AI Runtime transaction layer does not yet support full
  create/delete entity transactions. The demo runner may need to use existing
  editor MCP object/component tools for setup and then use runtime validation
  for safety.
- 2D animation support exists in the original engine stack but is not yet a
  mature agent-facing API. First pass should use static sprites or simple
  script-driven sprite changes.
- The engine does not yet expose a full agent-first tilemap authoring API.
  Declarative runtime generation is the practical first-pass path.
- Platformer physics can become brittle if implemented with direct transform
  movement. Keep the first pass simple and deterministic enough for validation.

## Implementation Recommendation

Use the scripted declarative-level approach first.

This is the smallest design that tests the important AI-native questions:

- Can an agent assemble a game-like scene?
- Can it run and control a non-trivial platformer loop?
- Can it visually observe the rendered output?
- Can it verify collisions, score, and completion through runtime state?
- Can it recover and report errors?

After this demo works, the next engineering target should be an
agent-facing 2D authoring kit: tilemap creation, asset import settings,
animation binding, prefab instantiation, and transaction-backed create/delete
operations.
