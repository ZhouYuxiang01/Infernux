# AI-First Engine Core 未来目标（v3 - AI-native 扩展版）

---

## 一、系统定位

本项目的目标不是构建传统游戏引擎，而是构建：

```text
AI-native Runtime System
```

系统从：

```text
AI 操作世界
```

演进到：

```text
AI 构造、修改、验证并优化世界与引擎系统
```

---

## 二、系统整体架构（核心）

未来系统采用三层结构：

```text
Model / Planner Layer
        ↓
Agent / Task Layer
        ↓
Engine Core（当前已完成）
```

---

## 三、Engine Core（当前阶段）

### 🎯 职责

提供**通用、无语义的操作与观察原语**

包括：

* WorldState / QueryAPI
* ControlAPI
* Input Injection（通用输入通道）
* RuntimeEventCollector
* ObservationAPI（实体级）

v1.2 已新增：

* Evaluation（评估原语）
* Adjustment（输入级调整）
* World Editing（实例级修改）
* Event Masking（事件过滤）

---

### ⚠️ 核心原则

```text
Engine Core 不理解任何游戏语义
```

例如：

* 不知道什么是 player
* 不知道什么是 ground
* 不知道什么是 jump / attack

---

### 🔧 语义去除（未来重构方向）

当前 v1 为了验证闭环，Engine Core 中仍存在少量 **convenience adapters**。

未来版本必须完成以下重构：

---

#### 1️⃣ 移除动作语义

移除：

* move / jump / attack 等 ActionType
* send_action 中的具体动作分支

替换为：

```text
通用输入通道（Generic Control Signal）
```

---

#### 2️⃣ 移除 player-centric 观测

移除：

* PlayerSnapshot
* get_player_snapshot()
* ActivitySummary 中的 jumped / attacked
* Player tag 依赖逻辑

替换为：

```text
Entity-centric Observation（统一实体观测）
```

---

#### 3️⃣ 分层原则

```text
Engine Core        → 无语义原语
Adapter / Example  → 游戏语义封装
```

---

### 📌 目标

```text
Engine Core 可用于任意游戏或仿真环境
```

---

## 四、Agent / Task Layer（未来核心）

### 🎯 职责

```text
理解任务 → 决策行为 → 驱动 Engine Core → 形成闭环
```

---

### 核心能力

#### 1️⃣ 资源语义理解

识别：

* 哪个对象是地面
* 哪个对象是角色
* 哪个对象是平台 / 障碍

---

#### 2️⃣ 任务理解

例如：

```text
搭建可玩的场景
```

拆解为：

```text
选择资源 → 放置 → 验证 → 修正
```

---

#### 3️⃣ 行为决策

* 选择 action
* 调用 world editing
* 控制执行流程

---

#### 4️⃣ 自我修正

```text
失败 → evaluate → adjust / edit → 再尝试
```

---

## 五、Engine Core 扩展方向

---

### 1️⃣ World Editing（核心）

#### Instance-level（已支持）

```python
move_entity(id, position)
set_component(id, key, value)
duplicate_entity(id)
```

---

#### Structural Editing（中期）

```python
create_from_prefab(...)
remove_entity(...)
```

---

### 原则

* 可控
* 可回滚
* 支持 preview

---

### 2️⃣ Event Channel（增强）

支持：

* 多 agent 过滤
* task scope
* 分通道观测

---

### 3️⃣ Sub-step Observation（长期）

支持：

```text
frame / substep
```

用于精细物理分析。

---

### 4️⃣ Multi-Agent

支持：

* 多输入通道
* 多观测流
* 多评估

---

## 六、Engine Subsystem AI Integration（新增核心）

---

### 🎯 目标

```text
让引擎底层系统成为 AI 可观测、可配置、可评估的对象
```

---

### ⚠️ 原则

```text
AI 不直接参与底层求解
AI 负责配置与监督
```

---

## 六点一、Rendering（渲染系统）

---

### 接口设计

```text
RenderSnapshot
- camera
- lighting
- exposure
- post_processing
- frame_time
- draw_calls
```

```python
get_render_snapshot()
set_render_param(key, value)
get_render_metrics()
```

---

### AI 能力

AI 可以：

* 调整画质参数
* 优化性能（FPS / draw call）
* 自动选择渲染配置
* 验证视觉结果

---

## 六点二、Physics（物理系统）

---

### 接口设计

```text
PhysicsSnapshot
- gravity
- timestep
- solver_iterations
- active_bodies
- collision_count
```

```python
get_physics_snapshot()
set_physics_param(key, value)
get_physics_metrics()
```

---

### AI 能力

AI 可以：

* 调整 damping / friction / restitution
* 优化稳定性（减少抖动）
* 分析碰撞行为
* 自动调优参数

---

## 六点三、参与层级（限制）

---

### Level A：配置层（允许）

```text
AI 修改参数
```

---

### Level B：监督层（允许）

```text
AI 观察结果并评估
```

---

### ❌ 不在当前范围

```text
AI 参与物理或渲染求解
```

---

### 📌 本质提升

```text
Game-level AI → Engine-level AI
```

---

## 七、Asset Editing（资源层）

---

### Phase A（优先）

```python
set_material_param(...)
set_prefab_param(...)
```

---

### Phase B

结构修改。

---

### Phase C

生成式内容。

---

## 八、安全编辑机制

必须支持：

* 白名单
* Patch / Diff
* Undo
* Preview
* Validation

---

## 九、核心闭环

```text
编辑 → 运行 → 评估 → 再编辑
```

---

## 十、Search / Optimization

属于 Agent 层：

* hill climbing
* search
* tuning

---

## 十一、能力演进

```text
v1.x：AI 操作世界
v2.x：AI 修改世界
v3.x：AI 修改资源
v4.x：AI 构建完整内容
```

---

## 十二、最终愿景

```text
AI-native Content Creation System
```

---

## 十三、总结

```text
Engine Core 提供能力
Agent 决策行为
AI 优化系统
```

---

> 🔥 核心突破：
>
> 传统引擎：人类操作系统
> 本系统：AI 可操作整个运行时与引擎系统
