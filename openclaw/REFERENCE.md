# REFERENCE.md - 命令模板与数据格式

> AGENTS.md 中引用的 bash 命令模板、JSON schema、日志格式。
> 原则和工作流见 [AGENTS.md](AGENTS.md)，本文件只放"怎么写"。

---

## 延时任务模板（事件驱动）

### 定时通知 → timer.sh（推荐，最简单）

```bash
bash command:"./scripts/timer.sh 秒数 '到期后要说的话'"
```

示例：
```bash
bash command:"./scripts/timer.sh 60 '主人，1分钟到了'"
bash command:"./scripts/timer.sh 300 '主人，该开会了'"
```

### 定时通知 → Timer API（高级用法）

```bash
bash command:"curl -s -X POST http://localhost:8789/api/timer \
  -H 'Content-Type: application/json' \
  -d '{\"delay_seconds\": 20, \"message\": \"Hello！20 秒到啦~\"}'"
```

- `session_key` 可省略，系统自动使用最近活跃的会话
- 事件驱动：Timer API 创建 asyncio 定时器，到期后自动投递到绑定的 Telegram 会话
- 不阻塞当前 turn，Agent 立即回复确认
- 支持查询和取消：`GET /api/timers`、`DELETE /api/timer/{id}`

**⚠️ 禁止使用 `openclaw cron add`，它在当前架构下静默失败。**

### 超时哨兵 → Timer API + notify.sh

```bash
bash command:"curl -s -X POST http://localhost:8789/api/timer \
  -H 'Content-Type: application/json' \
  -d '{\"delay_seconds\": SECONDS, \"session_key\": \"SESSION_KEY\", \"message\": \"⏰ 后台任务「NAME」预计已完成，请检查结果。\"}'"
```

### 回退方案（Timer API 不可用时）

```bash
bash background:true command:"sleep 20 && /Users/kaiqidong/Devkit/scripts/notify.sh 'Hello！20 秒到啦~'"
```

---

## 后台任务派发模板

### 步骤 1：后台派发（prompt 末尾追加完成通知）

```bash
bash pty:true workdir:<项目路径> background:true command:"cursor agent -p '<开发指令>

完成后执行: openclaw system event --text \"Done: <简要描述>\" --mode now' --trust"
```

返回 `sessionId`，记为 XXX。

### 步骤 2：注册到任务表

用 file 工具在 `.tasks/active.json` 中追加任务条目（格式见下方）。

### 步骤 3：创建超时哨兵（Timer API）

```bash
bash command:"curl -s -X POST http://localhost:8789/api/timer \
  -H 'Content-Type: application/json' \
  -d '{\"delay_seconds\": EXPECTED_SECONDS, \"session_key\": \"SESSION_KEY\", \"message\": \"⏰ 后台任务「TASK_NAME」预计已完成，请检查结果。\"}'"
```

### 步骤 4：告知用户

---

## Cursor Agent 调用模板

基础调用：

```bash
bash pty:true workdir:<项目路径> command:"cursor agent -p '<具体开发指令>' --trust"
```

指定模型：

```bash
bash pty:true workdir:<项目路径> command:"cursor agent -p '<指令>' --trust --model sonnet-4.6"
```

项目路径从 `USER.md` 的"管理的项目"表格中查找。默认大本营：`/Users/kaiqidong/Devkit`

---

## .tasks/active.json 格式

```json
[
  {
    "id": "auth-refactor",
    "type": "cursor",
    "processSessionId": "abc123",
    "guardCron": "guard-auth-refactor",
    "startedAt": "2026-03-05T14:30:00Z",
    "expectedMinutes": 10,
    "description": "重构 auth 模块",
    "project": "/Users/kaiqidong/SomeProject"
  }
]
```

空列表 `[]` 表示无活跃任务。文件不存在时视为空列表。

---

## 审计日志格式

每次 Cursor 调用记录到项目仓库内 `.audit/` 目录：

文件名: `YYYY-MM-DD_HH-MM_<简述>.md`

```markdown
# <任务简述>
- 时间：<ISO 时间>
- 触发原因：<为什么>

## 发给 Cursor 的指令
<完整 prompt>

## Cursor 输出摘要
<关键输出>

## 变更文件
<列表>

## 结果判断
<通过/不通过，后续动作>
```

---

## 三层保障唤醒对照表

| 层级 | 触发方式 | 时机 | session |
|---|---|---|---|
| L1 事件回调 | Cursor 完成 → `openclaw system event --mode now` | 即时 | 主 session |
| L2 超时哨兵 | Timer API (`POST /api/timer`) 事件驱动 | 延迟 | 绑定 session |
| L3 巡检兜底 | heartbeat 周期性检查 | 定期 | isolated |

### 完成处理流程（无论哪层触发）

1. `process action:log sessionId:XXX` — 读取完整输出
2. 验证结果是否符合预期
3. 更新 `.tasks/active.json` — 移除该任务
4. 汇报用户（通过 Timer API 或 `scripts/notify.sh` 发送 Telegram 通知）
6. 记录到 `.audit/`
