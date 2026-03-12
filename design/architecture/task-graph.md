# 任务图架构设计

## 概述

任务图系统将任务分解与追踪从聊天历史中独立出来，以 DAG 结构持久化到 Neo4j，并通过栈路径注入为 agent 提供全局视角。

## Neo4j 图 Schema

### 节点：`:Task`

| 属性 | 类型 | 说明 |
|------|------|------|
| `task_id` | string (UUID) | 主键 |
| `session_key` | string | 所属会话 |
| `source_channel` | string | 来源渠道（fengling/telegram） |
| `title` | string | 任务标题 |
| `intent` | string | 任务意图描述 |
| `risk_level` | string | 风险等级（low/medium/high） |
| `state` | string | 任务状态（9 种） |
| `priority` | int | 优先级（1-5，1 最高） |
| `depth` | int | 在分解树中的深度（根=0） |
| `created_at` | float | 创建时间戳 |
| `updated_at` | float | 最后更新时间戳 |
| `completed_at` | float | 完成时间戳（可选） |
| `next_action` | string | 下一步行动描述（可选） |
| `artifacts` | string[] | 产出物列表（可选） |
| `result_summary` | string | 完成摘要（可选） |
| `error_summary` | string | 错误摘要（可选） |

### 关系类型

| 关系 | 方向 | 含义 |
|------|------|------|
| `SUBTASK_OF` | child → parent | 分解层级，栈路径由此推导 |
| `DEPENDS_ON` | dependent → dependency | 跨分支依赖 |
| `CONTINUATION_OF` | new → old | 续作任务指向前序任务 |

### 索引

```cypher
CREATE INDEX task_id_idx FOR (t:Task) ON (t.task_id);
CREATE INDEX task_session_idx FOR (t:Task) ON (t.session_key);
CREATE INDEX task_state_idx FOR (t:Task) ON (t.state);
```

## "栈"行为映射到图

- **当前焦点** = session 中最深的 running/queued 任务节点
- **栈路径** = 从焦点沿 SUBTASK_OF 上溯到根的节点序列
- **完成子任务** = 检查兄弟是否全完成 → 是则自动完成父任务（"弹栈"）
- **栈路径在每轮对话前动态查询注入 Context，不在内存中维护**

## 模块结构

```
implementation/runtime/task_graph/
  __init__.py
  models.py          — Pydantic 数据模型
  graph_store.py     — Neo4j async 连接与 Cypher 操作封装
  stack.py           — 栈路径计算与 Context 文本渲染
  orchestrator.py    — 高层编排逻辑
  tools.py           — 6 个新 agent 工具
  events.py          — EventBus 集成
  cli.py             — CLI 入口
```

## Context 注入格式

注入到 Context Assembly 第 5 优先级位置，≤400 tokens：

```
## 当前任务上下文

### 任务栈
[root] 整理论文目录 (running)
  └─ 筛选机器学习相关 (running) ← 当前焦点

### 当前焦点
- task_id: abc-123
- 标题: 筛选机器学习相关
- 状态: running
- 下一步: 逐个读取剩余 PDF 摘要

### 会话任务总览
- 整理论文目录: running (2/5 子任务完成)
- 设置提醒: completed
```

## API 端点

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/tasks?session_id=` | 列出 session 根任务 |
| GET | `/api/tasks/{task_id}` | 单任务详情 |
| GET | `/api/tasks/{task_id}/tree` | 子任务树（嵌套结构） |
| PUT | `/api/tasks/{task_id}` | 更新任务 |
| POST | `/api/tasks/{task_id}/subtasks` | 手动添加子任务 |
| GET | `/api/tasks/events?session_id=` | SSE 实时推送 |

## 恢复机制

agent 启动时：
1. 查询 Neo4j 中所有非终态任务
2. `running` 状态的任务降级为 `queued`
3. `waiting_external` 任务与 EventBus 定时器重新关联
4. 栈路径自动重建

## 相关文档

- [runtime-core.md](runtime-core.md) — Context Assembly 策略
- [task-graph-neo4j.md](../decisions/task-graph-neo4j.md) — Neo4j 选型决策
- [requirements/core/task-graph.md](../../requirements/core/task-graph.md) — 能力规格
