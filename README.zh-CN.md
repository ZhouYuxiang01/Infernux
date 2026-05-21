# Infernux AI-Native Engine Layer

[English README](README.md) | [文档索引](docs/README.md) | [原始 Infernux README](README-INFERNUX.md)

本仓库是在开源游戏引擎 Infernux 基础上改造出的 AI-native 游戏运行时层。

这里的目标不是在引擎里实现一个 AI Agent，而是把游戏引擎改造成外部
AI Agent 可以全局观察、结构化控制、安全编辑、验证结果的运行时系统。

简单说：

```text
Infernux 不是 Agent。
Infernux 是给 Agent 操作世界的运行时操作系统。
```

当前阶段已经冻结为 **AI Runtime Core v1 baseline**。这个阶段的重点不是继续堆
demo，而是把外部 Agent 操作引擎所需的基础合约收紧：结构化观测、通用控制、
生命周期、事件、实验 guard、有限世界编辑事务、内部视觉观察和 MCP 工具面。

## 项目定位

传统游戏引擎主要面向人类开发者和玩家：

- 开发者在编辑器里创建内容。
- 玩家通过输入设备操作游戏。
- 自动化脚本通常只覆盖局部逻辑或测试流程。

这个项目面向外部 AI Agent：

- Agent 可以读取结构化世界快照。
- Agent 可以看到引擎内部 Game Render Target 画面。
- Agent 可以通过通用 `ControlSignal` 控制运行时。
- Agent 可以通过 MCP 工具进入、运行、暂停、验证 Play Mode。
- Agent 可以在受限 allowlist 内预览、提交、回滚世界编辑。
- Agent 可以读取事件、错误、diff 和实验状态。

核心边界是：

```text
External AI Agent
        |
        v
Adapter Layer
        |
        v
Infernux AI Runtime Core
        |
        v
Python facade / pybind11 bindings
        |
        v
C++ runtime source of truth
```

AI Runtime Core 必须保持无游戏语义。它可以提供 query、observation、control、
lifecycle、event、evaluation、editing，但不应该理解 player、enemy、jump、
attack、goal、strategy 这类玩法概念。这些语义属于 adapter 或外部 agent。

## 当前已实现能力

| 能力 | 当前状态 |
| --- | --- |
| Runtime Core 边界 | `Infernux.ai_runtime` 提供无语义的核心运行时接口。 |
| 实体观测 | 支持实体列表、组件查询、半径查询、实体快照和活动摘要。 |
| World Model | 支持 `WorldSnapshot`、组件 schema、allowlist 字段读取和 snapshot diff。 |
| 通用控制 | 支持 `ControlSignal`、MCP 控制提交、状态读取、清理和 `duration_ms` 自动过期。 |
| 生命周期 | 支持进入/退出 Play Mode、暂停、恢复、step、run-for。 |
| 事件和错误 | 支持 runtime event 读取、过滤、runtime error 读取。 |
| ExperimentGuard | 将实验规则变成可执行约束，限制 step/run 混用和 control path 混用。 |
| 内部视觉观察 | 支持从引擎内部 Game Render Target 做 GPU readback 并保存 PNG。 |
| 世界编辑 | 支持有限字段 allowlist、移动实体、设置组件字段、事务 preview/validate/commit/rollback。 |
| MCP Agent Cockpit | 暴露 agent onboarding、world snapshot、schema、diff、control、guard、transaction、render capture 等工具。 |
| Agent 文档 | 提供 `AGENTS.md`、quickstart 和 recipes，帮助没见过本项目的 Agent 快速上手。 |

## 和传统 Unity 式引擎的关键区别

这个项目不是要复制 Unity 编辑器能力，而是把“Agent 可操作性”作为运行时能力来设计。

几个关键不同点：

- 传统引擎主要把世界展示给人；本项目把世界同时暴露成结构化数据和可读像素。
- 传统输入通常绑定玩家动作；本项目的核心输入是无语义 `ControlSignal`。
- 传统 editor automation 多依赖脚本约定；本项目提供 MCP 工具作为外部 Agent cockpit。
- 传统世界编辑偏向人工操作；本项目要求 preview、validate、commit、rollback 和 diff。
- 传统测试往往验证代码或画面；本项目希望 Agent 可以观察、操作、运行、验证、恢复。
- 传统引擎不会关心 AI 是否混用了运行策略；本项目用 `ExperimentGuard` 约束实验过程。

因此，一个外部 Agent 可以做这样的闭环：

```text
读取 world snapshot
读取 component schema
捕获 Game Render Target
计划一个最小操作
提交 ControlSignal 或预览世界编辑事务
运行短时间
读取 diff / events / errors / pixels
判断结果是否符合目标
必要时清理控制或回滚编辑
```

## Agent 第一次连接时应该做什么

外部 Agent 连接运行中的编辑器 MCP 后，推荐顺序：

1. `agent_bootstrap`
2. `mcp_health`
3. 如果要用 `runtime_run_for`，调用 `runtime_experiment_begin(mode="run")`
4. `runtime_experiment_mark_health_check`
5. `runtime_explain_current_scene`
6. `runtime_get_world_snapshot`
7. 如需检查画面，调用 `runtime_capture_game_render_target`
8. `runtime_read_errors`

