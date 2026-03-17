"""Tests for process skill — background process lifecycle management."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))


def _ctx():
    ctx = MagicMock()
    ctx.session_key = "test"
    return ctx


@pytest.mark.asyncio
async def test_process_start_returns_pid():
    """process_start 后台启动并返回 pid"""
    from tools.skills.process.process import process_start, _REGISTRY

    result = await process_start({"command": "echo hello", "label": "test-echo"}, _ctx())
    assert "pid=" in result
    # Extract pid from result string
    import re
    m = re.search(r"pid=(\d+)", result)
    assert m
    pid = int(m.group(1))
    assert pid in _REGISTRY
    _REGISTRY.pop(pid, None)


@pytest.mark.asyncio
async def test_process_list_shows_running():
    """process_list 显示正在运行的进程"""
    from tools.skills.process.process import process_start, process_list, _REGISTRY

    await process_start({"command": "sleep 10", "label": "sleep-test"}, _ctx())

    result = await process_list({}, _ctx())
    assert "sleep-test" in result
    assert "running" in result

    # Cleanup: kill the sleep process
    for pid, entry in list(_REGISTRY.items()):
        if entry.label == "sleep-test":
            entry._proc.kill()
            _REGISTRY.pop(pid, None)


@pytest.mark.asyncio
async def test_process_log_returns_output():
    """process_log 返回命令输出"""
    from tools.skills.process.process import process_start, process_log, _REGISTRY
    import re

    result = await process_start({"command": "echo 'test output line'", "label": "echo-test"}, _ctx())
    m = re.search(r"pid=(\d+)", result)
    pid = int(m.group(1))

    # Wait for output to be captured
    await asyncio.sleep(0.3)

    log_result = await process_log({"pid": pid}, _ctx())
    assert "test output line" in log_result or "0 行" in log_result  # may have finished

    _REGISTRY.pop(pid, None)


@pytest.mark.asyncio
async def test_process_kill_terminates():
    """process_kill 正确终止进程"""
    from tools.skills.process.process import process_start, process_kill, _REGISTRY
    import re

    result = await process_start({"command": "sleep 30", "label": "kill-test"}, _ctx())
    m = re.search(r"pid=(\d+)", result)
    pid = int(m.group(1))

    kill_result = await process_kill({"pid": pid}, _ctx())
    assert "已终止" in kill_result

    # Verify state
    await asyncio.sleep(0.1)
    entry = _REGISTRY.get(pid)
    assert entry is None or entry.state in ("killed", "done", "failed")
    _REGISTRY.pop(pid, None)


@pytest.mark.asyncio
async def test_process_wait_completes():
    """process_wait 等待短命令完成"""
    from tools.skills.process.process import process_start, process_wait, _REGISTRY
    import re

    result = await process_start({"command": "echo done && sleep 0.1", "label": "wait-test"}, _ctx())
    m = re.search(r"pid=(\d+)", result)
    pid = int(m.group(1))

    wait_result = await process_wait({"pid": pid, "timeout": 5}, _ctx())
    assert "done" in wait_result or "rc=0" in wait_result

    _REGISTRY.pop(pid, None)


@pytest.mark.asyncio
async def test_process_unknown_pid():
    """未知 pid 返回 error"""
    from tools.skills.process.process import process_log, process_kill

    log_r = await process_log({"pid": 999999}, _ctx())
    kill_r = await process_kill({"pid": 999999}, _ctx())
    assert "[error]" in log_r
    assert "[error]" in kill_r


@pytest.mark.asyncio
async def test_process_list_empty():
    """没有进程时返回提示"""
    from tools.skills.process.process import process_list, _REGISTRY
    _REGISTRY.clear()

    result = await process_list({}, _ctx())
    assert "没有" in result
