# AI-First Engine Core v1 — Unified Spec Patch (Final)

---

## 0. 本文定位

本文件统一并替代历史 v1 / v1.1 / v1.2 文档。

目标：

- 消除语义冲突
- 固化 Engine Core 边界
- 定义可执行接口语义
- 为未来扩展预留结构
- 为代码重构提供单一规范依据

---

# 1. 核心定义

## 1.1 系统定位

Engine Core = AI Runtime Operating System

Engine Core 的职责是提供**无具体玩法语义**的运行时原语，使 AI 可以在运行中的世界中进行：

- 查询
- 控制
- 观测
- 评估
- 编辑

Engine Core 不负责任务理解、玩法解释或策略决策。

---

## 1.2 核心原则

### 原语化

Engine Core 仅提供以下原语能力：

- Query
- Control
- Observation / Event
- Evaluation
- Editing

---

### 无玩法语义（Critical Rule）

Engine Core 不允许包含以下具体玩法语义：

- player / enemy
- jump / attack / move
- platform / goal

这些概念必须位于 Core 之上的语义层中表达。

---

### 单一事实源

- C++ Runtime = Source of Truth
- Python = Facade / API Layer

Python 不持有真实世界状态，只负责 API 聚合、调用与协议封装。

---

### 非侵入

Engine Core 不重写引擎核心系统，仅做包装与暴露。

不重写：

- ECS
- Physics
- Scene
- Rendering

允许：

- wrap
- expose
- light hook

---

# 2. 分层架构

C++ Runtime  
→ Engine Core  
→ Adapter Layer  
→ Agent Layer  

---

## 2.1 Engine Core

职责：

1. 世界是什么（Query）
2. 世界如何推进（Control）
3. 世界发生了什么（Observation / Event）
4. 世界是否满足条件（Evaluation）
5. 世界如何被修改（Editing）

---

## 2.2 Adapter Layer

位置：

```text
python/Infernux/ai_adapters/
```

职责：

- 将无语义原语转化为具体项目语义
- 解析实体角色
- 将语义动作翻译为 ControlSignal
- 提供项目特定的行为检测与评估封装

依赖规则：

- Adapter 可以依赖 Core
- Core 禁止依赖 Adapter

---

### Adapter 最小协议（通用必选）

```python
def resolve_semantic_entity(scene, role: str) -> int | None: ...
def translate_action(name: str, **kwargs) -> "ControlSignal": ...
```

说明：

- `role` 例如 `"player"`、`"enemy"`、`"target"`，属于 Adapter 语义，不属于 Core
- `name` 例如 `"jump"`、`"attack"`、`"dash"`，由 Adapter 翻译成无语义输入信号

---

### Adapter 扩展示例（非必选）

以下仅是某类游戏 Adapter 的扩展示例，不构成所有 Adapter 的通用协议：

```python
def detect_jump(entity_id: int) -> bool: ...
def expect_platform_reached(entity_id: int) -> bool: ...
```

---

## 2.3 Agent Layer

职责：

- 任务理解
- 行为决策
- 自我修正
- 决定何时调用 Query / Control / Evaluation / Editing / Adapter API

Agent 不直接改变 Runtime 合约，只消费 Core 与 Adapter 提供的能力。

---

# 3. Engine Core API

---

## 3.1 Query

```python
list_entities()
get_entity(id)
find_by_component(type)
find_in_radius(position, radius)
get_recent_events(ms)
```

说明：

- `list_entities()` 返回实体列表
- `get_entity(id)` 返回实体的只读投影
- `find_by_component(type)` 按组件类型查找实体
- `find_in_radius(position, radius)` 进行空间范围查询
- `get_recent_events(ms)` 返回最近时间窗口内的事件

---

## 3.2 Control

```python
enter_play_mode()
pause()
resume()
step(n)
```

说明：

- `enter_play_mode()` 进入运行态
- `pause()` 暂停 simulation
- `resume()` 恢复 simulation
- `step(n)` 推进 simulation `n` 步

---

## 3.3 ControlSignal（核心）

```python
class ControlSignal:
    channel_id: int
    axes: dict[str, float]
    buttons: dict[str, bool]
    duration_ms: int | None
    timestamp_ms: int | None = None
```

---

### Core 控制入口

```python
def submit_control(signal: ControlSignal) -> None
def clear_control(channel_id: int | None = None) -> None
```

说明：

- `submit_control(signal)` 提交一个输入信号到指定 channel
- `clear_control(channel_id)` 清空指定 channel 的输入状态
- `clear_control(None)` 清空所有 channel 的输入状态

