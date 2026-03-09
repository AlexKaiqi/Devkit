# 系统架构

```
用户
  │
  ├── 风铃 (:3001)              ← 语音+文字（语音问语音答 · 打字问文字答）
  └── Telegram Bot              ← 即时通讯（文字 + 语音 + 图片 + 视频）
        │
        ▼
LocalAgent (进程内)             ← AI 分身核心（希露菲），openai SDK 直连 LLM
  │
  ├── LLM API                   ← OpenAI 兼容代理 (yinli.one / OpenRouter)
  │
  ├── 内置工具                   ← exec / read_file / write_file / search
  │     ├── Cursor CLI           ← cursor agent -p "..." 执行开发
  │     ├── himalaya             ← 邮件 CLI (IMAP/SMTP)
  │     ├── SearXNG (:8080)      ← 自托管搜索引擎 (Docker)
  │     ├── mcporter             ← MCP 工具（A股数据等）
  │     └── ...                  ← 详见 CAPABILITIES.md
  │
  └── 豆包语音引擎 (:8787)       ← STT（语音识别）+ TTS（语音合成）
        ├── STT: 火山引擎 BigModel ASR（Whisper API 兼容）
        └── TTS: 豆包语音合成大模型（25+大模型音色可选）

事件总线（进程内）
  EventBus (asyncio pub/sub)       ← 异步事件分发：定时器到期、未来扩展
  │
  └── Timer API (:8789)            ← Agent 通过 timer.sh 创建/取消定时器
        └── asyncio.sleep → timer.fired 事件 → session_key 路由 → 投递

数据层
  ├── data/voice-audit/          ← 审计日志（逐条 JSONL，按日存储）
  ├── persona/memory/            ← 每日记忆日志
  └── data/                      ← 通讯录 · 人情记录等结构化数据
```

全部本地运行，无数据外泄。

## 服务拓扑

| 服务 | 端口 | 技术 | 职责 |
|------|------|------|------|
| LocalAgent | 进程内 | Python (openai SDK) | Agent 运行时：LLM 调度、工具调用、会话管理 |
| 风铃 | :3001 | Python FastAPI | 语音+文字 Web 客户端 |
| 豆包 STT Proxy | :8787 | Python FastAPI | Whisper API → 火山引擎 BigModel ASR |
| SearXNG | :8080 | Docker | 自托管搜索引擎（聚合 Google/Bing/DDG）|
| Telegram Bot | - | Python | 即时通讯渠道 |
| EventBus + Timer API | :8789 | Python asyncio | 事件分发 + 定时器调度（进程内，嵌入 Telegram Bot） |

## 通信协议

```
风铃 / Telegram ──HTTP──→ LocalAgent ──openai SDK──→ LLM API
     │                        │
     │← streaming events ─────│ ──exec/read_file/...──→ 工具
```

- 渠道通过 Python 函数调用 `agent.chat_send()` 与 LocalAgent 交互
- LocalAgent 内部：openai SDK streaming + tool-calling loop
- 异步任务：Agent 通过 Timer API 发布延时意图，EventBus 到期后按 `session_key` 路由投递

详见 [specs/event-system.md](specs/event-system.md) 了解事件驱动架构的设计与考量。

## 项目目录四层模型

```
docs/           ← Layer 1: 语义层（要什么、是什么、有什么）
persona/        ← Layer 2: 人格层（Agent 是谁、怎么想、怎么做）
services/       ← Layer 3: 实现层（用什么技术、怎么实现）
根目录脚本       ← Layer 4: 运维层（怎么跑、怎么修、怎么查）
```

详见 [SERVICE_CATALOG.md](../services/SERVICE_CATALOG.md) 了解每个服务的职责和对应能力。
