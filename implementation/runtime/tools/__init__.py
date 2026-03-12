"""
Tool registry with auto-discovery.

Each tool is a single .py file in this package, decorated with @tool.
The framework auto-discovers all tool files on startup via discover_tools().
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("tools")

# ── Registry ─────────────────────────────────────────

@dataclass
class ToolDef:
    name: str
    schema: dict
    handler: Callable  # async (args: dict, ctx: ToolContext) -> str
    requires: list[str] = field(default_factory=list)


class ToolContext:
    """Runtime context passed to every tool handler."""

    def __init__(self, session_key: str = "", data: dict[str, Any] | None = None):
        self.session_key = session_key
        self._data = data or {}

    def get(self, key: str) -> Any:
        value = self._data.get(key)
        if value is None:
            raise KeyError(f"Context key not found: {key}")
        return value


_REGISTRY: dict[str, ToolDef] = {}
_CONTEXT: dict[str, Any] = {}


# ── Decorator ────────────────────────────────────────

def tool(
    name: str,
    description: str,
    parameters: dict,
    requires: list[str] | None = None,
):
    """Decorator: declare and register a tool."""

    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name] = ToolDef(
            name=name,
            schema={
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            handler=fn,
            requires=requires or [],
        )
        return fn

    return decorator


# ── Public API ───────────────────────────────────────

def set_context(key: str, value: Any) -> None:
    """Inject a shared object (e.g. orchestrator) available to tools via ctx.get()."""
    _CONTEXT[key] = value


def get_schemas() -> list[dict]:
    """Return schemas for all tools whose `requires` are satisfied."""
    return [
        td.schema
        for td in _REGISTRY.values()
        if all(k in _CONTEXT for k in td.requires)
    ]


async def run_tool(name: str, arguments: dict, session_key: str = "") -> str:
    td = _REGISTRY.get(name)
    if not td:
        return f"[error] Unknown tool: {name}"

    from tools.sandbox import check_permission

    denial = check_permission(name, arguments)
    if denial:
        return denial

    ctx = ToolContext(session_key=session_key, data=_CONTEXT)
    try:
        return await td.handler(arguments, ctx)
    except Exception as e:
        return f"[error] {name}: {e}"


def discover_tools() -> None:
    """Import every .py module in this package, triggering @tool registration."""
    package = importlib.import_module(__name__)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{info.name}")
    log.info("Discovered %d tools: %s", len(_REGISTRY), list(_REGISTRY.keys()))
