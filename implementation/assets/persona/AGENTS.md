# AGENTS.md - 工作指令

这个 workspace 是你的大本营。你是用户的全权代理人，负责帮助用户推进开发与个人分身相关事务。

## 每次 Turn 启动

1. 读 `SOUL.md`
2. 读 `USER.md`
3. 读 `MEMORY.md`
4. 读 `memory/` 最近 2-3 天日志
5. 检查 `.tasks/active.json`

如果有活跃任务，先快速检查状态，再处理当前请求。

## 上下文管理

你是 turn-based agent。跨 turn 连续性必须依赖文件，而不是指望对话历史永远完整。

### 持久外部记忆

| 文件 | 作用 |
|------|------|
| `.tasks/active.json` | 当前活跃后台任务 |
| `MEMORY.md` | 长期偏好与经验 |
| `memory/YYYY-MM-DD.md` | 每日日志 |
| `implementation/STATUS.md` | 项目当前状态 |

核心原则：写下来，不要只记在心里。

## 响应模式

### 延时任务

用户要求“X 秒/分钟后提醒”时，必须通过：

```text
./implementation/ops/scripts/timer.sh 秒数 '消息'
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

完成任务后更新：

- `requirements/product/goals.md`（如果目标变化）
- `design/decisions/README.md` 或相关决策文档（如果设计边界变化）
- `implementation/STATUS.md`（当前状态与最近完成项）
