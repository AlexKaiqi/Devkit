# 系统架构

```
用户
  │
  ├── 风铃 (:3001)              ← 语音+文字（语音问语音答 · 打字问文字答）
  ├── Telegram Bot              ← 即时通讯（文字 + 语音 + 图片 + 视频）
  └── OpenCami (:3000)          ← 全功能聊天界面（任务调度 · 工具调用）
        │
        ├── 全部通过 WebSocket 接入 ──┐
        ▼                            ▼
OpenClaw Gateway (:18789)       ← AI 分身核心（希露菲），全权代理，调度一切
  │
  ├── Cursor CLI                ← cursor agent -p "..." 执行开发
  │     └── Devkit 仓库          ← 本地文件系统
  │
  ├── 外部工具链                 ← 邮件 / 日历 / 搜索 / 智能家居 / 云存储 ...
  │     ├── himalaya             ← 邮件 CLI (IMAP/SMTP)
  │     ├── SearXNG (:8080)      ← 自托管搜索引擎 (Docker)
  │     ├── peekaboo             ← macOS 桌面 GUI 自动化
  │     ├── playwright           ← Web 浏览器自动化
  │     └── ...                  ← 详见 CAPABILITIES.md
  │
  └── 豆包语音引擎 (:8787)       ← STT（语音识别）+ TTS（语音合成）
        ├── STT: 火山引擎 BigModel ASR（Whisper API 兼容）
        └── TTS: 豆包语音合成大模型（25+大模型音色可选）

数据层
  ├── data/voice-audit/          ← 审计日志（逐条 JSONL，按日存储）
  ├── openclaw/memory/           ← 每日记忆日志
  └── data/                      ← 通讯录 · 人情记录等结构化数据
```

全部本地运行，无数据外泄。

## 服务拓扑

| 服务 | 端口 | 技术 | 职责 |
|------|------|------|------|
| OpenClaw Gateway | :18789 | Node.js | Agent 运行时：LLM 调度、工具调用、会话管理 |
| OpenCami | :3000 | Node.js | 全功能 Web UI (PWA) |
| 风铃 | :3001 | Python FastAPI | 语音+文字 Web 客户端 |
| 豆包 STT Proxy | :8787 | Python FastAPI | Whisper API → 火山引擎 BigModel ASR |
| SearXNG | :8080 | Docker | 自托管搜索引擎（聚合 Google/Bing/DDG）|
| Telegram Bot | - | Python | 即时通讯渠道 |

## 通信协议

```
风铃 / Telegram ──WebSocket──→ Gateway ──RPC──→ Agent ──bash/MCP──→ 工具
     │                              │
     │← agent events (streaming) ───│
     │                              │
     │     Ed25519 设备认证           │
     │     v3 签名握手协议            │
```

- 渠道与 Gateway 之间：WebSocket JSON 帧，Ed25519 challenge-response 握手
- Gateway 内部：RPC (`chat.send`) + 流式事件 (`agent` events)
- 事件隔离：每次 `chat.send` 返回 `runId`，客户端按 `runId` 过滤事件

## 项目目录四层模型

```
docs/           ← Layer 1: 语义层（要什么、是什么、有什么）
openclaw/       ← Layer 2: 人格层（Agent 是谁、怎么想、怎么做）
services/       ← Layer 3: 实现层（用什么技术、怎么实现）
根目录脚本       ← Layer 4: 运维层（怎么跑、怎么修、怎么查）
```

详见 [SERVICE_CATALOG.md](../services/SERVICE_CATALOG.md) 了解每个服务的职责和对应能力。
