"""Tests for watchlist feature (Feature 3)."""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))


@pytest.fixture
def watchlist_path(tmp_path):
    return tmp_path / "watchlist.json"


@pytest.fixture
def tools_dir(tmp_path):
    """Create a fake tools skills dir on sys.path for the watchlist skill tests."""
    return tmp_path


# ── Tool function tests ──────────────────────────────────────

def _import_watch_tools(watchlist_json_path):
    """Import watch tool handlers directly by patching DATA_PATH."""
    import importlib
    import tools.skills.watchlist.watch as watch_mod
    original_path = watch_mod.DATA_PATH
    watch_mod.DATA_PATH = watchlist_json_path
    return watch_mod, original_path


@pytest.mark.asyncio
async def test_watch_add_writes_json(watchlist_path):
    """watch_add 写入 watchlist.json"""
    import tools.skills.watchlist.watch as watch_mod
    orig = watch_mod.DATA_PATH
    watch_mod.DATA_PATH = watchlist_path
    try:
        ctx = MagicMock()
        ctx.session_key = "test-session"
        result = await watch_mod.watch_add(
            {"topic": "A股行情", "query": "沪深300", "interval_hours": 12}, ctx
        )
        assert "watch_id" in result
        data = json.loads(watchlist_path.read_text())
        assert len(data) == 1
        assert data[0]["topic"] == "A股行情"
        assert data[0]["query"] == "沪深300"
        assert data[0]["interval_hours"] == 12
    finally:
        watch_mod.DATA_PATH = orig


@pytest.mark.asyncio
async def test_watch_remove_deletes_entry(watchlist_path):
    """watch_remove 删除条目"""
    import tools.skills.watchlist.watch as watch_mod
    orig = watch_mod.DATA_PATH
    watch_mod.DATA_PATH = watchlist_path
    try:
        ctx = MagicMock()
        ctx.session_key = "test-session"
        result = await watch_mod.watch_add({"topic": "test", "query": "test"}, ctx)
        # parse watch_id from result string
        import re
        m = re.search(r'"watch_id":\s*"([^"]+)"', result)
        if not m:
            # try JSON parse
            data = json.loads(result)
            watch_id = data["watch_id"]
        else:
            watch_id = m.group(1)

        await watch_mod.watch_remove({"watch_id": watch_id}, ctx)
        data = json.loads(watchlist_path.read_text())
        assert not any(e["watch_id"] == watch_id for e in data)
    finally:
        watch_mod.DATA_PATH = orig


@pytest.mark.asyncio
async def test_watch_list_returns_all(watchlist_path):
    """watch_list 返回全部条目"""
    import tools.skills.watchlist.watch as watch_mod
    orig = watch_mod.DATA_PATH
    watch_mod.DATA_PATH = watchlist_path
    try:
        ctx = MagicMock()
        ctx.session_key = "test-session"
        await watch_mod.watch_add({"topic": "A", "query": "qa"}, ctx)
        await watch_mod.watch_add({"topic": "B", "query": "qb"}, ctx)
        result = await watch_mod.watch_list({}, ctx)
        assert "A" in result
        assert "B" in result
    finally:
        watch_mod.DATA_PATH = orig


# ── WatchlistChecker tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_check_notifies_on_change(watchlist_path, tmp_path):
    """hash 变化 → notify 被调用"""
    from watchlist_checker import WatchlistChecker

    old_hash = "aaaaaa"
    entry = {
        "watch_id": "w1",
        "topic": "test topic",
        "query": "test query",
        "interval_hours": 1,
        "session_key": "s1",
        "last_checked_at": "2000-01-01T00:00:00",
        "last_result_hash": old_hash,
    }
    watchlist_path.write_text(json.dumps([entry]))

    called_tools = []

    async def fake_run_tool(name, args, session_key=""):
        called_tools.append((name, args))
        if name == "search":
            return "new result content different"
        return "ok"

    checker = WatchlistChecker(
        data_path=watchlist_path,
        run_tool_fn=fake_run_tool,
        interval_sec=9999,
    )
    await checker._check_all()

    notify_calls = [(n, a) for n, a in called_tools if n == "notify"]
    assert len(notify_calls) == 1
    assert "test topic" in notify_calls[0][1].get("message", "")


@pytest.mark.asyncio
async def test_check_silent_on_no_change(watchlist_path):
    """hash 不变 → notify 不被调用"""
    from watchlist_checker import WatchlistChecker
    import hashlib

    content = "same result"
    content_hash = hashlib.md5(content.encode()).hexdigest()

    entry = {
        "watch_id": "w2",
        "topic": "no change",
        "query": "query",
        "interval_hours": 1,
        "session_key": "s1",
        "last_checked_at": "2000-01-01T00:00:00",
        "last_result_hash": content_hash,
    }
    watchlist_path.write_text(json.dumps([entry]))

    called_tools = []

    async def fake_run_tool(name, args, session_key=""):
        called_tools.append(name)
        return content

    checker = WatchlistChecker(watchlist_path, fake_run_tool, 9999)
    await checker._check_all()

    assert "notify" not in called_tools


@pytest.mark.asyncio
async def test_check_skips_not_due(watchlist_path):
    """刚检查过的条目 → search 不被调用"""
    from watchlist_checker import WatchlistChecker
    from datetime import datetime, timezone

    entry = {
        "watch_id": "w3",
        "topic": "recent",
        "query": "query",
        "interval_hours": 24,
        "session_key": "s1",
        "last_checked_at": datetime.now(timezone.utc).isoformat(),  # just now
        "last_result_hash": "",
    }
    watchlist_path.write_text(json.dumps([entry]))

    called_tools = []

    async def fake_run_tool(name, args, session_key=""):
        called_tools.append(name)
        return "result"

    checker = WatchlistChecker(watchlist_path, fake_run_tool, 9999)
    await checker._check_all()

    assert "search" not in called_tools
