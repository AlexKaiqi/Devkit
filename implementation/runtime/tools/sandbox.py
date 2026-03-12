"""
Tool execution sandbox — path partitioning + command filtering.

Provides check_permission() as a unified pre-check for all tool calls.
See design/decisions/tool-sandbox.md for rationale.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ── Configuration ────────────────────────────────────

SANDBOX_MODE = os.environ.get("SANDBOX_MODE", "enforced")

REPO_ROOT = Path(
    os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[3]))
).resolve()

# ── Path partitioning ────────────────────────────────

# Safe zone — write_file writes freely, read_file reads freely
SAFE_PREFIXES = [
    "implementation/assets/persona/",
    "implementation/data/",
]

# Both raw and resolved forms for macOS (/tmp → /private/tmp)
SAFE_ABSOLUTE = list(set([
    "/tmp/devkit-",
    str(Path("/tmp").resolve()) + "/devkit-",
]))

# Forbidden — both write_file and read_file are denied
FORBIDDEN_PATTERNS = [
    re.compile(r"\.env($|\.)"),
    re.compile(r"\.pem$"),
    re.compile(r"_key$"),
    re.compile(r"_secret"),
]

FORBIDDEN_PREFIXES = [
    "/etc/",
    "/usr/",
    "/var/",
    os.path.expanduser("~/.ssh/"),
    os.path.expanduser("~/.gnupg/"),
]

# ── Command filtering ────────────────────────────────

BLOCKED_PATTERNS = [
    (re.compile(r"\brm\s+-[^\s]*r[^\s]*f"), "rm -rf"),
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"\bmkfs\b"), "mkfs"),
    (re.compile(r"\bdd\s+if="), "dd"),
    (re.compile(r"\b>\s*/dev/sd"), "write to /dev/sd*"),
    (re.compile(r"\bchmod\s+777"), "chmod 777"),
    (re.compile(r"\bcurl\b.*\|\s*(ba)?sh"), "curl | sh"),
]

WARN_PATTERNS = [
    (re.compile(r"\bgit\s+push\s+.*--force"), "git push --force"),
    (re.compile(r"\bgit\s+reset\s+--hard"), "git reset --hard"),
    (re.compile(r"\brm\s+-r\b"), "rm -r"),
    (re.compile(r"\bpip\s+install\b"), "pip install"),
]


# ── Path classification ──────────────────────────────

def classify_path(path_str: str) -> str:
    """Classify a file path as 'safe', 'controlled', or 'forbidden'.

    Args:
        path_str: Absolute or relative file path.

    Returns:
        One of 'safe', 'controlled', 'forbidden'.
    """
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    else:
        p = p.resolve()

    abs_str = str(p)

    # 1. Check forbidden patterns (filename-based)
    name = p.name
    rel_str = abs_str  # use full path for pattern matching
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(name) or pattern.search(rel_str):
            return "forbidden"

    # 2. Check forbidden absolute prefixes
    for prefix in FORBIDDEN_PREFIXES:
        if abs_str.startswith(prefix):
            return "forbidden"

    # 3. Check if inside REPO_ROOT
    try:
        rel = p.relative_to(REPO_ROOT)
        rel_posix = rel.as_posix()
    except ValueError:
        # Outside repo root — check safe absolute prefixes
        for prefix in SAFE_ABSOLUTE:
            if abs_str.startswith(prefix):
                return "safe"
        return "forbidden"

    # 4. Inside repo root — check safe prefixes
    for prefix in SAFE_PREFIXES:
        if rel_posix.startswith(prefix) or (rel_posix + "/").startswith(prefix):
            return "safe"

    # 5. Check safe absolute prefixes (e.g. /tmp/devkit-*)
    for prefix in SAFE_ABSOLUTE:
        if abs_str.startswith(prefix):
            return "safe"

    # 6. Inside repo but not in safe zone → controlled
    return "controlled"


# ── Permission check ─────────────────────────────────

def check_permission(name: str, arguments: dict) -> str | None:
    """Check if a tool call is allowed.

    Returns:
        None if allowed, or a denial/confirmation message string.
    """
    if SANDBOX_MODE == "disabled":
        return None

    if name == "exec":
        return _check_exec(arguments)
    elif name == "write_file":
        return _check_write_file(arguments)
    elif name == "read_file":
        return _check_read_file(arguments)

    return None


def _check_exec(arguments: dict) -> str | None:
    command = arguments.get("command", "")
    confirmed = arguments.get("confirmed", False)

    # Check blocked patterns
    for pattern, desc in BLOCKED_PATTERNS:
        if pattern.search(command):
            return f"[denied] 危险命令被拒绝: {desc}"

    # Check warn patterns
    if not confirmed:
        for pattern, desc in WARN_PATTERNS:
            if pattern.search(command):
                return f"[confirm_required] 即将执行: {command}。请确认后重试。"

    return None


def _check_write_file(arguments: dict) -> str | None:
    path = arguments.get("path", "")
    confirmed = arguments.get("confirmed", False)

    zone = classify_path(path)

    if zone == "forbidden":
        return f"[denied] 禁止写入: {path}"
    elif zone == "controlled" and not confirmed:
        return f"[confirm_required] 即将写入受控区: {path}。请确认后重试。"

    return None


def _check_read_file(arguments: dict) -> str | None:
    path = arguments.get("path", "")

    zone = classify_path(path)

    if zone == "forbidden":
        return f"[denied] 禁止读取: {path}"

    return None
