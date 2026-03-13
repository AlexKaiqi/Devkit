"""create_task tool — create a new task (root or subtask)."""

import json

from tools import tool


@tool(
    name="create_task",
    description="创建一个新任务（根任务或子任务）。当你接到一个新的复杂请求时，先创建根任务。",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "任务标题，简洁描述要做什么"},
            "intent": {"type": "string", "description": "任务意图的详细描述"},
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "风险等级（默认 low）",
            },
            "parent_task_id": {
                "type": "string",
                "description": "父任务 ID（创建子任务时提供）",
            },
        },
        "required": ["title"],
    },
    requires=["orchestrator"],
)
async def handle(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    task = await orchestrator.create_task(
        session_key=ctx.session_key,
        title=args["title"],
        intent=args.get("intent", ""),
        risk_level=args.get("risk_level", "low"),
        parent_task_id=args.get("parent_task_id"),
    )
    return json.dumps({
        "task_id": task.task_id,
        "title": task.title,
        "state": task.state.value,
        "depth": task.depth,
    }, ensure_ascii=False)
