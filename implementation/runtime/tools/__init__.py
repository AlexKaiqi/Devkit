"""
Tool registry with Skill-based grouping and lazy loading.

Tools are organised into Skill packages under tools/skills/<name>/.
Each Skill has a SKILL.md with YAML frontmatter (name, always, keywords).
Agent activates Skills based on keyword matching against the user message.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("tools")

# ── Registry ─────────────────────────────────────────

@dataclass
class ToolDef:
    name: str
    schema: dict
    handler: Callable  # async (args: dict, ctx: ToolContext) -> str
    requires: list[str] = field(default_factory=list)
    skill: str = ""    # which skill this tool belongs to


@dataclass
class SkillDef:
    name: str
    path: Path
    keywords: list[str]
    always: bool
    description: str   # SKILL.md body (without frontmatter)
    tools: list[str] = field(default_factory=list)  # tool names belonging to this skill


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
_SKILLS: dict[str, SkillDef] = {}
_CONTEXT: dict[str, Any] = {}

_SKILLS_DIR = Path(__file__).parent / "skills"


# ── Decorator ────────────────────────────────────────

def tool(
    name: str,
    description: str,
    parameters: dict,
    requires: list[str] | None = None,
):
    """Decorator: declare and register a tool."""

    def decorator(fn: Callable) -> Callable:
        # Determine skill name from module path
        module = fn.__module__  # e.g. "tools.skills.system.exec"
        skill_name = ""
        parts = module.split(".")
        if "skills" in parts:
            idx = parts.index("skills")
            if idx + 1 < len(parts):
                skill_name = parts[idx + 1]

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
            skill=skill_name,
        )
        # Register tool into its skill's tool list
        if skill_name and skill_name in _SKILLS:
            if name not in _SKILLS[skill_name].tools:
                _SKILLS[skill_name].tools.append(name)
        return fn

    return decorator


# ── SKILL.md parsing ─────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_skill_md(text: str) -> dict:
    """Parse SKILL.md frontmatter + body. Returns dict with keys: name, always, keywords, description."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {"name": "", "always": False, "keywords": [], "description": text.strip()}

    fm_raw, body = m.group(1), m.group(2).strip()

    # Minimal YAML parse (no external deps)
    data: dict[str, Any] = {"name": "", "always": False, "keywords": []}
    for line in fm_raw.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "name":
            data["name"] = val
        elif key == "always":
            data["always"] = val.lower() in ("true", "yes", "1")
        elif key == "keywords":
            # Parse inline list: [a, b, c]
            inner = val.strip("[]")
            data["keywords"] = [k.strip().strip("'\"") for k in inner.split(",") if k.strip()]

    data["description"] = body
    return data


# ── Discovery ────────────────────────────────────────

def discover_skills() -> None:
    """Scan tools/skills/ directory, register SkillDefs, then import all tool modules."""
    if not _SKILLS_DIR.exists():
        log.warning("Skills directory not found: %s", _SKILLS_DIR)
        return

    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            log.warning("Skill %s missing SKILL.md, skipping", skill_dir.name)
            continue

        parsed = _parse_skill_md(skill_md.read_text(encoding="utf-8"))
        skill_name = parsed.get("name") or skill_dir.name

        _SKILLS[skill_name] = SkillDef(
            name=skill_name,
            path=skill_dir,
            keywords=parsed.get("keywords", []),
            always=parsed.get("always", False),
            description=parsed.get("description", ""),
            tools=[],
        )

    # Import all tool modules (triggers @tool registration)
    for skill_name, skill_def in _SKILLS.items():
        pkg_name = f"tools.skills.{skill_name}"
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError as e:
            log.warning("Failed to import skill package %s: %s", pkg_name, e)
            continue

        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("_"):
                continue
            mod_name = f"{pkg_name}.{info.name}"
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                log.warning("Failed to import tool module %s: %s", mod_name, e)

        # Back-fill tool list for late-registered tools (tool decorator may run before SkillDef exists)
        for tool_name, tool_def in _REGISTRY.items():
            if tool_def.skill == skill_name and tool_name not in skill_def.tools:
                skill_def.tools.append(tool_name)

    total = len(_REGISTRY)
    log.info(
        "Discovered %d skills, %d tools: %s",
        len(_SKILLS),
        total,
        {s: sd.tools for s, sd in _SKILLS.items()},
    )


def discover_tools() -> None:
    """Backward-compatible alias for discover_skills()."""
    discover_skills()


# ── Skill activation ─────────────────────────────────

def get_active_skills(message: str = "") -> list[SkillDef]:
    """Return activated SkillDefs: always=True skills + keyword-matched skills for message."""
    active: list[SkillDef] = []
    msg_lower = message.lower()

    for skill_def in _SKILLS.values():
        if skill_def.always:
            active.append(skill_def)
            continue
        if message and any(kw.lower() in msg_lower for kw in skill_def.keywords):
            active.append(skill_def)

    return active


# ── Public API ───────────────────────────────────────

def set_context(key: str, value: Any) -> None:
    """Inject a shared object (e.g. orchestrator) available to tools via ctx.get()."""
    _CONTEXT[key] = value


def get_schemas(message: str = "") -> list[dict]:
    """Return tool schemas for active skills.

    If message is empty, returns schemas for all tools whose `requires` are satisfied
    (backward-compatible full-load mode).
    """
    if not message:
        # Full load: all tools with satisfied requires
        return [
            td.schema
            for td in _REGISTRY.values()
            if all(k in _CONTEXT for k in td.requires)
        ]

    active_skills = get_active_skills(message)
    active_skill_names = {s.name for s in active_skills}

    result = []
    for td in _REGISTRY.values():
        if td.skill not in active_skill_names:
            continue
        if not all(k in _CONTEXT for k in td.requires):
            continue
        result.append(td.schema)

    log.debug(
        "get_schemas(message=%r): active skills=%s, tools=%d",
        message[:50],
        sorted(active_skill_names),
        len(result),
    )
    return result


def get_skill_context(message: str) -> str:
    """Return SKILL.md bodies of active skills, for injection into system prompt."""
    if not message:
        return ""

    active = get_active_skills(message)
    # Only include non-always skills' docs (system skill is always-on, no need to repeat)
    parts = [s.description for s in active if not s.always and s.description]
    return "\n\n---\n\n".join(parts)


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
