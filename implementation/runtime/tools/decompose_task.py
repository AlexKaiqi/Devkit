"""decompose_task tool — split a task into subtasks."""

import json

from tools import tool


@tool(
    name="decompose_task",
    description="将一个任务分解为多个子任务。适用于需要多步执行的复杂任务。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "要分解的任务 ID"},
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "子任务标题"},
                        "intent": {"type": "string", "description": "子任务意图"},
                    },
                    "required": ["title"],
                },
                "description": "子任务列表",
            },
        },
        "required": ["task_id", "subtasks"],
    },
    requires=["orchestrator"],
)
async def handle(args: dict, ctx) -> str:
    orchestrator = ctx.get("orchestrator")
    children = await orchestrator.decompose_task(
        task_id=args["task_id"],
        subtasks=args["subtasks"],
    )
    return json.dumps({
        "parent_task_id": args["task_id"],
        "subtasks": [
            {"task_id": c.task_id, "title": c.title, "depth": c.depth}
            for c in children
        ],
    }, ensure_ascii=False)