之后使用这个循环：

```text
Observe -> Plan -> Act -> Advance -> Verify -> Recover
```

更详细的 Agent 操作手册见：

- [AGENTS.md](AGENTS.md)
- [docs/agent/quickstart.md](docs/agent/quickstart.md)
- [docs/agent/recipes/](docs/agent/recipes/)

## 文档入口

| 文档 | 用途 |
| --- | --- |
| [README.md](README.md) | 当前 AI-native 项目英文主页。 |
| [README.zh-CN.md](README.zh-CN.md) | 当前 AI-native 项目中文主页。 |
| [docs/README.md](docs/README.md) | 全部文档索引和阅读路径。 |
| [API_Reference.md](API_Reference.md) | AI Runtime Core 手写 API 合约。 |
| [AGENTS.md](AGENTS.md) | 给外部 coding/AI agent 的根目录操作指南。 |
| [docs/agent/](docs/agent/README.md) | Agent quickstart 和操作 recipes。 |
| [AI_FIRST_ENGINE_v1_SPEC_PATCH.md](AI_FIRST_ENGINE_v1_SPEC_PATCH.md) | Core / Adapter / Agent 分层边界。 |
| [AI_FIRST_ENGINE_FUTURE_GOALS.md](AI_FIRST_ENGINE_FUTURE_GOALS.md) | 长期 AI-native engine 目标。 |
| [RUNTIME_EXPERIMENT_RULES.md](RUNTIME_EXPERIMENT_RULES.md) | Runtime 实验规则。 |
| [README-INFERNUX.md](README-INFERNUX.md) | 原始 Infernux 开源引擎 README。 |
| [README-zh.md](README-zh.md) | 原始 Infernux 中文 README，保留用于历史对照。 |

## 构建和验证入口

完整原引擎依赖请参考 [README-INFERNUX.md](README-INFERNUX.md)。

常用构建命令：

```powershell
cmake --preset release
cmake --build --preset release
```

运行不依赖 native/editor 的合约测试：

```powershell
.\venv\Scripts\python.exe -m pytest python\test\test_mcp_agent_onboarding_tools.py -q --noconftest
.\venv\Scripts\python.exe -m pytest python\test\test_mcp_runtime_world_model_tools.py -q --noconftest
.\venv\Scripts\python.exe -m pytest python\test\test_visual_observation.py -q --noconftest
```

运行外部 Agent 操作 demo：

```powershell
$env:PYTHONPATH="C:\Users\zyx62\Documents\GitHub\Infernux\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_world_operation_demo.py --auto-close
```

运行 Pellet Chase demo：

```powershell
$env:PYTHONPATH="C:\Users\zyx62\Documents\GitHub\Infernux\python"
& "C:\Users\zyx62\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\agent_pellet_chase_demo.py
```

这些 demo 的重点不是证明游戏内容复杂，而是证明外部 Agent 可以通过 MCP 完成：

- 观测世界；
- 预览/提交受限编辑；
- 进入 Play Mode；
- 提交通用控制；
- 运行一小段时间；
- 读取事件、错误、状态和内部渲染画面；
- 验证结果。

## 当前限制

当前阶段仍然是 AI Runtime Core v1 baseline，不是 production-grade agent-operable engine。

主要限制：

- World Model 还缺历史记录、订阅和资源图。
- 世界编辑事务仍只覆盖有限 move/set 操作，rollback 是 best-effort。
- Evaluation 还不是完整实验报告和 benchmark 框架。
- Replay 和确定性实验还处于早期。
- legacy player/action API 仍保留兼容 re-export，但新代码应使用无语义 core API。
- native/editor 集成测试依赖本机 Python 版本、`_Infernux` native 模块和 DLL 集合匹配。

## 下一阶段方向

当前阶段冻结后，下一步更适合做工程化升级，而不是继续堆更多 demo：

1. 完成 stable / experimental / legacy API 分层迁移。
2. 扩展 World Model：资源图、历史、订阅、更强 diff。
3. 将控制升级为 command system：command id、状态、结果、队列、replay。
4. 扩展 transaction：create/delete entity、add/remove component、持久 audit log。
5. 建立实验框架：scenario、objective metrics、run report、failure trace。
6. 强化 MCP Agent Cockpit：能力门控、结构化响应、读写权限模式。

## 非目标

这个项目当前不做这些事：

- 在引擎内部实现某个固定 AI Agent；
- 把游戏策略写进 Core；
- 把 player/enemy/jump/attack 这类玩法语义写进 Core；
- 替代原引擎 renderer、physics、scene、editor 系统；
- 把 demo adapter 当成长期 engine API。

## 总结

当前改造已经让 Infernux 从“可以运行 Python 脚本的游戏引擎”，推进到“外部 Agent
可以开始操作的游戏运行时系统”。

这个阶段最重要的价值是：

```text
结构化世界观测
通用控制信号
可执行实验约束
受限世界编辑事务
内部视觉观察
MCP Agent 操作面
```

后续重点应继续围绕可靠性、可验证性和可复现实验推进。
