# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Devkit 是一个围绕**风铃（Fengling）**构建的个人 AI 分身项目。风铃是自有移动端主客户端；Telegram 如果保留，默认只是可选的外部通知或轻量集成工具。所有入口都接入同一个本地 runtime，由 runtime 负责任务、记忆、知识、工具与回报。

仓库采用三层结构：
- `requirements/` — 产品需求、能力定义、验收场景（描述*想要什么*）
- `design/` — 目标架构、接口契约、设计决策（描述*应该怎样*）
- `implementation/` — 源代码、运行时资产、脚本、测试（描述*现在有什么*）

## Commands

```bash
# Setup & run
./setup.sh          # 初始化环境：创建 .env、.venv、安装 Python 依赖和 CLI 工具
./start.sh          # 启动所有服务（SearXNG、STT proxy、Fengling、Telegram bot）
./stop.sh           # 停止所有服务

# Health check
./check.sh          # 人类可读的状态诊断
./check.sh --json   # 机器可读输出

# Tests (always use project .venv)
.venv/bin/pytest implementation/tests/unit/
.venv/bin/pytest implementation/tests/integration/
.venv/bin/pytest implementation/tests/e2e/
.venv/bin/pytest -m "not slow"         # skip slow tests
.venv/bin/pytest -m "requires_agent"   # tests needing LLM API

# Evaluation / acceptance
.venv/bin/python implementation/evals/runners/acceptance_runner.py
```

All Python commands must use the project-local `.venv/bin/python` (Python 3.12+).

## Architecture

**Runtime core** (`implementation/runtime/`): Shared agent runtime — `agent.py`, `tools.py`, `event_bus.py`. Thin OpenAI-compatible model adapter layer, event-driven design for async operations.

**Channels** (`implementation/channels/`):
- `fengling/` — Fengling channel implementation (currently exposed through a FastAPI + WebSocket interface)
- `telegram/` — optional python-telegram-bot integration for external delivery / lightweight commands

**Services** (`implementation/services/`):
- `speech/` — Doubao STT/TTS proxy
- `search/` — SearXNG configuration (Docker)

**Persona assets** (`implementation/assets/persona/`): SOUL.md, IDENTITY.md, USER.md, MEMORY.md — runtime reads these to form agent behavior.

**Ops scripts** (`implementation/ops/scripts/`): `notify.sh` (Telegram instant notification), `timer.sh` (deferred reminder).

**Key reference files:**

| File | Purpose |
|------|---------|
| `requirements/product/goals.md` | Project goals and iteration priorities |
| `requirements/acceptance/README.md` | Acceptance scenario index |
| `design/architecture/system-overview.md` | System architecture |
| `design/decisions/ai-native-development.md` | AI-native development methodology |
| `design/evaluation/eval-protocol.md` | Evaluation protocol |
| `implementation/STATUS.md` | Current implementation state — update after every task |

## Conventions

- **Layer order**: change `requirements/` and `design/` first, then `implementation/`.
- **New capabilities**: write `requirements/acceptance/` scenarios before writing code.
- **After every task**: update `implementation/STATUS.md`.
- **Test after every change**: 实现或修复任何功能后，必须进行完整测试：
  1. 运行单元测试：`.venv/bin/pytest implementation/tests/unit/ -q`
  2. 针对该功能做端到端验证（curl、日志核查、或直接调用相关模块）
  3. 确认无回归后再视为完成
- **Memory**: important findings go to `implementation/assets/persona/MEMORY.md`; daily logs to `implementation/assets/persona/memory/YYYY-MM-DD.md`.
- **Language**: documentation and communication in Chinese; technical terms stay in English.
- **Existing decisions**: follow `design/decisions/README.md` before making new technology choices.
- **Agent mode**: when invoked by a higher-level agent via `cursor agent -p`, execute strictly to the prompt, mark uncertainties as "待确认", and output a completion report (status, changed files, decisions, open items).
