"""Tests for docs skill — semantic document search via LlamaIndex."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))


def _ctx():
    ctx = MagicMock()
    ctx.session_key = "test"
    return ctx


def _make_fake_embed():
    """Return a fake embedding model that returns fixed 4-dim vectors."""
    from llama_index.core.base.embeddings.base import BaseEmbedding

    class FakeEmbed(BaseEmbedding):
        model_config = {"arbitrary_types_allowed": True}

        def _get_query_embedding(self, query: str) -> list[float]:
            return [0.1, 0.2, 0.3, 0.4]

        def _get_text_embedding(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3, 0.4]

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return [0.1, 0.2, 0.3, 0.4]

        async def _aget_text_embedding(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3, 0.4]

    return FakeEmbed(model_name="fake")


@pytest.fixture(autouse=True)
def reset_docs_module(tmp_path):
    """Reset module-level singletons and patch paths before each test."""
    import tools.skills.docs.docs as docs_mod

    # Reset singletons
    docs_mod._index = None
    docs_mod._embed_model = None

    # Redirect index dir to tmp
    orig_index_dir = docs_mod._INDEX_DIR
    orig_meta_file = docs_mod._META_FILE

    docs_mod._INDEX_DIR = tmp_path / "docs_index"
    docs_mod._META_FILE = docs_mod._INDEX_DIR / "meta.json"

    # Patch embed model
    fake_embed = _make_fake_embed()
    orig_get_embed = docs_mod._get_embed_model
    docs_mod._get_embed_model = lambda: fake_embed

    yield tmp_path

    # Restore
    docs_mod._INDEX_DIR = orig_index_dir
    docs_mod._META_FILE = orig_meta_file
    docs_mod._get_embed_model = orig_get_embed
    docs_mod._index = None
    docs_mod._embed_model = None


@pytest.mark.asyncio
async def test_docs_index_txt_file(tmp_path):
    """索引 TXT 文件后 meta.json 有记录"""
    import tools.skills.docs.docs as docs_mod

    txt = tmp_path / "test.txt"
    txt.write_text("这是一份测试文档，包含重要的合同条款。付款方式为月结30天。")

    result = await docs_mod.docs_index({"path": str(txt)}, _ctx())
    assert "索引完成" in result or "新增" in result

    meta = json.loads(docs_mod._META_FILE.read_text())
    assert str(txt) in meta["indexed_files"]


@pytest.mark.asyncio
async def test_docs_index_skip_already_indexed(tmp_path):
    """已索引且未变更的文件跳过"""
    import tools.skills.docs.docs as docs_mod

    txt = tmp_path / "doc.txt"
    txt.write_text("内容不变的文档")

    await docs_mod.docs_index({"path": str(txt)}, _ctx())

    # Second index without force — should skip
    result2 = await docs_mod.docs_index({"path": str(txt)}, _ctx())
    assert "跳过" in result2 or "最新" in result2


@pytest.mark.asyncio
async def test_docs_list_empty():
    """没有索引时返回提示"""
    import tools.skills.docs.docs as docs_mod

    result = await docs_mod.docs_list({}, _ctx())
    assert "没有" in result


@pytest.mark.asyncio
async def test_docs_list_shows_files(tmp_path):
    """索引后 docs_list 显示文件"""
    import tools.skills.docs.docs as docs_mod

    txt = tmp_path / "report.txt"
    txt.write_text("季度财务报告内容")
    await docs_mod.docs_index({"path": str(txt)}, _ctx())

    result = await docs_mod.docs_list({}, _ctx())
    assert "report.txt" in result


@pytest.mark.asyncio
async def test_docs_search_no_index():
    """没有索引时搜索返回提示"""
    import tools.skills.docs.docs as docs_mod

    result = await docs_mod.docs_search({"query": "付款条款"}, _ctx())
    assert "没有索引" in result or "先用" in result


@pytest.mark.asyncio
async def test_docs_search_returns_results(tmp_path):
    """索引后搜索返回结果"""
    import tools.skills.docs.docs as docs_mod

    txt = tmp_path / "contract.txt"
    txt.write_text(
        "甲方同意按月结30天方式付款。\n"
        "乙方需在每月最后一个工作日提交发票。\n"
        "逾期付款将按日加收0.05%的违约金。\n" * 10
    )

    await docs_mod.docs_index({"path": str(txt)}, _ctx())

    # Reset index singleton to force reload
    docs_mod._index = None

    result = await docs_mod.docs_search({"query": "付款", "top_k": 3}, _ctx())
    # With fake embeddings returning same vector, retrieval should still work
    assert "找到" in result or "片段" in result or "contract" in result


@pytest.mark.asyncio
async def test_docs_index_nonexistent_path():
    """不存在的路径返回 error"""
    import tools.skills.docs.docs as docs_mod

    result = await docs_mod.docs_index({"path": "/nonexistent/path/doc.txt"}, _ctx())
    assert "[error]" in result


@pytest.mark.asyncio
async def test_docs_index_directory(tmp_path):
    """目录下多个文件都被索引"""
    import tools.skills.docs.docs as docs_mod

    subdir = tmp_path / "docs"
    subdir.mkdir()
    (subdir / "a.txt").write_text("文档A的内容")
    (subdir / "b.md").write_text("# 文档B\n\n内容")
    (subdir / "ignore.exe").write_text("忽略")

    result = await docs_mod.docs_index({"path": str(subdir)}, _ctx())
    assert "2" in result or "新增" in result

    meta = json.loads(docs_mod._META_FILE.read_text())
    keys = list(meta["indexed_files"].keys())
    assert any("a.txt" in k for k in keys)
    assert any("b.md" in k for k in keys)
    assert not any("ignore.exe" in k for k in keys)
