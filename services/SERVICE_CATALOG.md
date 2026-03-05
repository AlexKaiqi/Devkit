# 服务总览

能力 → 实现的映射。每个服务解决一个明确的问题。

## 服务清单

| 服务 | 解决的问题 | 对应能力 | 端口 | 技术 |
|------|-----------|---------|------|------|
| `gateway_client.py` | 统一 Gateway WebSocket 通信 | 所有渠道共用 | - | Python, websockets, Ed25519 |
| `voice-chat/` | 风铃 Web 语音+文字客户端 | 语音交互, 视觉理解 | :3001 | Python FastAPI + HTML/JS |
| `telegram-bot/` | Telegram 即时通讯渠道 | 多渠道对话, 语音交互 | - | Python, python-telegram-bot |
| `doubao-stt-proxy/` | Whisper API → 火山引擎 ASR 代理 | 语音识别 | :8787 | Python FastAPI |
| `searxng/` | 自托管搜索引擎配置 | 知识检索 | :8080 | Docker, YAML 配置 |
| `heartbeat/` | macOS 定时巡检配置 | 定时巡检 | - | launchd plist |

## 服务依赖关系

```
风铃 (voice-chat)  ─┬── gateway_client.py ──→ OpenClaw Gateway (:18789)
                    ├── doubao-stt-proxy (:8787)
                    └── 豆包 TTS API (直连火山引擎)

Telegram Bot       ─┬── gateway_client.py ──→ OpenClaw Gateway (:18789)
                    ├── doubao-stt-proxy (:8787)
                    └── 豆包 TTS API

OpenClaw Gateway   ─┬── LLM API (OpenAI 兼容)
                    ├── Cursor CLI
                    ├── SearXNG (:8080)
                    └── MCP Servers (akshare-one-mcp 等)
```

## 配置入口

| 配置项 | 文件 | 服务 |
|--------|------|------|
| 火山引擎凭据 | `.env` (DOUBAO_APPID, DOUBAO_TOKEN) | STT Proxy, 风铃 TTS, Telegram TTS |
| TTS 默认音色 | `.env` (TTS_VOICE) | 风铃, Telegram |
| Telegram Bot | `.env` (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) | Telegram Bot |
| SearXNG | `searxng/settings.yml` | SearXNG Docker |
| LLM | `~/.openclaw/openclaw.json` | Gateway |

## 启停管理

所有服务通过根目录脚本统一管理：

```bash
./start.sh    # 启动全部
./stop.sh     # 停止全部
./check.sh    # 健康检查
```

日志位置：

| 服务 | 日志 |
|------|------|
| STT Proxy | `/tmp/doubao-stt-proxy.log` |
| Gateway | `/tmp/openclaw-gateway.log` |
| OpenCami | `/tmp/opencami.log` |
| 风铃 | `/tmp/voice-chat.log` |
| Telegram Bot | `/tmp/telegram-bot.log` |
| SearXNG | `docker logs -f searxng` |
