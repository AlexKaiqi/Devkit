"""
CLI entry point for the Task Graph system.

Usage:
    .venv/bin/python -m runtime.task_graph.cli list [--session KEY] [--state STATE]
    .venv/bin/python -m runtime.task_graph.cli tree <task_id>
    .venv/bin/python -m runtime.task_graph.cli show <task_id>
    .venv/bin/python -m runtime.task_graph.cli focus [--session KEY]
    .venv/bin/python -m runtime.task_graph.cli cancel <task_id> [--cascade]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from task_graph.graph_store import GraphStore
from task_graph.orchestrator import TaskOrchestrator
from task_graph.models import TaskState, TERMINAL_STATES
from task_graph.stack import render_stack_path


async def cmd_list(store: GraphStore, args):
    """List tasks, optionally filtered by session and state."""
    if args.session:
        tasks = await store.get_session_root_tasks(args.session)
    else:
        tasks_raw = await store.get_all_non_terminal_tasks()
        if args.state:
            tasks_raw = [t for t in tasks_raw if t.state.value == args.state]
        tasks = tasks_raw

    if not tasks:
        print("（无任务）")
        return

    for t in tasks:
        children = await store.get_children(t.task_id)
        child_info = ""
        if children:
            completed = sum(1 for c in children if c.state == TaskState.COMPLETED)
            child_info = f" ({completed}/{len(children)} 子任务完成)"
        print(f"  [{t.state.value:20s}] {t.task_id[:8]}  {t.title}{child_info}")
        if t.session_key:
            print(f"                         session: {t.session_key}")


async def cmd_tree(store: GraphStore, args):
    """Show full subtask tree."""
    tree = await store.get_subtree(args.task_id)
    if not tree:
        print(f"Task {args.task_id} not found")
        return
    _print_tree(tree, indent=0)


def _print_tree(tree: dict, indent: int):
    task = tree.get("task", {})
    prefix = "  " * indent + ("└─ " if indent > 0 else "")
    state = task.get("state", "?")
    title = task.get("title", "")
    tid = task.get("task_id", "")[:8]
    print(f"{prefix}[{state}] {tid} {title}")
    for child in tree.get("children", []):
        _print_tree(child, indent + 1)


async def cmd_show(store: GraphStore, args):
    """Show detailed task info."""
    task = await store.get_task(args.task_id)
    if not task:
        print(f"Task {args.task_id} not found")
        return
    print(json.dumps(task.model_dump(), indent=2, ensure_ascii=False, default=str))


async def cmd_focus(store: GraphStore, args):
    """Show current focus task and stack path."""
    session = args.session or ""
    if not session:
        print("请提供 --session 参数")
        return

    focus = await store.get_focus_task(session)
    if not focus:
        print(f"Session {session} 无活跃焦点任务")
        return

    stack = await store.get_stack_path(focus.task_id)
    print("任务栈:")
    print(render_stack_path(stack, focus))
    print()
    print(f"焦点: {focus.task_id[:8]} — {focus.title}")


async def cmd_cancel(store: GraphStore, args):
    """Cancel a task (optionally with cascade)."""
    orch = TaskOrchestrator(store)
    task = await orch.update_task(args.task_id, state="cancelled")
    print(f"已取消: {task.task_id[:8]} — {task.title}")


async def main():
    parser = argparse.ArgumentParser(description="Task Graph CLI")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--session", default="")
    p_list.add_argument("--state", default="")

    p_tree = sub.add_parser("tree", help="Show task tree")
    p_tree.add_argument("task_id")

    p_show = sub.add_parser("show", help="Show task details")
    p_show.add_argument("task_id")

    p_focus = sub.add_parser("focus", help="Show current focus")
    p_focus.add_argument("--session", default="")

    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("task_id")
    p_cancel.add_argument("--cascade", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    store = GraphStore()
    try:
        await store.connect()
    except Exception as e:
        print(f"无法连接 Neo4j: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        handlers = {
            "list": cmd_list,
            "tree": cmd_tree,
            "show": cmd_show,
            "focus": cmd_focus,
            "cancel": cmd_cancel,
        }
        await handlers[args.command](store, args)
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
