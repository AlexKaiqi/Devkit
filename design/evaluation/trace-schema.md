# Evidence Trace Schema

评测应尽量基于 evidence trace，而不是只基于最终一句回复。

## 最小 evidence bundle

```json
{
  "case_id": "task-continuation-001",
  "run_id": "2026-03-09T12-00-00Z-task-continuation-001",
  "channel": "fengling",
  "input": {
    "user_message": "..."
  },
  "context_summary": {
    "task_id": "task-123"
  },
  "assistant_response": {
    "spoken": "...",
    "attachments": []
  },
  "tool_trace": [],
  "task_trace": [],
  "notification_trace": [],
  "artifacts": [],
  "metadata": {
    "candidate": "local-runtime",
    "judge_rubric": "task_continuation_v1"
  }
}
```

## 字段说明

| 字段 | 作用 |
|------|------|
| `case_id` | 对应需求层验收用例 |
| `run_id` | 单次执行标识 |
| `channel` | 从哪个入口运行 |
| `input` | 评测输入 |
| `context_summary` | 执行前关键上下文摘要 |
| `assistant_response` | 最终输出的文本与附件 |
| `tool_trace` | 关键工具调用摘要 |
| `task_trace` | 任务状态流转摘要 |
| `notification_trace` | 异步回报与提醒轨迹 |
| `artifacts` | 产物清单 |
| `metadata` | candidate / judge 等元信息 |

## 设计原则

1. trace 要足够让 deterministic checks 先做判断。
2. trace 要足够让 LLM judge 看到关键证据。
3. trace 不应强绑定某个单一模型或工具供应商。
4. trace 应允许后续人工复盘与回归沉淀。
