你正在操作 Infernux runtime。
必须严格遵守以下规则，否则不要继续尝试。

---

# 一、唯一允许路径

## 控制对象（只能选一种）

✔ 使用 Input API → 控制器 → transform.position
（优先）
或
✔ 使用 Rigidbody.velocity（仅一种方式，不混用）

禁止：

* 同时用 velocity + transform
* 同时用 update + fixed_update
* 混用 move_position / add_force / velocity

---

## 读取状态（唯一方式）

必须使用：

```python
get_entity_snapshot(...)
get_entity_snapshot_by_name(...)
get_entity_activity_summary(...)
```

禁止：

* 持有 scene object 引用
* 用非 observation API 读 runtime 状态

---

## Play Mode 规则（必须）

进入 Play Mode 后：

```text
所有对象必须重新获取
```

流程必须是：

```python
enter_play_mode()
wait_until_playing()
entity = get_entity_snapshot_by_name(...)
```

禁止：

* 使用编辑态获取的对象
* 跨 Play Mode 使用旧引用

---

# 二、运行模式（只能选一个）

✔ 模式 A：实时运行

```text
enter_play_mode → sleep
```

或

✔ 模式 B：step 驱动

```text
pause → step(n)
```

禁止混用。

---

# 三、健康检查（必须先执行）

在主逻辑前必须验证：

1. 能进入 Play Mode
2. 能获取 live entity snapshot
3. 注入输入后 position 会变化
4. observation 会随时间更新

任一失败：

```text
立即停止，不继续实验
```

---

# 四、实验结构（必须遵循）

```python
enter_play_mode()
wait_until_playing()

entity = get_entity_snapshot_by_name(...)

while not success:
    # 1. 设置参数 / 输入
    # 2. 运行一段时间
    # 3. 读取 snapshot
    # 4. 计算结果（distance / score）
    # 5. 判断 success
    # 6. 若失败 → 修改参数
```

---

# 五、参数调优规则

必须：

* 多轮尝试（≥3）
* 每轮输出参数 + 结果
* 根据结果修改参数

禁止：

* 写死最优参数
* 一次成功就结束
* 直接计算解析解

---

# 六、事件使用规则

* 所有事件必须带时间窗口（ms）
* 碰撞类事件必须用小窗口（50~200ms）
* 不依赖偶然捕获

---

# 七、禁止事项

禁止：

* 修改 engine core
* 使用 game-specific 语义（jump / attack / platform）
* teleport / 强行设置最终位置
* 使用未定义路径绕过规则
* 混用多种控制或观测方式

---

# 八、目标

你不是在“让代码跑通”，而是在：

```text
基于真实 runtime 结果做稳定决策与优化
```

如果你发现路径不稳定，请：

```text
停止试错 → 回到唯一允许路径
```
