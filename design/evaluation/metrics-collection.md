# 指标采集方案

本文档定义北极星指标和核心体验指标的最小可采集版本：audit log 字段约定、计算方式和采集路径。

> 完整指标定义见 [requirements/product/metrics.md](../../requirements/product/metrics.md)。本文只回答"怎么采"。

## 原则

- V1 优先用已有日志文件（不引入新数据库或埋点系统）
- 计算方式以人工可验证为标准，不追求自动化 dashboard
- 指标采集粒度：每次任务（task 级）

## Audit Log Schema

所有任务事件写入 `implementation/data/audit.jsonl`，每行一条事件：

```json
{
  "ts": "2026-03-09T10:05:00Z",
  "event": "task.created | task.state_changed | tool.called | tool.result | policy.check | confirmation.requested | confirmation.granted | notification.sent | memory.written | knowledge.upserted",
  "task_id": "task-20260309-001",
  "session_key": "fengling-local-20260309",
  "channel": "fengling",
  "data": {}
}
```

各事件类型的 `data` 字段约定：

| event | data 字段 |
|-------|-----------|
| `task.created` | `{ title, source_channel, risk_level }` |
| `task.state_changed` | `{ from_state, to_state, reason }` |
| `tool.called` | `{ tool_name, risk_level, args_summary }` |
| `tool.result` | `{ tool_name, success, duration_ms, error? }` |
| `policy.check` | `{ tool_name, risk_level, decision, action_required? }` |
| `confirmation.requested` | `{ tool_name, scope_summary }` |
| `confirmation.granted` | `{ tool_name, granted_scope }` |
| `notification.sent` | `{ target_channel, task_id, delivery_success }` |
| `memory.written` | `{ subject, source_origin }` |
| `knowledge.upserted` | `{ id, type, subject, source_origin }` |

## 北极星指标计算

### 每周闭环任务数

**采集字段**：`task.state_changed` 事件，`to_state = completed`，`ts` 在目标周内

**计算**：

```
closed_tasks_this_week = count(
  event="task.state_changed",
  to_state="completed",
  ts in [week_start, week_end]
)
```

### 有效代理率

**采集字段**：任务的最终状态 + 是否存在 `waiting_user` 事件（表示需要用户手工补充核心信息）

**计算**：

```
effective = count(tasks where final_state="completed" and no waiting_user event)
total = count(tasks where final_state in [completed, failed, cancelled])
rate = effective / total
```

## 核心体验指标计算

### 首响应延迟

**采集字段**：需要在渠道层打点。从用户消息到达到首条 assistant 流式文本开始的时间差。

**V1 最小实现**：在 `task.created` 事件 data 里加 `{ input_received_at, first_response_at }`

```
p50/p95 latency = percentile(first_response_at - input_received_at, [50, 95])
```

### 异步结果回报时效

**采集字段**：`notification.sent` 事件 + `timer.fired` 事件

```
delivery_delta = notification.sent.ts - timer.fired.ts
on_time_rate = count(delivery_delta < 10s) / count(notification.sent)
```

### 多渠道连续性

**采集字段**：`notification.sent` 事件，`target_channel != source_channel`

```
cross_channel_success_rate = count(delivery_success=true) / count(cross-channel notifications)
```

## 信任与可控指标计算

### 确认覆盖率

**采集字段**：`policy.check` 事件（L2/L3）+ `confirmation.requested` 事件

```
# 每个 L2/L3 tool.called 对应是否有 confirmation.requested
coverage = count(L2/L3 tool_calls with prior confirmation.requested) / count(L2/L3 tool_calls)
```

### 误执行率

**采集字段**：需要人工标注。建议每周人工抽查 `tool.called` 日志，对"不该执行"的调用打 `misfire=true` 标签。

V1 不自动计算，人工抽查并记录。

## 记忆与知识指标计算

### 记忆复用率

**采集字段**：Context Assembly 装载记忆时，在 `task.created` 里记录 `memory_entries_loaded`；再对比该任务的最终回复是否引用了记忆内容（LLM judge 评估）。

V1 最小实现：只统计 `memory_entries_loaded > 0` 的任务占比作为代理指标。

### 知识维护负债

**采集字段**：`knowledge.upserted` 事件中 `status=unverified` 的累计条目数 + 超期 `review_after` 的条目数。

```
debt = count(knowledge entries where status="unverified")
     + count(knowledge entries where review_after < now)
```

## 采集现状与路径

| 指标 | V1 可采集？ | 所需新增 |
|------|------------|---------|
| 每周闭环任务数 | ✓（补 audit.jsonl 即可） | 无 |
| 有效代理率 | ✓ | 无 |
| 首响应延迟 | 部分 | task.created 需增加时间戳字段 |
| 异步回报时效 | ✓ | 无 |
| 多渠道连续性 | ✓ | 无 |
| 确认覆盖率 | ✓ | policy.check 事件需实现 |
| 误执行率 | 人工 | 人工抽查 |
| 记忆复用率 | 代理指标 | Context Assembly 需记录装载信息 |
| 知识维护负债 | ✓ | knowledge-gateway 实现后自然产生 |

## 相关文档

- [requirements/product/metrics.md](../../requirements/product/metrics.md)
- [eval-protocol.md](eval-protocol.md)
- [policy-check.md](../architecture/policy-check.md)
- [session-identity.md](../architecture/session-identity.md)