---

### ControlSignal 执行语义（必须遵守）

#### 触发类型

默认采用：

```text
level-trigger
```

即：

- `buttons[key] = True` 表示“按住”状态，而不是“按下一帧边沿”
- `axes` 表示持续输入值，而不是瞬时脉冲

Core 不直接提供 edge-trigger。  
需要“短按一次”的语义时，由 Adapter 通过提交 + 定时清空组合实现。

---

#### 生命周期

- 若 `duration_ms != None`，则信号在持续时间到期后自动清零
- 若 `duration_ms is None`，则信号持续存在，直到：
  - 被同 channel 的新信号覆盖，或
  - 被 `clear_control()` 清空

---

#### 覆盖规则

同一 `channel_id` 上提交新 signal 时：

```text
last-write-wins
```

即：

- 新 signal 直接覆盖旧 signal
- 不做自动 merge
- 不做 axes 求和
- 不做 buttons 并集

---

#### step 行为

```text
step() 不清空 control signal
```

`step(n)` 仅推进 simulation，不隐式消耗或清除输入状态。

---

#### axes 值域

规范值域：

```text
[-1.0, 1.0]
```

运行时策略：

```text
clamp
```

即：

- 小于 `-1.0` 的值自动截断为 `-1.0`
- 大于 `1.0` 的值自动截断为 `1.0`

这样可提高 Adapter / Agent 的容错性，避免单次越界直接打断闭环。

---

#### timestamp_ms

- 若调用方提供 `timestamp_ms`，则按提供值记录
- 若未提供，则由 Runtime 在接收时自动填充

v1 中 `timestamp_ms` 主要用于记录与调试；更复杂的多 agent 冲突排序不在 v1 范围内。

---

## 3.4 Legacy API（兼容迁移）

历史语义 API：

```python
send_action("jump")
send_action("attack")
send_action("move")
```

这些 API 不再视为 Core 的长期 contract。

迁移策略：

- v1.3：保留
- v1.4：发出 `DeprecationWarning`
- v2.0：从 Core 中删除

实现原则：

- Core 不直接依赖 Adapter
- 自 v1.4 起，推荐使用 Adapter 层的语义 API
- Core 中的 `send_action` 仅保留为 deprecated 壳子，用于告警与引导迁移
- 语义动作的真实翻译逻辑应位于 Adapter 中

---

## 3.5 Observation（Entity-centric）

```python
get_entity_snapshot(entity_id)
get_entity_snapshot_by_name(name)
get_entity_activity_summary(entity_id, ms)
```

说明：

- Core 采用 entity-centric 观测，不提供 player-centric 观测
- 所有实体观测必须基于显式 entity id 或显式查询结果
- Core 不做隐式 player 推断

---

### Snapshot 字段冻结

Core 的 `get_entity_snapshot(...)` 返回的核心字段为稳定 contract，不允许被 Adapter 污染或扩写：

- `entity_id`
- `name`
- `position`
- `velocity`
- `component_types`

如需扩展如 `health`、`score`、`is_player_controlled` 等项目字段，应由 Adapter 或上层维护，不得反向写入 Core snapshot contract。

---

### 废弃（迁移中）

以下不再属于 Core 的长期 contract：

- `PlayerSnapshot`
- `get_player_snapshot()`
- `jumped / attacked`

它们属于历史 convenience API，必须迁移到 Adapter 层。

---

## 3.6 Event

```python
from typing import Union

EventValue = Union[
    int,
    float,
    bool,
    str,
    tuple[float, float, float],
]

class RuntimeEvent:
    event_type: str
    timestamp_ms: int
    source_entity_id: int | None
    target_entity_id: int | None
    agent_id: int | None
    payload: dict[str, EventValue]
```

说明：

- `payload` 中保留基础值类型，不允许全量字符串化
- `tuple[float, float, float]` 用于表达 Vec3 类数据
- 后续如需扩展更丰富类型，应在此 contract 上增量演进，而不是退回 string-only

---

### v1 中 agent_id 约定

- 单 agent 场景：`agent_id = 0`
- `agent_id = None`：表示 system-level event 或不归属于任何 agent 的事件

---

## 3.7 Evaluation

```python
evaluate(metrics: dict) -> EvaluationResult
```

要求：

- `metrics` 为纯数据条件
- 不包含玩法语义判断
- 不依赖具体游戏类型

示例：

```python
evaluate({
    "moved": displacement > 1.0,
    "collision_happened": collision_count > 0,
})
```

