"""get_task_status tool — query task details or session task tree."""

import json

from tools import tool


@tool(
    name="get_task_status",
    description="查询任务详情或会话的任务树。提供 task_id 查单个任务，提供 session_key 查整个会话。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务 ID"},
            "session_key": {"type": "string", "description": "会话 key"},
        },
    },
    requires=["orchestrator"],
)
async def handle(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    result = await orchestrator.get_task_status(
        task_id=args.get("task_id"),
        session_key=args.get("session_key", ctx.session_key),
    )
    return json.dumps(result, ensure_ascii=False, default=str)
