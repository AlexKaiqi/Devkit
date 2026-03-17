"""Tests for code_agent skill — Claude Code CLI integration."""

import asyncio
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


def _make_proc_mock(stdout=b"", stderr=b"", returncode=0):
    """Create a mock subprocess with given outputs."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    return proc


@pytest.mark.asyncio
async def test_handle_success():
    """成功执行：JSON 输出正确解析，结果包含文本和 cost。"""
    result_json = json.dumps({
        "result": "已完成：创建了 hello.py",
        "cost_usd": 0.0123,
        "duration_ms": 5000,
    })
    proc = _make_proc_mock(stdout=result_json.encode())

    with patch("asyncio.create_subprocess_exec", return_value=proc), \
         patch("asyncio.wait_for", return_value=(result_json.encode(), b"")):
        proc.communicate = AsyncMock(return_value=(result_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "创建 hello.py"}, _ctx())

    assert "已完成：创建了 hello.py" in result
    assert "$0.0123" in result
    assert "5.0s" in result


@pytest.mark.asyncio
async def test_handle_timeout():
    """超时场景：返回超时错误信息。"""
    proc = _make_proc_mock()

    async def _timeout_communicate():
        raise asyncio.TimeoutError()

    with patch("asyncio.create_subprocess_exec", return_value=proc), \
         patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "很长的任务"}, _ctx())

    assert "超时" in result
    assert "[error]" in result


@pytest.mark.asyncio
async def test_handle_process_error():
    """非零退出码：返回 stderr 错误信息。"""
    proc = _make_proc_mock(
        stdout=b"",
        stderr=b"Error: something went wrong",
        returncode=1,
    )

    with patch("asyncio.create_subprocess_exec", return_value=proc), \
         patch("asyncio.wait_for", return_value=(b"", b"Error: something went wrong")):
        proc.communicate = AsyncMock(return_value=(b"", b"Error: something went wrong"))
        proc.returncode = 1

        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "会失败的任务"}, _ctx())

    assert "[error]" in result
    assert "something went wrong" in result


@pytest.mark.asyncio
async def test_handle_cli_not_found():
    """CLI 找不到：返回 FileNotFoundError 信息。"""
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("not found")):
        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "test"}, _ctx())

    assert "[error]" in result
    assert "找不到" in result


def test_model_mapping():
    """验证 sonnet/haiku/opus 参数映射到正确模型名。"""
    from tools.skills.coding.code_agent import MODEL_MAP

    assert MODEL_MAP["sonnet"] == "claude-sonnet-4-5"
    assert MODEL_MAP["haiku"] == "claude-haiku-4-5"
    assert MODEL_MAP["opus"] == "claude-opus-4-5"


@pytest.mark.asyncio
async def test_handle_non_json_output():
    """非 JSON 输出：直接返回原始文本。"""
    raw_text = b"This is plain text output, not JSON"
    proc = _make_proc_mock(stdout=raw_text)

    with patch("asyncio.create_subprocess_exec", return_value=proc), \
         patch("asyncio.wait_for", return_value=(raw_text, b"")):
        proc.communicate = AsyncMock(return_value=(raw_text, b""))

        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "test"}, _ctx())

    assert "This is plain text output" in result


@pytest.mark.asyncio
async def test_handle_default_model():
    """默认使用 sonnet 模型。"""
    result_json = json.dumps({"result": "done", "cost_usd": 0.01})
    proc = _make_proc_mock(stdout=result_json.encode())
    captured_cmd = []

    async def _capture_exec(*args, **kwargs):
        captured_cmd.extend(args)
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=_capture_exec), \
         patch("asyncio.wait_for", return_value=(result_json.encode(), b"")):
        proc.communicate = AsyncMock(return_value=(result_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        await handle({"prompt": "test task"}, _ctx())

    # 命令中应包含 sonnet 模型
    assert "claude-sonnet-4-5" in captured_cmd


@pytest.mark.asyncio
async def test_methodology_context_injected():
    """有方法论引擎且有活跃 Feature 时，CLI 命令包含 --append-system-prompt。"""
    result_json = json.dumps({"result": "done", "cost_usd": 0.01})
    proc = _make_proc_mock(stdout=result_json.encode())
    captured_cmd = []

    async def _capture_exec(*args, **kwargs):
        captured_cmd.extend(args)
        return proc

    # 构造带 methodology_engine 的 ctx
    ctx = _ctx()
    mock_engine = MagicMock()
    ctx.get = MagicMock(return_value=mock_engine)

    methodology_text = "[方法论状态]\nFeature: test (new_capability) — 当前阶段: requirements\n⛔ 门控未通过"

    with patch("asyncio.create_subprocess_exec", side_effect=_capture_exec), \
         patch("asyncio.wait_for", return_value=(result_json.encode(), b"")), \
         patch("methodology.context.build_methodology_context", return_value=methodology_text) as mock_build:
        proc.communicate = AsyncMock(return_value=(result_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        await handle({"prompt": "test task"}, ctx)

    assert "--append-system-prompt" in captured_cmd
    assert methodology_text in captured_cmd
    ctx.get.assert_called_with("methodology_engine")


@pytest.mark.asyncio
async def test_no_methodology_when_no_engine():
    """无方法论引擎时，CLI 命令不包含 --append-system-prompt。"""
    result_json = json.dumps({"result": "done", "cost_usd": 0.01})
    proc = _make_proc_mock(stdout=result_json.encode())
    captured_cmd = []

    async def _capture_exec(*args, **kwargs):
        captured_cmd.extend(args)
        return proc

    # ctx 无 methodology_engine（get 返回 None）
    ctx = _ctx()
    ctx.get = MagicMock(return_value=None)

    with patch("asyncio.create_subprocess_exec", side_effect=_capture_exec), \
         patch("asyncio.wait_for", return_value=(result_json.encode(), b"")):
        proc.communicate = AsyncMock(return_value=(result_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        await handle({"prompt": "test task"}, ctx)

    assert "--append-system-prompt" not in captured_cmd


@pytest.mark.asyncio
async def test_methodology_context_empty_string_no_append():
    """方法论引擎存在但返回空字符串时，不附加 --append-system-prompt。"""
    result_json = json.dumps({"result": "done", "cost_usd": 0.01})
    proc = _make_proc_mock(stdout=result_json.encode())
    captured_cmd = []

    async def _capture_exec(*args, **kwargs):
        captured_cmd.extend(args)
        return proc

    ctx = _ctx()
    mock_engine = MagicMock()
    ctx.get = MagicMock(return_value=mock_engine)

    with patch("asyncio.create_subprocess_exec", side_effect=_capture_exec), \
         patch("asyncio.wait_for", return_value=(result_json.encode(), b"")), \
         patch("methodology.context.build_methodology_context", return_value=""):
        proc.communicate = AsyncMock(return_value=(result_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        await handle({"prompt": "test task"}, ctx)

    assert "--append-system-prompt" not in captured_cmd


@pytest.mark.asyncio
async def test_methodology_context_exception_graceful():
    """方法论上下文构建异常时，降级运行不报错。"""
    result_json = json.dumps({"result": "done", "cost_usd": 0.01})
    proc = _make_proc_mock(stdout=result_json.encode())
    captured_cmd = []

    async def _capture_exec(*args, **kwargs):
        captured_cmd.extend(args)
        return proc

    ctx = _ctx()
    mock_engine = MagicMock()
    ctx.get = MagicMock(return_value=mock_engine)

    with patch("asyncio.create_subprocess_exec", side_effect=_capture_exec), \
         patch("asyncio.wait_for", return_value=(result_json.encode(), b"")), \
         patch("methodology.context.build_methodology_context", side_effect=RuntimeError("boom")):
        proc.communicate = AsyncMock(return_value=(result_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "test task"}, ctx)

    # 不应包含 --append-system-prompt，但应正常返回结果
    assert "--append-system-prompt" not in captured_cmd
    assert "done" in result


@pytest.mark.asyncio
async def test_handle_budget_exceeded():
    """预算耗尽：返回有意义的错误消息而非'无输出'。"""
    budget_json = json.dumps({
        "type": "result",
        "subtype": "error_max_budget_usd",
        "is_error": False,
        "result": None,
        "total_cost_usd": 0.5787,
        "duration_ms": 41834,
    })
    proc = _make_proc_mock(stdout=budget_json.encode())

    with patch("asyncio.create_subprocess_exec", return_value=proc), \
         patch("asyncio.wait_for", return_value=(budget_json.encode(), b"")):
        proc.communicate = AsyncMock(return_value=(budget_json.encode(), b""))

        from tools.skills.coding.code_agent import handle
        result = await handle({"prompt": "复杂编码任务"}, _ctx())

    assert "预算耗尽" in result
    assert "$0.58" in result
    assert "截断" in result
