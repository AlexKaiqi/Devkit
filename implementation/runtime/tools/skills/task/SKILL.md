---
name: task
always: false
keywords: [任务, task, 计划, 项目, 创建任务, 完成任务, 分解, subtask, 子任务, 进度, 状态, 待办, todo, 执行, 追踪]
---
# Task Skill

任务管理能力（需要 orchestrator 上下文）。

- `create_task` 创建根任务或子任务
- `decompose_task` 将任务拆解为子任务列表
- `complete_task` / `fail_task` 标记任务完成或失败
- `get_task_status` 查询任务及子任务状态
- `update_task` 更新任务属性（标题、优先级等）
- 创建复杂任务后，使用 `decompose_task` 拆解；执行完每步后更新状态
