"""complete_task tool — mark a task as completed."""

import json

from tools import tool


@tool(
    name="complete_task",
    description="标记任务为已完成。如果所有兄弟任务都完成，父任务会自动完成（弹栈）。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "要完成的任务 ID"},
            "result_summary": {"type": "string", "description": "完成摘要"},
            "artifacts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "产出物列表（文件路径等）",
            },
        },
        "required": ["task_id"],
    },
    requires=["orchestrator"],
)
async def handle(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    task = await orchestrator.complete_task(
        task_id=args["task_id"],
        result_summary=args.get("result_summary", ""),
        artifacts=args.get("artifacts"),
    )
    return json.dumps({
        "task_id": task.task_id,
        "state": task.state.value,
        "result_summary": task.result_summary,
    }, ensure_ascii=False)
