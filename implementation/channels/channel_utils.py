"""channel_utils.py — 各 channel 共享工具函数。"""

import base64
import os
import re
import subprocess
import tempfile
from pathlib import Path

import mistune

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


class _PlainTextRenderer(mistune.BaseRenderer):
    """mistune Renderer：将 Markdown AST 渲染为适合 TTS 朗读的纯文本。"""

    NAME = "plain"

    # ── Block-level ──────────────────────────────────────
    def paragraph(self, token, state):
        return self.render_children(token, state) + "\n\n"

    def heading(self, token, state):
        return self.render_children(token, state) + "\n\n"

    def thematic_break(self, token, state):
        return ""

    def block_code(self, token, state):
        # 代码块整体跳过（由 parse_response 单独提取为 attachment）
        return ""

    def block_quote(self, token, state):
        return self.render_children(token, state)

    def list(self, token, state):
        return self.render_children(token, state)

    def list_item(self, token, state):
        return self.render_children(token, state) + "\n"

    def block_text(self, token, state):
        return self.render_children(token, state)

    # ── Table ─────────────────────────────────────────────
    def table(self, token, state):
        return self.render_children(token, state) + "\n"

    def table_head(self, token, state):
        cells = self.render_children(token, state)
        return cells + "\n"

    def table_body(self, token, state):
        return self.render_children(token, state)

    def table_row(self, token, state):
        return self.render_children(token, state) + "\n"

    def table_cell(self, token, state):
        return self.render_children(token, state) + " "

    def block_html(self, token, state):
        # 去掉 HTML 标签，保留标签内文字
        raw = token.get("raw", "")
        return re.sub(r"<[^>]+>", "", raw)

    def blank_line(self, token, state):
        return ""

    def linebreak(self, token, state):
        return "\n"

    # ── Inline-level ─────────────────────────────────────
    def text(self, token, state):
        return token.get("raw", "")

    def strong(self, token, state):
        return self.render_children(token, state)

    def emphasis(self, token, state):
        return self.render_children(token, state)

    def codespan(self, token, state):
        return token.get("raw", "")

    def strikethrough(self, token, state):
        return self.render_children(token, state)

    def link(self, token, state):
        # 只读链接文字，丢弃 URL
        return self.render_children(token, state)

    def image(self, token, state):
        return token.get("attrs", {}).get("alt", "")

    def inline_html(self, token, state):
        return ""

    def softline(self, token, state):
        return " "

    def hardline(self, token, state):
        return "\n"

    def render_token(self, token, state):
        # 未显式处理的 token 类型：尝试渲染子节点，否则返回空
        func = self._get_method(token["type"])
        if func:
            return func(token, state)
        children = token.get("children")
        if children:
            return self.render_children(token, state)
        return token.get("raw", "")

    def render_children(self, token, state):
        children = token.get("children") or []
        return "".join(self.render_token(child, state) for child in children)

    def __call__(self, tokens, state):
        return "".join(self.render_token(tok, state) for tok in tokens)


_md = mistune.create_markdown(renderer=_PlainTextRenderer(), plugins=["strikethrough", "table"])


def clean_for_tts(text: str) -> str:
    """通过 mistune AST 将 Markdown 转换为适合 TTS 朗读的纯文本。"""
    result = _md(text)
    # 合并多余空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def parse_response(text: str) -> dict:
    """将 LLM 回复拆分为可朗读文本和代码块附件。"""
    attachments = []
    for m in CODE_BLOCK_RE.finditer(text):
        attachments.append({
            "type": "code",
            "language": m.group(1) or "",
            "content": m.group(2).strip(),
        })
    spoken = CODE_BLOCK_RE.sub("", text).strip()
    spoken = clean_for_tts(spoken)
    return {"spoken": spoken, "attachments": attachments}


def extract_video_frames(video_bytes: bytes, max_frames: int = 4) -> list[str]:
    """从视频中均匀截取帧，返回 base64 data URL 列表。"""
    import logging
    log = logging.getLogger("channel_utils")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        video_path = tmp.name
    out_dir = tempfile.mkdtemp()
    frames: list[str] = []
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(probe.stdout.strip() or "1")
        interval = max(duration / max_frames, 0.5)
        subprocess.run(
            ["ffmpeg", "-i", video_path,
             "-vf", f"fps=1/{interval:.2f},scale=512:-1",
             "-frames:v", str(max_frames), "-q:v", "5", "-y",
             f"{out_dir}/f%03d.jpg"],
            capture_output=True, timeout=60,
        )
        for fp in sorted(Path(out_dir).glob("f*.jpg")):
            b64 = base64.b64encode(fp.read_bytes()).decode()
            frames.append(f"data:image/jpeg;base64,{b64}")
            fp.unlink()
    except Exception as e:
        log.warning("frame extraction failed: %s", e)
    finally:
        Path(video_path).unlink(missing_ok=True)
        try:
            Path(out_dir).rmdir()
        except OSError:
            pass
    return frames
