"""grep tool — fast full-text search using ripgrep."""

import asyncio
import os
import shutil
from pathlib import Path

from tools import tool

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[4]))
_RG = shutil.which("rg") or "rg"


@tool(
    name="grep",
    description=(
        "在文件或目录中快速全文搜索（使用 ripgrep）。"
        "适合在文档/代码/日志中找关键词，比 docs_search 快得多，无需预先索引。"
        "支持正则表达式。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "搜索模式（支持正则）"},
            "path": {"type": "string", "description": "搜索路径（文件或目录，默认项目根目录）"},
            "glob": {"type": "string", "description": "文件过滤 glob，如 '*.py'、'*.md'、'*.pdf'"},
            "ignore_case": {"type": "boolean", "description": "忽略大小写（默认 true）"},
            "context_lines": {"type": "integer", "description": "匹配行前后显示的行数（默认 2）"},
            "max_results": {"type": "integer", "description": "最多返回匹配数（默认 50）"},
        },
        "required": ["pattern"],
    },
)
async def handle(args: dict, ctx) -> str:
    pattern = args["pattern"].strip()
    raw_path = args.get("path", "").strip() or DEFAULT_WORKDIR
    glob = args.get("glob", "").strip()
    ignore_case = bool(args.get("ignore_case", True))
    context_lines = int(args.get("context_lines", 2))
    max_results = int(args.get("max_results", 50))

    # Resolve path
    p = Path(raw_path).expanduser()
    if not p.is_absolute():
        p = (Path(DEFAULT_WORKDIR) / p).resolve()

    cmd = [_RG, "--no-heading", "--line-number", f"--context={context_lines}"]
    if ignore_case:
        cmd.append("--ignore-case")
    if glob:
        cmd.extend(["--glob", glob])
    cmd.extend(["--max-count", str(max_results)])
    cmd.append(pattern)
    cmd.append(str(p))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        return "[error] grep 超时（30s）"
    except FileNotFoundError:
        return "[error] ripgrep (rg) 未安装，请运行 brew install ripgrep"
    except Exception as e:
        return f"[error] {e}"

    output = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace").strip()

    if proc.returncode == 1 and not output:
        return f"没有找到匹配「{pattern}」的内容。"
    if proc.returncode > 1:
        return f"[error] rg 返回 {proc.returncode}: {err}"

    # Truncate if too long
    lines = output.splitlines()
    total = len(lines)
    if total > 200:
        output = "\n".join(lines[:200]) + f"\n...(显示前 200 行，共 {total} 行)"

    return output
