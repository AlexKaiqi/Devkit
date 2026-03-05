"""L3 Integration: Agent tool calling — file, shell, git, MCP."""

import pytest


async def _send_and_collect(gw, session_key: str, message: str, timeout_ms: int = 90000) -> str:
    full_text = ""
    async for evt in gw.chat_send(session_key, message, timeout_ms=timeout_ms):
        if evt["type"] == "text":
            full_text += evt["content"]
        elif evt["type"] in ("done", "error"):
            break
    return full_text


@pytest.mark.requires_gateway
class TestFileOperations:

    @pytest.mark.asyncio
    async def test_read_status_md(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "读取 STATUS.md 文件的内容，告诉我第一行写了什么",
        )
        assert len(reply) > 5

    @pytest.mark.asyncio
    async def test_write_and_verify_file(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "创建文件 /tmp/pytest_devkit_test.txt，内容为 'hello from pytest'，然后读取它确认内容",
        )
        assert "hello" in reply.lower() or "pytest" in reply.lower()


@pytest.mark.requires_gateway
class TestShellCommands:

    @pytest.mark.asyncio
    async def test_execute_date(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "执行 shell 命令 `date +%Y` 并告诉我输出结果",
        )
        assert "202" in reply

    @pytest.mark.asyncio
    async def test_execute_pwd(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "执行 pwd 命令告诉我当前目录",
        )
        assert "/" in reply


@pytest.mark.requires_gateway
class TestGitOperations:

    @pytest.mark.asyncio
    async def test_git_status(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "执行 git status 命令并告诉我当前分支名",
        )
        assert len(reply) > 3


@pytest.mark.requires_gateway
class TestMcpStock:

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_query_stock(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "查询贵州茅台（600519）的最新股价",
            timeout_ms=120000,
        )
        assert len(reply) > 5