以下不属于 Core Evaluation：

- `expect_jump()`
- `detect_attack()`
- `is_player_win()`

这些属于 Adapter 或 Agent 层。

---

## 3.8 Adjustment

```python
adjust_input(result)
```

限制：

- 只能调整输入参数 / 输入时序 / step 次数
- 不允许直接修改世界状态

---

### Adjustment 生命周期

v1 中 session 定义为：

```text
enter_play_mode() → exit_play_mode()
```

规则：

- session 与 play mode 生命周期一致
- Adjustment 状态必须按 `agent_id` 隔离
- 必须支持 reset

推荐入口：

```python
def reset_adjustment(agent_id: int | None = None) -> None
```

说明：

- `reset_adjustment(agent_id)`：重置指定 agent 的 adjustment 状态
- `reset_adjustment(None)`：重置所有 agent 的 adjustment 状态

---

## 3.9 World Editing

```python
move_entity(id, position, preview=False)
set_component(id, key, value, preview=False)
```

说明：

- Editing 仅支持最小实例级修改
- 所有编辑必须受控
- 所有字段必须经过白名单检查
- `preview=True` 时只返回拟应用结果，不真正提交

---

### EditResult

```python
class FieldChange:
    entity_id: int
    component: str
    key: str
    old: object
    new: object

class EditResult:
    success: bool
    preview_only: bool
    diff: list[FieldChange]
```

说明：

- `diff` 必须是结构化字段变更列表，而不是无类型 `list`
- `preview_only=True` 表示本次结果仅为 dry-run

---

## 3.10 Event Masking

```python
set_event_filter(
    event_types=None,
    source_entity_ids=None,
    target_entity_ids=None,
    agent_id=None
)
```

说明：

- 过滤应在 C++ 层或尽可能靠近事实源的位置执行
- `agent_id=None` 表示不按 agent 过滤

---

# 4. C++ 输入系统重构（关键）

历史结构（语义耦合，不再作为长期方向）：

```cpp
bool jump;
bool attack;
float move_x;
```

目标结构：

```cpp
struct InputChannel {
    std::unordered_map<std::string, float> axes;
    std::unordered_map<std::string, bool> buttons;
};

std::vector<InputChannel> channels;
```

说明：

- Python `ControlSignal` 应映射到 C++ `InputChannel`
- C++ 输入层必须摆脱 platformer-specific 的具名字段绑定
- 未来如需性能优化，可在不改变对外 contract 的前提下替换底层存储形式

---

### C++ 输入迁移时间表

| 数据结构 | v1.3 | v1.4 | v2.0 |
|---|---|---|---|
| `VirtualInputState`（具名字段） | 保留（Legacy 兼容） | 保留（Legacy 兼容） | 删除 |
| `std::vector<InputChannel>` | 新增 | 推荐主路径 | 唯一路径 |

---

# 5. Legacy API 迁移时间表

| API | v1.3 | v1.4 | v2.0 |
|---|---|---|---|
| `send_action` | 保留 | `DeprecationWarning` | 删除 |
| `PlayerSnapshot` | 保留 | `DeprecationWarning` | 删除 |
| `get_player_snapshot` | 保留 | `DeprecationWarning` | 删除 |
| `submit_control` | 新增 | 推荐 | 唯一路径 |
| Entity-centric Observation | 可用 | 推荐 | 唯一路径 |

---

# 6. 非目标（v1）

以下内容不属于 v1 范围：

- Multi-agent 完整实现（仅预留字段）
- Engine Subsystem AI Integration（Render / Physics）
- Asset editing
- Structural editing
- Planner / RL
- Edge-trigger 原生输入语义
- 完整事务式 undo/redo 系统

---

# 7. 成功标准

AI 能够：

1. 操作世界
2. 读取状态
3. 评估结果
4. 调整行为
5. 在受控条件下修改世界（可选）

并满足以下边界要求：

- Core 无具体玩法语义
- 语义解释位于 Adapter 层
- 决策位于 Agent 层
- 运行时真实状态始终来自 C++ Runtime

---

# 8. 总结

Engine Core = 无语义运行时原语系统  
Adapter = 语义层  
Agent = 决策层  

本补丁的核心修复不是增加更多功能，而是重新明确边界：

- Core 不再承载玩法语义
- 语义迁移到 Adapter
- 输入协议从具名动作迁移为通用信号
- 观测从 player-centric 迁移为 entity-centric

这构成 v1 的统一 contract。