"""docs tools — local document semantic search via LlamaIndex + Qwen3 Embedding."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from tools import tool

log = logging.getLogger("docs")

# ── Paths ──────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[4])))
_INDEX_DIR = _REPO_ROOT / "implementation" / "runtime" / "data" / "docs_index"
_META_FILE = _INDEX_DIR / "meta.json"

# ── Embedding config ───────────────────────────────────────────────────────

_EMBED_BASE_URL = os.environ.get(
    "DOCS_EMBED_BASE_URL",
    "http://langdata.models.qwen3-embedding-8b.polaris:8021/v1",
)
_EMBED_API_KEY = os.environ.get("DOCS_EMBED_API_KEY", "none")
_EMBED_MODEL = os.environ.get("DOCS_EMBED_MODEL", "qwen3-8b-embedding-langdata")

# ── Lazy singletons ────────────────────────────────────────────────────────

_index = None          # VectorStoreIndex
_embed_model = None    # OpenAIEmbedding (OpenAI-compatible)


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from llama_index.embeddings.openai import OpenAIEmbedding
        _embed_model = OpenAIEmbedding(
            api_base=_EMBED_BASE_URL,
            api_key=_EMBED_API_KEY,
            model=_EMBED_MODEL,
        )
    return _embed_model


def _load_meta() -> dict:
    if _META_FILE.exists():
        try:
            return json.loads(_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"indexed_files": {}}


def _save_meta(meta: dict) -> None:
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_index():
    """Load or create the persistent VectorStoreIndex."""
    global _index
    if _index is not None:
        return _index

    from llama_index.core import (
        VectorStoreIndex,
        StorageContext,
        load_index_from_storage,
        Settings,
    )

    Settings.embed_model = _get_embed_model()
    Settings.llm = None  # we only use for retrieval, not generation

    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    persist_dir = str(_INDEX_DIR / "vector_store")

    try:
        storage_ctx = StorageContext.from_defaults(persist_dir=persist_dir)
        _index = load_index_from_storage(storage_ctx)
        log.info("Loaded existing docs index from %s", persist_dir)
    except Exception:
        # Fresh index
        _index = VectorStoreIndex(nodes=[], embed_model=_get_embed_model())
        log.info("Created fresh docs index")

    return _index


def _collect_files(path: Path) -> list[Path]:
    """Collect indexable files from a path (file or directory)."""
    supported = {".pdf", ".txt", ".md", ".docx", ".doc", ".csv", ".rst"}
    if path.is_file():
        return [path] if path.suffix.lower() in supported else []
    files = []
    for f in path.rglob("*"):
        if f.is_file() and f.suffix.lower() in supported:
            files.append(f)
    return files


# ── Tools ──────────────────────────────────────────────────────────────────

@tool(
    name="docs_index",
    description=(
        "将文件或目录下的文档（PDF/TXT/MD/DOCX）建立语义索引，之后可用 docs_search 搜索。"
        "支持增量索引（已索引文件自动跳过）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件或目录路径（绝对路径或相对于项目根目录）",
            },
            "force": {
                "type": "boolean",
                "description": "强制重新索引已有文件（默认 false）",
            },
        },
        "required": ["path"],
    },
)
async def docs_index(args: dict, ctx) -> str:
    raw_path = args["path"].strip()
    force = bool(args.get("force", False))

    # Resolve path
    p = Path(raw_path).expanduser()
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve()

    if not p.exists():
        return f"[error] 路径不存在: {p}"

    files = _collect_files(p)
    if not files:
        return f"[error] {p} 下没有可索引的文档（支持 PDF/TXT/MD/DOCX/CSV）"

    meta = _load_meta()
    indexed = meta.get("indexed_files", {})

    to_index = []
    skipped = 0
    for f in files:
        key = str(f)
        mtime = f.stat().st_mtime
        if not force and key in indexed and indexed[key]["mtime"] == mtime:
            skipped += 1
            continue
        to_index.append(f)

    if not to_index:
        return f"全部 {len(files)} 个文件已是最新索引，无需重新索引。"

    try:
        from llama_index.core import SimpleDirectoryReader, Settings
        from llama_index.core.node_parser import SentenceSplitter

        Settings.embed_model = _get_embed_model()
        Settings.llm = None

        # Load documents
        docs = SimpleDirectoryReader(
            input_files=[str(f) for f in to_index],
            filename_as_id=True,
        ).load_data()

        if not docs:
            return "[error] 文档加载为空，请检查文件格式"

        # Parse into nodes
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        nodes = splitter.get_nodes_from_documents(docs)

        index = _get_index()
        index.insert_nodes(nodes)

        # Persist
        persist_dir = str(_INDEX_DIR / "vector_store")
        index.storage_context.persist(persist_dir=persist_dir)

        # Update meta
        for f in to_index:
            indexed[str(f)] = {
                "mtime": f.stat().st_mtime,
                "indexed_at": time.time(),
                "size": f.stat().st_size,
            }
        meta["indexed_files"] = indexed
        _save_meta(meta)

    except Exception as e:
        log.exception("docs_index error")
        return f"[error] 索引失败: {e}"

    result_parts = [f"索引完成：新增 {len(to_index)} 个文件"]
    if skipped:
        result_parts.append(f"跳过 {skipped} 个已索引文件")
    result_parts.append(f"共 {len(nodes)} 个文本块")
    return "，".join(result_parts) + "。"


@tool(
    name="docs_search",
    description=(
        "在已索引的文档中语义搜索，返回最相关的文本片段。"
        "适合：'合同里的付款条款'、'报告中的风险部分'等自然语言查询。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索问题或关键词"},
            "top_k": {"type": "integer", "description": "返回结果数（默认 5）"},
        },
        "required": ["query"],
    },
)
async def docs_search(args: dict, ctx) -> str:
    query = args["query"].strip()
    top_k = int(args.get("top_k", 5))

    if not query:
        return "[error] 请提供搜索内容"

    meta = _load_meta()
    if not meta.get("indexed_files"):
        return "还没有索引任何文档。请先用 docs_index 索引文件。"

    try:
        from llama_index.core import Settings
        Settings.embed_model = _get_embed_model()
        Settings.llm = None

        index = _get_index()
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)

    except Exception as e:
        log.exception("docs_search error")
        return f"[error] 搜索失败: {e}"

    if not nodes:
        return f"没有找到与「{query}」相关的内容。"

    parts = [f"找到 {len(nodes)} 个相关片段：\n"]
    for i, node in enumerate(nodes, 1):
        score = getattr(node, "score", None)
        score_str = f" (相似度 {score:.3f})" if score is not None else ""
        source = Path(node.node.metadata.get("file_path", "unknown")).name
        text = node.node.get_content().strip()
        if len(text) > 600:
            text = text[:600] + "…"
        parts.append(f"[{i}] 来自《{source}》{score_str}:\n{text}\n")

    return "\n".join(parts)


@tool(
    name="docs_list",
    description="列出已索引的所有文档。",
    parameters={"type": "object", "properties": {}},
)
async def docs_list(args: dict, ctx) -> str:
    meta = _load_meta()
    indexed = meta.get("indexed_files", {})

    if not indexed:
        return "还没有索引任何文档。"

    lines = [f"已索引 {len(indexed)} 个文档："]
    for path_str, info in sorted(indexed.items(), key=lambda x: x[1]["indexed_at"], reverse=True):
        p = Path(path_str)
        size_kb = round(info.get("size", 0) / 1024, 1)
        lines.append(f"  - {p.name} ({size_kb} KB)  ← {p.parent}")

    return "\n".join(lines)
