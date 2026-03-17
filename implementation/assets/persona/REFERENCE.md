# REFERENCE.md - 命令模板与数据格式

> AGENTS.md 中引用的命令模板和数据格式参考。
> 原则和工作流见 [AGENTS.md](AGENTS.md)。

---

## 延时提醒（Action Tag）

对话中直接嵌入，系统后台执行，无需等待：

```
[ACTION:remind delay="YYYY-MM-DD HH:MM" message="提醒内容"]
[ACTION:remind delay="5m" message="5分钟后提醒"]
```

delay 支持：
- 相对时间：`5m`、`2h`、`1d`、`1h30m`
- 绝对时间：`YYYY-MM-DD HH:MM`（CST）

---

## Timer API（高级用法）

通过 HTTP 创建/查询/取消定时器：

```bash
# 创建
curl -s -X POST http://localhost:8789/api/timer \
  -H 'Content-Type: application/json' \
  -d '{"delay_seconds": 300, "message": "5分钟到了"}'

# 查询
curl http://localhost:8789/api/timers

# 取消
curl -X DELETE http://localhost:8789/api/timer/{timer_id}
```

- `session_key` 可省略，自动使用最近活跃会话
- 触发后双渠道投递：Telegram + Web Push

**⚠️ 禁止使用 `sleep` 命令模拟延时任务。**

---

## 即时通知

```
[ACTION:notify message="通知内容"]
```

或直接调用脚本：
```bash
./implementation/ops/scripts/notify.sh "消息内容"
```

---

## 审计日志格式

每次 chat 自动写入 `implementation/data/voice-audit/YYYY-MM-DD.jsonl`，字段：
- `ts`：ISO 时间戳（CST）
- `event`：`chat` / `stt` / `tts` / `timer.created` / `timer.fired`
- `session`、`user`、`assistant`、`ms` 等

---

## 服务健康检查

```bash
./check.sh
./check.sh --json
```

| 服务 | 地址 |
|------|------|
| 风铃 | http://localhost:3001 |
| STT 代理 | http://localhost:8787/health |
| Timer API | http://localhost:8789/health |
| SearXNG | http://localhost:8080 |
