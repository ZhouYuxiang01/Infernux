# Infernux Documentation Index

This index separates the current AI-native project documentation from the
original Infernux engine documentation, generated scripting reference pages,
and agent-facing operation guides.

The current project phase is frozen as the AI Runtime Core v1 baseline. New
documentation should describe that baseline clearly before proposing future
extensions.

## Current AI-Native Project

| Document | Audience | Purpose |
| --- | --- | --- |
| [README.md](../README.md) | Humans, reviewers, agents | English project overview for the AI-native engine layer. |
| [README.zh-CN.md](../README.zh-CN.md) | Chinese readers | Chinese project overview for the AI-native engine layer. |
| [API_Reference.md](../API_Reference.md) | Runtime/API implementers, agent builders | Hand-written AI Runtime Core API contract. |
| [AI_FIRST_ENGINE_v1_SPEC_PATCH.md](../AI_FIRST_ENGINE_v1_SPEC_PATCH.md) | Architecture reviewers | Core / adapter / agent boundary and v1 design rules. |
| [AI_FIRST_ENGINE_FUTURE_GOALS.md](../AI_FIRST_ENGINE_FUTURE_GOALS.md) | Roadmap readers | Long-term AI-native runtime direction. |
| [RUNTIME_EXPERIMENT_RULES.md](../RUNTIME_EXPERIMENT_RULES.md) | Runtime experiment authors | Rules for controlled Play Mode experiments. |

## Agent Operation

| Document | Audience | Purpose |
| --- | --- | --- |
| [AGENTS.md](../AGENTS.md) | Coding agents, external AI agents | First-contact operating guide at repository root. |
| [docs/agent/README.md](agent/README.md) | External agents | Agent docs entry point and recipe list. |
| [docs/agent/quickstart.md](agent/quickstart.md) | External agents | MCP startup sequence, loop, and mode rules. |
| [docs/agent/recipes/observe_scene.md](agent/recipes/observe_scene.md) | External agents | Read scene/world/render state before acting. |
| [docs/agent/recipes/control_runtime.md](agent/recipes/control_runtime.md) | External agents | Drive Play Mode through guarded generic control. |
| [docs/agent/recipes/safe_world_edit.md](agent/recipes/safe_world_edit.md) | External agents | Preview, commit, and verify bounded world edits. |
| [docs/agent/recipes/debug_runtime_errors.md](agent/recipes/debug_runtime_errors.md) | External agents | Recover from runtime, script, scene, and MCP errors. |

## Original Engine And Generated Docs

| Document | Audience | Purpose |
| --- | --- | --- |
| [README-INFERNUX.md](../README-INFERNUX.md) | Engine users | Original open-source Infernux README. |
| [README-zh.md](../README-zh.md) | Engine users | Original Chinese Infernux README retained for history. |
| [docs/wiki/](wiki/) | Engine users | MkDocs source for engine scripting/API documentation. |
| [docs/wiki/docs/en/api/](wiki/docs/en/api/) | Engine users | Generated English scripting API pages. |
| [docs/wiki/docs/zh/api/](wiki/docs/zh/api/) | Engine users | Generated Chinese scripting API pages. |

Generated API pages under `docs/wiki/docs/*/api/` should not be hand-edited
unless the generation pipeline is updated at the same time.

## Recommended Reading Paths

For a first human review:

1. [README.md](../README.md)
2. [API_Reference.md](../API_Reference.md)
3. [AI_FIRST_ENGINE_v1_SPEC_PATCH.md](../AI_FIRST_ENGINE_v1_SPEC_PATCH.md)
4. [docs/agent/quickstart.md](agent/quickstart.md)

For a new external agent:

1. [AGENTS.md](../AGENTS.md)
2. `agent_bootstrap`
3. `mcp_health`
4. [docs/agent/quickstart.md](agent/quickstart.md)
5. The smallest matching recipe under [docs/agent/recipes/](agent/recipes/)

For demo validation:

1. `scripts/agent_world_operation_demo.py` for world-model/edit/control smoke
   validation.
2. `scripts/agent_pellet_chase_demo.py` for top-down movement, collection,
   collision, visual capture, and runtime guard validation.
3. `scripts/agent_side_scroller_demo.py` for 2D platformer movement, jumping,
   enemy contact, finish-state validation, visual capture, and runtime guard
   validation.

For runtime API work:

1. [API_Reference.md](../API_Reference.md)
2. [AI_FIRST_ENGINE_v1_SPEC_PATCH.md](../AI_FIRST_ENGINE_v1_SPEC_PATCH.md)
3. Relevant tests under `python/test/`
4. MCP wrappers under `python/Infernux/mcp/tools/`

For original engine usage:

1. [README-INFERNUX.md](../README-INFERNUX.md)
2. [docs/wiki/](wiki/)
3. Generated API pages under `docs/wiki/docs/*/api/`

## Documentation Ownership

- Project overview belongs in `README.md` and `README.zh-CN.md`.
- Public AI Runtime contracts belong in `API_Reference.md`.
- Agent operating rules belong in `AGENTS.md` and `docs/agent/`.
- Long-form architecture rationale belongs in `AI_FIRST_ENGINE_*` documents.
- Original engine documentation should remain separate from AI-native project
  documentation.
- Runtime-generated logs, local MCP config, and cache directories should not be
  added as documentation artifacts.
