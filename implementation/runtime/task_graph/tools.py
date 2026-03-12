"""
Backward-compatibility shim.

Task graph tool definitions have moved to runtime/tools/*.py (one file per tool).
This module re-exports names that older code may reference.
"""

# Tools are now registered via @tool decorator in tools/ package.
# These empty stubs prevent ImportError for any leftover references.
TASK_GRAPH_TOOL_SCHEMAS: list[dict] = []
TASK_GRAPH_HANDLERS: dict = {}
