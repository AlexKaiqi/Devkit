"""update_task tool — update task state or attributes."""

import json

from tools import tool


@tool(
    name="update_task",
    description="更新任务状态或属性。可用于暂停(waiting_user)、恢复(running)、取消(cancelled)、调优先级等。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务 ID"},
            "state": {
                "type": "string",
                "enum": [
                    "needs_clarification", "needs_confirmation",
                    "queued", "running", "waiting_external",
                    "waiting_user", "completed", "failed", "cancelled",
                ],
                "description": "新状态",
            },
            "priority": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "新优先级（1=最高, 5=最低）",
            },
            "next_action": {"type": "string", "description": "下一步行动描述"},
        },
        "required": ["task_id"],
    },
    requires=["orchestrator"],
)
async def handle(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    task = await orchestrator.update_task(
        task_id=args["task_id"],
        state=args.get("state"),
        priority=args.get("priority"),
        next_action=args.get("next_action"),
    )
    return json.dumps({
        "task_id": task.task_id,
        "state": task.state.value,
        "priority": task.priority,
    }, ensure_ascii=False)
