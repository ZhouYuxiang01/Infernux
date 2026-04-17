# AI-First Engine Core v1 技术设计文档

---

## 1. 引言

### 1.1 背景

传统游戏引擎主要面向人类开发者设计，其运行时接口（Runtime Interface）缺乏对 AI 系统的结构化支持，导致 AI 在参与运行时控制、分析与优化时存在以下问题：

* 无法稳定获取运行时状态
* 无法验证行为执行结果
* 无法形成自动闭环（Execution → Feedback → Adjustment）

本项目旨在构建一个**AI-first 的运行时接口层（Runtime Facade）**，使 AI 能够作为一等主体参与引擎运行。

---

### 1.2 目标

构建如下能力：

> **支持 AI 对运行时世界进行查询、控制、观测、评估与调整的统一接口体系**

---

### 1.3 范围

本版本（v1）包含：

* v1.1：运行时接入与观测能力
* v1.2：行为闭环（Evaluation / Adjustment）
* v1 扩展：通用实体观测与运行时规范

不包含：

* 强化学习（RL）
* 多智能体系统
* 资产生成
* 自然语言驱动系统
* 规划器（Planner）

---

## 2. 系统架构

### 2.1 分层结构

```text
C++ Runtime（Source of Truth）
    ↓
Python Engine Core（通用原语层）
    ↓
Runtime Usage Rules（运行规范层）
    ↓
AI Agent（决策层）
```

---

### 2.2 职责划分

| 层级          | 职责           |
| ----------- | ------------ |
| Runtime     | 真实状态与执行      |
| Engine Core | 提供通用操作原语     |
| Usage Rules | 约束使用路径，保证稳定性 |
| Agent       | 决策与策略        |

---

## 3. Engine Core 设计原则

### 3.1 单一职责原则

Engine Core 仅负责以下四类问题：

```text
1. 世界是什么（Query）
2. 世界如何推进（Control）
3. 世界发生了什么（Observation / Event）
4. 世界是否满足条件（Evaluation）
```

---

### 3.2 无语义原则

Engine Core 不包含：

* jump / attack / platform 等游戏语义
* 特定玩法逻辑

---

### 3.3 非侵入原则

不允许：

* 重写 ECS
* 重写 Physics
* 重写 SceneManager

仅允许：

* 包装（wrap）
* 暴露（expose）
* 轻量 hook

---

### 3.4 单一数据源原则

```text
C++ Runtime = 唯一事实源（Source of Truth）
```

Python 仅作为：

* Facade
* 调度层

---

## 4. v1.1：运行时接入能力

---

### 4.1 WorldState（只读投影）

#### 定义

WorldState 是当前运行时世界的只读投影。

#### 特性

* 非数据源
* 非 ECS
* 不参与运行逻辑

---

### 4.2 EntityRecord

包含：

* id
* name
* parent_id
* children_ids
* component_types（白名单）

---

### 4.3 Query API

支持：

```python
list_entities()
get_entity(id)
find_by_component(type)
find_in_radius(position, radius)
get_recent_events(ms)
```

---

### 4.4 Control API

支持：

```python
enter_play_mode()
pause()
resume()
step(n)
```

---

### 4.5 输入注入（Virtual Input）

支持：

```text
move(direction)
jump
attack
```

不支持：

* 低级输入（键盘/鼠标）
* SDL 事件伪造

---

### 4.6 Runtime Event System

最小事件集：

* PlayModeStart / Stop
* InputInjected
* Collision / Trigger
* Jump / Attack（可选）

---

### 4.7 Observation（v1.1）

#### PlayerSnapshot

* position
* velocity
* grounded

---

#### ActivitySummary

* event_count
* jump / attack（若存在）

---

## 5. v1.2：行为闭环能力

---

### 5.1 Evaluation

#### API

```python
evaluate(metrics: dict) -> EvaluationResult
```

---

#### EvaluationResult

```python
success: bool
score: float
failures: list[str]
metrics: dict
```

---

#### 约束

* metrics 为纯数据条件
* 不包含游戏语义
* 不依赖具体玩法

---

### 5.2 Adjustment

允许：

* 修改输入参数
* 修改输入强度
* 修改执行次数

禁止：

* 修改世界状态

---

### 5.3 World Editing（最小集）

```python
move_entity(id, position)
set_component(id, key, value)
```

限制：

* 白名单字段
* 不破坏系统稳定性

---

### 5.4 Event Masking

```python
set_event_filter(...)
```

特性：

* 在 C++ 层执行过滤
* 降低跨语言开销

---

### 5.5 Search（可选）

支持：

* hill climbing
* random search

---

## 6. v1 扩展：实体级运行时观测（新增）

---

### 6.1 目标

提供对任意实体的统一观测能力：

```text
Entity-level Runtime Observability
```

---

### 6.2 API

```python
get_entity_snapshot(entity_id)
get_entity_snapshot_by_name(name)
get_entity_activity_summary(entity_id, ms)
```

---

### 6.3 EntitySnapshot

包含：

* entity_id
* name
* position
* velocity
* component_types

---

### 6.4 EntityActivitySummary

包含：

* event_count
* collision_count
* moved

---

### 6.5 设计原则

* 不依赖 Player
* 不包含语义
* 面向任意实体

---

### 6.6 意义

将系统从：

```text
Player-centric
```

扩展为：

```text
Entity-centric
```

---

## 7. Runtime 使用规范（关键设计）

---

### 7.1 设计目的

避免 AI 在不确定系统中进行指数级试错。

---

### 7.2 控制路径规范

仅允许：

* Input → Controller → Transform
  或
* Rigidbody.velocity（单路径）

禁止混用。

---

### 7.3 观测路径规范

必须使用：

```text
Entity Observation API
```

禁止：

* scene object 持久引用

---

### 7.4 Play Mode 生命周期

规则：

```text
进入 Play Mode 后必须重新获取所有实体
```

---

### 7.5 运行模式

仅允许：

* 实时运行
  或
* step 驱动

禁止混用。

---

### 7.6 健康检查

必须验证：

1. Play Mode 成功
2. snapshot 可读
3. 输入有效
4. 状态更新

---

### 7.7 作用

将系统从：

```text
Non-deterministic environment
```

转为：

```text
Predictable runtime system
```

---

## 8. 完整运行闭环

```python
enter_play_mode()

entity = get_entity_snapshot_by_name(...)

for i in range(N):
    act()
    step()

    snapshot = get_entity_snapshot(...)
    result = evaluate(...)

    if result.success:
        break

    adjust_input(result)
```

---

## 9. 成功标准

AI 必须能够：

```text
1. 执行操作
2. 读取运行状态
3. 评估结果
4. 自动修正行为
```

---

## 10. 非目标

本版本不支持：

* 游戏语义 API
* 多 agent
* RL / 训练系统
* Planner
* 内容生成

---

## 11. 结论

### v1.1

```text
AI 能进入 runtime
```

### v1.2

```text
AI 能形成行为闭环
```

### v1（最终）

```text
AI 能在可预测系统中稳定决策
```

---

## 12. 核心设计结论

```text
Engine Core 提供通用能力
Usage Rules 保证稳定路径
AI 基于此进行决策
```

---

## 13. 总结

本系统的本质不是：

```text
AI 编程工具
```

而是：

> **AI 参与运行时世界的执行环境（AI-Operable Runtime System）**
