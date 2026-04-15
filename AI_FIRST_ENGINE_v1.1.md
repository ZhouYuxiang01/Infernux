# AI-First Engine Core v1.1 设计文档（仓库对齐版）

---

## 1. 项目目标

将当前引擎扩展为：

> **可查询、可控制、可观测的运行时世界系统（AI-friendly runtime facade）**

---

## 2. v1.1 核心目标（收敛版）

本阶段仅实现：

* WorldState（只读投影）
* QueryAPI（基础查询）
* ControlAPI（最小控制能力）
* RuntimeEventCollector（最小事件集合）
* Recorder（短期事件与状态缓存）
* ObservationAPI（基础摘要）

---

## 3. 重要边界（必须遵守）

### 3.1 WorldState 不是数据源

WorldState：

* ❌ 不是新的 ECS
* ❌ 不是运行时数据存储
* ❌ 不接管引擎

它只是：

> **当前 Scene / Runtime 的只读投影（Projection）**

---

### 3.2 不重构现有系统

不允许：

* 重写 ECS
* 重写 SceneManager
* 重写 Physics
* 重写 Editor

允许：

* 包装
* 暴露
* 少量 hook

---

### 3.3 Python 是 facade，不是事实源

* Python 用于 API 聚合和调用
* 真实状态必须来自 C++ runtime

---

## 4. WorldState v1.1（最小实现）

### 4.1 EntityRecord（简化）

仅包含：

* id
* name
* parent_id
* children_ids
* component_types（先只列类型）

---

### 4.2 ComponentRecord（白名单）

⚠️ 不做通用反射

只支持：

* Transform（position / rotation）
* Rigidbody（velocity）
* Collider（type / size）
* CharacterController（grounded / speed）
* Python组件（直接透传）

---

## 5. QueryAPI v1.1（限制版）

仅实现：

* list_entities()
* get_entity(id)
* find_by_component(type)
* find_in_radius(position, radius)
* get_recent_events(ms)

---

## 6. ControlAPI v1.1（收敛版）

### 支持：

* enter_play_mode()
* pause()
* resume()
* step(n)

---

### 输入注入（重点）

仅支持：

```text
jump
move(direction)
attack
```

❌ 不支持：

* 键盘按键级别
* 鼠标事件
* 文本输入

---

### 实现方式：

> 在 InputManager 增加 **VirtualInputState**

禁止：

* 伪造 SDL 事件

---

## 7. RuntimeEventCollector v1.1（最小事件集）

只收集：

### 必须事件

* PlayModeStart / Stop
* InputInjected
* Collision / Trigger
* AttackTriggered（如果已有）
* JumpTriggered（如果已有）

---

### 可选（后续）

* StateChange（需要额外实现）

---

## 8. Recorder v1.1（不做回放）

仅支持：

* 最近 N 条事件（环形缓冲）
* 最近输入记录
* Player 最近状态（position / grounded）

❌ 不支持：

* full replay
* deterministic simulation

---

## 9. ObservationAPI v1.1

提供：

### PlayerSnapshot

* position
* velocity
* grounded

---

### RecentEvents

最近 N ms 事件

---

### ActivitySummary（简单规则）

* 是否发生 jump
* 是否发生 attack
* 事件数量

---

## 10. v1.1 成功标准（严格）

必须实现：

### 查询

* 能列出所有 entity
* 能查 entity 组件类型

### 控制

* 能进入 play mode
* 能 step 模拟
* 能注入 jump / attack

### 观测

* 能看到 jump 事件
* 能看到 collision 事件
* 能获取 player snapshot

---

## 11. 明确不做

本阶段不做：

* 通用组件反射系统
* 完整事件系统
* replay系统
* DSL生成
* 自然语言
* AI自动构建

---

## 12. 总结

v1.1 的本质：

> **不是改造引擎，而是在现有引擎之上建立 AI 可操作接口层**

---
