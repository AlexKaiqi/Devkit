# 功能规格：事件驱动系统

## 背景

AI 管家需要**同时**处理多种异步活动：延时提醒、后台任务回调、定时巡检、主动通知。这些活动有一个共同特征：**不可阻塞用户对话**。

传统做法（sleep 阻塞、cron 轮询、后台进程 + 文件标记）在 AI agent 场景下存在根本缺陷：

| 方案 | 问题 |
|------|------|
| `sleep N && notify` | 阻塞 agent turn，用户无法继续对话 |
| 外部 cron 调度 | 依赖外部运行时 channel，与自定义 Bot polling 冲突（409 Conflict） |
| 后台 bash + 文件标记 | 无法携带会话上下文，agent 无法恢复到正确的用户对话 |

核心矛盾：**AI agent 的 turn-based 执行模型与异步世界天然冲突**。解决方案是引入事件总线，让 agent 只负责"发起意图"，由事件系统承载时序逻辑和上下文传递。

## 设计原则

### 事件即一等公民

所有异步行为统一建模为事件。定时器是"时钟事件"，Gateway 消息是"通信事件"，任务完成是"回调事件"。agent 不直接操作定时器或后台进程——它发布意图，订阅结果。

### 会话绑定

每个事件携带 `session_key`（如 `tg-6952177147`），标识事件关联的用户会话。事件触发时，系统通过 session_key 反查投递渠道（chat_id / WebSocket 连接），将结果送达正确的用户。

这解决了"agent 完成异步任务后找不到用户"的根本问题。

### 非阻塞发布

`publish()` 为每个 handler 创建独立的 `asyncio.Task`，发布者不等待任何 handler 完成。一个 handler 失败不影响其他 handler，也不影响事件总线本身。

## 事件模型

### Event 结构

```python
@dataclass
class Event:
    event_type: str       # 事件类型（如 "timer.fired", "gateway.agent"）
    session_key: str      # 绑定的用户会话标识
    payload: dict         # 事件数据（类型相关）
    timestamp: float      # 事件创建时间
    event_id: str         # 全局唯一 ID
```

### 已定义事件类型

| 事件类型 | 触发者 | 含义 | payload 示例 |
|----------|--------|------|-------------|
| `timer.created` | Timer API | 定时器已注册 | `{timer_id, delay_seconds}` |
| `timer.fired` | EventBus 内部 | 定时器到期 | `{timer_id, message}` |
| `gateway.agent` | Gateway WebSocket | Agent 流式输出 | `{text, done, ...}` |
| `gateway.chat` | Gateway WebSocket | 对话完成信号 | `{text}` |

### 事件生命周期

```
Agent 调用 Timer API ──POST──→ EventBus.schedule_timer()
                                  │
                                  ├── 立即返回 timer_id（agent turn 结束，不阻塞）
                                  │
                          asyncio.sleep(delay)
                                  │
                                  ▼
                        EventBus.publish(timer.fired)
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
                  handler_1()         handler_2()    ← 各自独立 Task
                        │
              session_key → chat_id 反查
                        │
                        ▼
              bot.send_message(chat_id, text)
```

## Timer API

EventBus 内建定时器调度，通过 HTTP API 暴露给 agent：

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 创建定时器 | POST | `/api/timer` | `{session_key, delay_seconds, message}` |
| 列出定时器 | GET | `/api/timers` | 返回所有活跃定时器及剩余时间 |
| 取消定时器 | DELETE | `/api/timer/{id}` | 取消未到期的定时器 |
| 健康检查 | GET | `/health` | 服务存活探针 |

端口：`:8789`（`TIMER_API_PORT` 环境变量）。

### Agent 调用示例

```bash
curl -s -X POST http://localhost:8789/api/timer \
  -H "Content-Type: application/json" \
  -d '{"session_key":"tg-6952177147","delay_seconds":600,"message":"主人，该开会了"}'
```

agent 发出这条命令后立即获得 `timer_id` 响应，turn 结束，用户可以继续对话。600 秒后系统自动向 Telegram 投递消息。

## 会话路由

```
session_key 格式: "tg-{chat_id}" | "fengling-{connection_id}" | ...
                         │
                  _chat_ids 映射表
                         │
                         ▼
              Telegram chat_id / WebSocket conn
```

会话映射在首次对话时自动建立（`_bind_session`），双向维护：
- `chat_id → session_key`：用户发消息时，用于向 Gateway 标识会话
- `session_key → chat_id`：事件触发时，用于反查投递目标

## 与 Gateway 事件的关系

Gateway WebSocket 产生的事件也通过 EventBus 分发：

```
Gateway WebSocket ──msg──→ gateway_client._publish_to_bus()
                                  │
                           转换为 Event(type="gateway.agent", ...)
                                  │
                           EventBus.publish()
                                  │
                           已注册的 handlers 各自处理
```

这使得 Gateway 通信和定时器共享同一套事件基础设施，未来扩展新的事件源（如 webhook 回调、文件监控）无需改动分发逻辑。

## 可扩展性

当前 EventBus 是进程内 asyncio 实现，适合单机单进程场景。如果未来需要：

| 需求 | 演进路径 |
|------|----------|
| 跨进程事件 | EventBus 接口不变，底层替换为 Redis Pub/Sub 或 NATS |
| 持久化定时器 | 定时器元数据写入 SQLite/Redis，进程重启后恢复 |
| 事件溯源 | publish() 前写入 append-only 事件日志（已有 JSONL 审计框架可复用） |
| 复杂调度 | 引入 APScheduler 或 Celery Beat，EventBus 作为分发层 |

设计上有意保持最小化——asyncio 原语、无第三方依赖、单文件实现——在需求明确前不过度抽象。

## 验收标准

- [x] 定时器创建后 agent turn 立即结束，不阻塞用户对话
- [x] 定时器到期后消息自动投递到正确的 Telegram chat
- [x] 定时器可列出、可取消
- [x] 审计日志记录 `timer.created` 和 `timer.fired` 事件
- [x] EventBus shutdown 时取消所有未到期定时器
- [ ] 持久化定时器（进程重启后恢复） — 未实现，当前为内存态

## 技术约束

- 定时器为内存态，进程重启后丢失（适合分钟级延时，不适合跨天任务）
- Timer API 无鉴权（仅监听 localhost，由 agent 通过 bash curl 调用）
- 单进程单 event loop，handler 不应执行 CPU 密集操作

## 相关决策

- [DECISIONS.md] "禁用 Gateway 内建 Telegram channel，延时任务改为事件驱动 Timer API"
- [PITFALLS.md] "Gateway Telegram channel 与自定义 Bot 不能同时 polling"
- [PITFALLS.md] "cron --announce 对 operator WebSocket 无效"
- [PITFALLS.md] "禁用 Gateway channel 后 cron agent turn 也无法启动"
