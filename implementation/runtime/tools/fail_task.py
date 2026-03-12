"""fail_task tool — mark a task as failed."""

import json

from tools import tool


@tool(
    name="fail_task",
    description="标记任务为失败，记录错误原因。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "失败的任务 ID"},
            "error_summary": {"type": "string", "description": "错误描述"},
        },
        "required": ["task_id", "error_summary"],
    },
    requires=["orchestrator"],
)
async def handle(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    task = await orchestrator.fail_task(
        task_id=args["task_id"],
        error_summary=args["error_summary"],
    )
    return json.dumps({
        "task_id": task.task_id,
        "state": task.state.value,
        "error_summary": task.error_summary,
    }, ensure_ascii=False)
