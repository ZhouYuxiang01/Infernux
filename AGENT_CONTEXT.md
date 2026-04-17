# Infernux Agent Execution Context

This file defines the **mandatory execution rules** for all AI-driven runtime experiments inside Infernux.

---

# 1. Sources of Truth

You MUST follow all of the following:

- AI_FIRST_ENGINE_v1_SPEC_PATCH.md
- RUNTIME_EXPERIMENT_RULES.md
- POSTMORTEM_MOVE_TO_TARGET.md

These define:
- architecture boundaries
- runtime interaction rules
- known failure patterns

If any step violates these rules:

> STOP immediately. Do NOT continue by guessing.

---

# 2. Core Principles

## 2.1 Single Valid Path

At any time:

- Use **ONE control path only**
- Use **ONE observation path only**
- Use **ONE execution mode only**

Forbidden:

- Mixing transform + Rigidbody
- Mixing multiple input systems
- Mixing real-time and step-driven execution

---

## 2.2 Snapshot is Ground Truth

Only trust:

- `get_entity_snapshot(...)`
- `get_entity_snapshot_by_name(...)`

Never trust:

- local variables
- cached object references
- assumed state

Success MUST be based on snapshot data.

---

## 2.3 Play Mode Rules

After entering Play Mode:

- ALL objects must be reacquired
- NEVER reuse editor-time references

Required flow:
