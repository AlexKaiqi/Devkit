# 事件系统接口

事件系统负责承载所有非阻塞推进能力，包括延时提醒、外部回调、任务续作和主动通知。

## 设计目标

- 让 runtime 只发布意图，不承担长时间等待。
- 让定时器、回调和续作共享同一套事件基础设施。
- 让事件始终携带可路由的会话标识，以便把结果送回正确入口。
- 让事件模型可以从单机进程内实现逐步演进到跨进程或持久化实现。

## 核心原则

### 事件是一等公民

所有异步行为都建模为事件。定时器是时钟事件，任务恢复是续作事件，结果投递是渠道事件。

### 会话绑定

每个事件都必须携带 `session_key`，用于把结果回投到正确的渠道会话。

### 发布非阻塞

事件发布者不等待具体 handler 完成。一个 handler 失败，不应阻塞其他 handler。

## 事件对象

```python
@dataclass
class Event:
    event_type: str
    session_key: str
    payload: dict
    timestamp: float
    event_id: str
```

## 规范事件类型

| 事件类型 | 含义 | 典型 payload |
|----------|------|-------------|
| `timer.created` | 已注册一个未来触发的提醒或任务 | `{timer_id, delay_seconds}` |
| `timer.fired` | 定时器到期 | `{timer_id, message}` |
| `task.resumed` | 半途任务重新进入执行流 | `{task_id, continuation_of, reason}` |
| `channel.deliver` | 向某个入口投递结果 | `{session_key, content, attachments}` |
| `external.callback` | 外部系统把结果带回 runtime | `{source, data}` |

## Timer API 契约

Timer API 只暴露最小必要接口：

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 创建定时器 | POST | `/api/timer` | 创建延时意图 |
| 列出定时器 | GET | `/api/timers` | 查看活跃定时器 |
| 取消定时器 | DELETE | `/api/timer/{id}` | 取消未触发定时器 |
| 健康检查 | GET | `/health` | 运行状态探针 |

## 会话路由

推荐使用统一的 `session_key` 命名约定：

- `fengling-...`
- `tg-...`
- 其他渠道按相同规则扩展

渠道层负责建立 `channel_id <-> session_key` 映射，事件系统只依赖 `session_key` 进行路由。

## 与任务续作的关系

事件系统不仅负责提醒，也负责让任务在等待之后继续推进：

1. runtime 记录任务当前状态、产物与等待原因。
2. 外部条件满足或时间到达时，事件系统产生新事件。
3. runtime 根据事件重新组装上下文，生成续作输入。
4. 任务以“新的一次推进”继续运行，而不是强依赖完整旧对话回放。

## 演进方向

| 需求 | 演进方式 |
|------|----------|
| 跨进程事件 | 保持接口不变，替换底层事件总线 |
| 持久化定时器 | 引入持久化存储保存元数据和恢复信息 |
| 事件溯源 | 发布前写入 append-only 日志 |
| 更复杂调度 | 在事件系统前接调度器层 |

## 相关设计

- [系统设计总览](../architecture/system-overview.md)
- [Runtime Core](../architecture/runtime-core.md)
- [任务生命周期与续作](../../requirements/core/task-lifecycle.md)
- [事件与通知决策](../decisions/eventing-and-notification.md)
