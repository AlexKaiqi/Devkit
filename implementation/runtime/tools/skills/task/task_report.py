"""task_report tool — format current session task progress as Chinese summary."""

from tools import tool


@tool(
    name="task_report",
    description="汇报当前会话所有任务的进度摘要。用户问'任务做完了吗''进展如何'时调用。",
    parameters={"type": "object", "properties": {}},
    requires=["orchestrator"],
)
async def task_report(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    data = await orchestrator.get_task_status(session_key=ctx.session_key)

    tasks = data.get("tasks", [])
    if not tasks:
        return "当前会话暂无进行中的任务。"

    completed = []
    running = []
    failed = []
    other = []

    def _collect(node: dict) -> None:
        state = node.get("state", "")
        title = node.get("title", node.get("task_id", "?"))
        children = node.get("children", [])

        if state == "completed":
            completed.append(title)
        elif state in ("running", "pending"):
            child_done = sum(1 for c in children if c.get("state") == "completed")
            child_total = len(children)
            detail = f"（子任务 {child_done}/{child_total} 完成）" if child_total > 0 else ""
            running.append(f"{title}{detail}")
        elif state == "failed":
            error = node.get("error", "")
            failed.append(f"{title} — {error}" if error else title)
        else:
            other.append(title)

        for child in children:
            _collect(child)

    for task in tasks:
        _collect(task)

    total = len(tasks)
    lines = [f"当前会话共 {total} 个任务："]
    if completed:
        lines.append("✅ 已完成：" + "、".join(completed))
    if running:
        lines.append("🔄 进行中：" + "、".join(running))
    if failed:
        lines.append("❌ 失败：" + "、".join(failed))
    if other:
        lines.append("⏸ 其他：" + "、".join(other))

    return "\n".join(lines)
