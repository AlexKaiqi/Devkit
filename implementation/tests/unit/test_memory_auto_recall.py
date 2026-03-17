"""Tests for auto-recall injection in agent.chat_send (Feature 2)."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))


async def _collect_events(agent, session_key, message):
    """Helper: collect all events from chat_send."""
    events = []
    async for evt in agent.chat_send(session_key, message):
        events.append(evt)
    return events


def _make_agent():
    """Create a LocalAgent with mocked OpenAI client."""
    from agent import LocalAgent
    agent = LocalAgent.__new__(LocalAgent)
    agent._sessions = {}
    agent._sessions_dir = Path("/tmp/test_agent_sessions")
    agent._task_graph_store = None
    agent._task_orchestrator = None
    agent._workspace = Path("/tmp")
    agent._system_prompt = "test system prompt"
    agent.model = "test-model"
    return agent


def _make_mock_openai_client(text_content="test reply"):
    """Return a mock OpenAI client that yields a simple text response."""
    from openai.types.chat.chat_completion_chunk import (
        ChatCompletionChunk, Choice, ChoiceDelta
    )

    async def mock_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = text_content
        chunk.choices[0].delta.tool_calls = None
        yield chunk

        # Final empty chunk
        end = MagicMock()
        end.choices = [MagicMock()]
        end.choices[0].delta = MagicMock()
        end.choices[0].delta.content = None
        end.choices[0].delta.tool_calls = None
        yield end

    mock_client = MagicMock()
    mock_create = AsyncMock(return_value=mock_stream())
    mock_client.chat.completions.create = mock_create
    return mock_client


@pytest.mark.asyncio
async def test_recall_injected_when_results_found():
    """mock run_tool 返回有内容 → api_messages 含 [记忆检索]"""
    agent = _make_agent()
    agent.client = _make_mock_openai_client("hello")

    recall_result = "找到 2 条结果：\n[MEMORY.md] 主人喜欢喝咖啡\n[MEMORY.md] 主人的生日是5月1日"

    captured_messages = []

    original_create = agent.client.chat.completions.create

    async def capture_create(*args, **kwargs):
        msgs = kwargs.get("messages", [])
        captured_messages.extend(msgs)
        return await original_create(*args, **kwargs)

    agent.client.chat.completions.create = capture_create

    with patch("agent.run_tool", new_callable=AsyncMock) as mock_run_tool:
        mock_run_tool.return_value = recall_result
        events = await _collect_events(agent, "session-test", "test message")

    # Check that [记忆检索] was injected
    contents = [m.get("content", "") for m in captured_messages if isinstance(m.get("content"), str)]
    assert any("[记忆检索]" in c for c in contents), f"No [记忆检索] in messages: {contents}"


@pytest.mark.asyncio
async def test_recall_not_injected_when_empty():
    """返回 "未找到" → 不注入"""
    agent = _make_agent()
    agent.client = _make_mock_openai_client("hello")

    captured_messages = []
    original_create = agent.client.chat.completions.create

    async def capture_create(*args, **kwargs):
        msgs = kwargs.get("messages", [])
        captured_messages.extend(msgs)
        return await original_create(*args, **kwargs)

    agent.client.chat.completions.create = capture_create

    with patch("agent.run_tool", new_callable=AsyncMock) as mock_run_tool:
        mock_run_tool.return_value = "未找到包含「test」的记忆条目。"
        events = await _collect_events(agent, "session-test", "test message")

    contents = [m.get("content", "") for m in captured_messages if isinstance(m.get("content"), str)]
    assert not any("[记忆检索]" in c for c in contents)


@pytest.mark.asyncio
async def test_recall_only_on_first_round():
    """tool_round==2 时不重复注入"""
    agent = _make_agent()

    recall_result = "找到 1 条结果：\n[MEMORY.md] test"
    call_count = 0
    captured_system_messages = []

    # First call returns a tool call, second call returns text
    import json as _json

    async def mock_stream_with_tool():
        # Yield a tool call
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = None
        tc = MagicMock()
        tc.index = 0
        tc.id = "call-1"
        tc.function = MagicMock()
        tc.function.name = "recall"
        tc.function.arguments = '{"query": "test"}'
        chunk.choices[0].delta.tool_calls = [tc]
        yield chunk

    async def mock_stream_text():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "done"
        chunk.choices[0].delta.tool_calls = None
        yield chunk

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        msgs = kwargs.get("messages", [])
        for m in msgs:
            if m.get("role") == "system":
                captured_system_messages.append(m.get("content", ""))
        if call_count == 1:
            return mock_stream_with_tool()
        return mock_stream_text()

    agent.client = MagicMock()
    agent.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    with patch("agent.run_tool", new_callable=AsyncMock) as mock_run_tool:
        mock_run_tool.return_value = recall_result
        events = await _collect_events(agent, "session-test", "test message")

    # Count [记忆检索] injections across all rounds
    inject_count = sum(1 for c in captured_system_messages if "[记忆检索]" in c)
    assert inject_count <= 1, f"[记忆检索] injected {inject_count} times (expected <=1)"


@pytest.mark.asyncio
async def test_recall_failure_does_not_block():
    """recall 抛异常 → chat_send 正常继续"""
    agent = _make_agent()
    agent.client = _make_mock_openai_client("all good")

    with patch("agent.run_tool", new_callable=AsyncMock) as mock_run_tool:
        mock_run_tool.side_effect = Exception("recall failed")
        events = await _collect_events(agent, "session-test", "test")

    # Should not error out, should have text event
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) > 0
