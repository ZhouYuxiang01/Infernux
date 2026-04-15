# AI-First Engine Core v1.2 设计文档

---

## 一、版本定位

### v1.1 已完成

* 可操作 runtime（Execution）
* 可观测系统（Event / Snapshot）
* 基础闭环（Action → Result）

---

## v1.2 核心目标

```text
Execution → Evaluation → Adjustment
```

但关键变化是：

```text
Evaluation 不包含任何游戏语义
```

---

## 二、分层架构（核心修订）

```text
C++ Runtime (Source of Truth)
    ↓
Python Engine Core (通用原语层)
    ↓
Example / Game-specific Layer（示例/业务封装）
    ↓
AI Agent
```

---

## 三、引擎核心职责（Engine Core）

引擎只回答四个问题：

```text
1. 世界是什么（Query）
2. 世界怎么推进（Control）
3. 世界发生了什么（Event）
4. 世界是否满足某些条件（Evaluation）
```

---

# Phase 6：Evaluation（引擎核心）

## 🎯 目标

```text
提供通用的结果评估机制
```

---

## 核心 API

```python
evaluate(metrics: dict) -> EvaluationResult
```

---

## EvaluationResult

```python
class EvaluationResult:
    success: bool
    score: float
    failures: list[str]
    metrics: dict
```

---

## 设计原则

* metrics 是**纯数据条件**
* 不包含任何游戏语义
* 不依赖特定玩法

---

## 示例（通用）

```python
result = evaluate({
    "displacement": player_pos.x > 2.0,
    "contact_occurred": collision_count > 0,
})
```

---

## ❗ 禁止

```python
detect_jump()
expect_move()
expect_attack()
```

这些不属于引擎核心。

---

# Phase 7：Adjustment（输入级）

## 🎯 目标

```text
基于 Evaluation 结果调整输入
```

---

## 核心循环

```python
for i in range(N):
    act()
    result = evaluate(...)

    if result.success:
        break

    adjust_input(result)
```

---

## 允许操作

* 修改输入参数
* 修改输入时序
* 调整 step 数量

---

## ❗ 不允许

* 修改世界状态
* 修改组件
* 修改实体

---

## 示例（通用）

```python
if "displacement" in result.failures:
    increase_action_intensity()
```

---

# Phase 8：World Editing（最小集）

## 🎯 目标

```text
提供最小可控的世界修改能力
```

---

## API

```python
move_entity(id, position)
set_component(id, key, value)
```

---

## 限制

* set_component 必须白名单字段
* 不允许破坏 runtime
* 修改必须可控

---

## ❗ 不包含

```python
spawn_entity
remove_entity
```

---

## 示例（通用）

```python
if not result.success:
    move_entity(target_id, new_position)
```

---

# Phase 9：Event Masking（Observation 控制）

## 🎯 目标

```text
控制 AI 能看到的事件
```

---

## API

```python
set_event_filter(
    event_types: list[str] = None,
    source_entity_ids: list[int] = None,
    target_entity_ids: list[int] = None
)
```

---

## 行为

```text
get_recent_events(ms)
→ 返回过滤后的事件
```

---

## 原则

* 在 C++ 层过滤
* 减少跨语言开销
* 提升 AI 稳定性

---

# Phase 10：Search（可选）

## 🎯 目标

```text
自动寻找满足条件的输入或配置
```

---

## 方法

* hill climbing
* beam search
* random restart

---

## 不包含

* RL
* 模型训练

---

# Phase 11（预留）：Sub-step Observation

## 🎯 未来目标

```text
支持物理子步长级观测
```

---

## 扩展字段

```text
frame
substep_index
substep_time
```

---

## 当前状态

❌ 不在 v1.2 实现范围

---

# 四、示例层（非引擎核心）

⚠️ 以下内容**不属于 Engine Core**

---

## 示例：平台跳跃封装

```python
def expect_jump():
    return evaluate({
        "left_ground": detect_ground_loss(),
        "upward_velocity": velocity.y > 0,
    })
```

---

## 示例：移动检测

```python
def expect_move(distance):
    return evaluate({
        "displacement": get_delta_x() > distance
    })
```

---

## 示例：关卡修复

```python
if "displacement" in result.failures:
    move_entity(platform_id, closer_position)
```

---

## 说明

这些属于：

```text
Game-specific logic
```

不是：

```text
Engine Core contract
```

---

# 五、完整闭环（通用）

```python
set_event_filter(...)

enter_play_mode()
pause()

for i in range(5):
    submit_action(...)
    step(1)

    result = evaluate(...)

    if result.success:
        break

    adjust_input(result)
```

---

# 六、成功标准

AI 能做到：

```text
1. 执行动作
2. 使用通用 metrics 判断结果
3. 调整输入
4. （可选）修改世界
```

---

# 七、边界控制

v1.2 不做：

* 游戏语义 API（jump / attack 等）
* RL
* 多 agent
* spawn_entity
* planner

---

# 八、总结

```text
v1.1：AI 能操作世界
v1.2：AI 能基于通用条件判断并修正行为
```

---

# 九、关键设计结论

```text
Evaluation 是通用原语
Game logic 是上层封装
```

---
