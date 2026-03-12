"""
Stack path computation and Context text rendering for task graph.
"""

from __future__ import annotations

from task_graph.models import TaskNode, TaskState, SessionTaskSummary


def render_stack_path(path: list[TaskNode], focus: TaskNode | None) -> str:
    """Render stack path as indented text for Context injection."""
    if not path:
        return ""

    lines = []
    for i, node in enumerate(path):
        indent = "  " * i
        prefix = "[root] " if i == 0 else "└─ "
        state_label = node.state.value
        marker = " ← 当前焦点" if (focus and node.task_id == focus.task_id) else ""
        lines.append(f"{indent}{prefix}{node.title} ({state_label}){marker}")

    return "\n".join(lines)


def render_focus_details(focus: TaskNode | None) -> str:
    """Render current focus task details."""
    if not focus:
        return "（无活跃任务）"

    lines = [
        f"- task_id: {focus.task_id[:8]}",
        f"- 标题: {focus.title}",
        f"- 状态: {focus.state.value}",
    ]
    if focus.next_action:
        lines.append(f"- 下一步: {focus.next_action}")
    if focus.intent:
        lines.append(f"- 意图: {focus.intent}")

    return "\n".join(lines)


def render_session_summary(
    root_tasks: list[TaskNode],
    children_map: dict[str, list[TaskNode]],
) -> str:
    """Render session task overview."""
    if not root_tasks:
        return "（无任务）"

    lines = []
    for task in root_tasks:
        children = children_map.get(task.task_id, [])
        if children:
            completed = sum(1 for c in children if c.state == TaskState.COMPLETED)
            total = len(children)
            lines.append(f"- {task.title}: {task.state.value} ({completed}/{total} 子任务完成)")
        else:
            lines.append(f"- {task.title}: {task.state.value}")

    return "\n".join(lines)


def render_task_context(
    stack_path: list[TaskNode],
    focus: TaskNode | None,
    root_tasks: list[TaskNode],
    children_map: dict[str, list[TaskNode]],
) -> str:
    """Render the full task context block for Context Assembly injection."""
    sections = ["## 当前任务上下文\n"]

    # Stack path
    if stack_path:
        sections.append("### 任务栈")
        sections.append(render_stack_path(stack_path, focus))
        sections.append("")

    # Focus details
    sections.append("### 当前焦点")
    sections.append(render_focus_details(focus))
    sections.append("")

    # Session summary
    if root_tasks:
        sections.append("### 会话任务总览")
        sections.append(render_session_summary(root_tasks, children_map))

    return "\n".join(sections)
