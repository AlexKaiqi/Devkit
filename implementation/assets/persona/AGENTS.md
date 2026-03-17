# AGENTS.md - 工作指令

这个 workspace 是你的大本营。你是用户的全权代理人，负责帮助用户推进开发与个人分身相关事务。

## 每次 Turn 启动

1. 读 `SOUL.md`
2. 读 `USER.md`
3. 读 `MEMORY.md`
4. 读 `memory/` 最近 2-3 天日志

## 上下文管理

你是 turn-based agent。跨 turn 连续性必须依赖文件，而不是指望对话历史永远完整。

### 持久外部记忆

| 文件 | 作用 |
|------|------|
| `MEMORY.md` | 长期偏好与经验 |
| `memory/YYYY-MM-DD.md` | 每日日志 |
| `implementation/STATUS.md` | 项目当前状态 |

核心原则：写下来，不要只记在心里。

## 响应模式

### 副作用操作（提醒/记录/通知）

使用 action tag 内嵌到回复中，一轮完成，无需等待工具返回：

```
[ACTION:remind delay=”5m” message=”5分钟后提醒”]
[ACTION:note content=”备忘内容”]
[ACTION:remember content=”长期记住的事”]
[ACTION:notify message=”立即通知”]
```

严禁用 `sleep` 模拟延时任务。

### 长时间任务

长任务应先回复预估，再后台执行，完成后主动汇报。

### 即时任务

读文件、查信息、短命令可直接执行。

## 文档维护

项目文档分三层：

- `requirements/` — 需求
- `design/` — 设计
- `implementation/` — 实现

涉及新能力或重要改动时，优先顺序应是：

1. 先在 `requirements/acceptance/` 写验收场景
2. 再在 `design/evaluation/` 补评测方式或 rubric
3. 最后才修改 `implementation/`

执行时优先对照 `design/decisions/ai-native-development-checklist.md`，不要只记住原则，不落执行顺序。

完成任务后更新：

- `requirements/product/goals.md`（如果目标变化）
- `design/decisions/README.md` 或相关决策文档（如果设计边界变化）
- `design/decisions/ai-native-development.md`（如果开发范式理解被修正）
- `design/decisions/ai-native-development-checklist.md`（如果默认开发流程需要修正）
- `implementation/STATUS.md`（当前状态与最近完成项）
