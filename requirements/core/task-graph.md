# 任务图（Task Graph）

## 概述

AI agent 在执行复杂多步任务时，需要一个持久化的任务分解与追踪系统。任务图以 DAG 结构组织任务之间的分解、依赖和续作关系，使 agent 在每轮对话中都能看到从根到当前焦点的"栈路径"，不丢失全局视角。

## 核心需求

### 1. 任务分解与栈路径

- 复杂任务可被分解为子任务 DAG
- agent 在执行时始终能看到从根到当前焦点的"栈路径"
- 当前焦点 = session 中最深的 running/queued 任务节点
- 栈路径 = 从焦点沿 SUBTASK_OF 上溯到根的节点序列

### 2. 持久化与恢复

- 任务图持久化到 Neo4j，支持进程重启后恢复执行
- `running` 状态的任务在重启后降级为 `queued`
- `waiting_external` 任务与 EventBus 定时器重新关联
- 栈路径自动重建

### 3. 自动传播（"弹栈"行为）

- 子任务全部完成时，自动向上传播完成状态
- 任何子任务失败时，父任务不自动失败，由 agent 决策

### 4. 用户观测与干预

- 用户可通过 Web UI 观测任务图全貌
- 支持暂停、取消、调整优先级、手动添加子任务
- 实时推送任务状态变更（SSE）

### 5. CLI 查询

- CLI 支持快速查询和操作任务状态
- 支持按 session、状态过滤
- 支持查看任务树结构

## 任务状态

对齐已有的 9 种状态：

| 状态 | 含义 |
|------|------|
| `needs_clarification` | 需要用户澄清意图 |
| `needs_confirmation` | 需要用户确认执行 |
| `queued` | 等待执行 |
| `running` | 执行中 |
| `waiting_external` | 等待外部事件 |
| `waiting_user` | 等待用户输入 |
| `completed` | 已完成 |
| `failed` | 已失败 |
| `cancelled` | 已取消 |

## 关系类型

| 关系 | 方向 | 含义 |
|------|------|------|
| `SUBTASK_OF` | child → parent | 分解层级，栈路径由此推导 |
| `DEPENDS_ON` | dependent → dependency | 跨分支依赖 |
| `CONTINUATION_OF` | new → old | 续作任务指向前序任务 |

## Agent 工具

Agent 通过以下 6 个工具与任务图交互：

| 工具名 | 用途 |
|--------|------|
| `create_task` | 创建任务（根或子任务） |
| `decompose_task` | 一次性将任务拆分为多个子任务 |
| `complete_task` | 标记完成，触发向上自动传播 |
| `fail_task` | 标记失败 |
| `get_task_status` | 查询任务详情或 session 任务树 |
| `update_task` | 通用更新（暂停、恢复、取消、调优先级） |

## 上下文注入

栈路径在每轮对话前动态查询并注入 Context Assembly 第 5 优先级位置（任务状态上下文，≤400 tokens），不在内存中维护。
