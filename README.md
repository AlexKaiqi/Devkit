# Devkit

AI 原生的个人数字分身平台。语音或文字下达指令 → AI 分身自主拆解、执行、汇报。支持开发、科研、智能家居、生活管理。

## 架构

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
  │     └── ...                  ← 详见 CAPABILITIES.md 第十章
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

## 前置条件

| 依赖 | 用途 | 安装 |
|------|------|------|
| Node.js 20+ | OpenClaw / OpenCami | `brew install node` |
| Python 3.12+ | STT 代理 + 科研/自动化工具链 | `brew install python@3.12` |
| Cursor IDE | 代码执行 Agent | [cursor.com](https://www.cursor.com/) |
| Git | 版本管理 | `brew install git` |
| Docker | SearXNG 搜索引擎 | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| cloudflared | 移动端 HTTPS 隧道 | `brew install cloudflared`（可选） |

## 需要准备的账号和凭据

| 凭据 | 用途 | 获取方式 |
|------|------|----------|
| `DOUBAO_APPID` | 豆包语音识别 + 语音合成 | [火山引擎控制台](https://console.volcengine.com/speech/service/8) → 语音技术 |
| `DOUBAO_TOKEN` | 豆包语音识别 + 语音合成 | 同上，创建应用获取 |
| `LLM_API_KEY` | LLM API | 任意 OpenAI 兼容服务商的 API Key |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot | [@BotFather](https://t.me/BotFather) 创建 Bot 获取（可选） |
| `TELEGRAM_CHAT_ID` | 限制 Bot 只响应你 | 给 Bot 发消息后从日志中获取（可选） |

## 从零安装

### 方式一：AI 引导（推荐）

```bash
git clone <repo-url> Devkit && cd Devkit
```

用 Cursor 打开项目，AI 会自动检测到未完成的配置，交互式引导完成全部初始化。
无需手动读文档 — Cursor Rules 已内置完整的 onboarding 流程。

### 方式二：手动安装

```bash
git clone <repo-url> Devkit && cd Devkit

# 1. 运行安装脚本（检查依赖、创建 .env、安装工具链）
./setup.sh

# 2. 编辑 .env，填入凭据
vim .env

# 3. 再次运行安装（加载 .env 并完成配置）
./setup.sh

# 4. 检查项目状态
./check.sh
```

### OpenClaw 首次配置

安装脚本会检查 OpenClaw，但首次需要手动完成 onboard：

```bash
# 引导式配置（选择 LLM provider、Channel 等）
openclaw onboard

# 同步 Agent 人设配置
./openclaw/sync.sh
```

## 启动 / 停止

```bash
./start.sh    # 启动所有服务（SearXNG + STT 代理 + Gateway + OpenCami）
./stop.sh     # 停止所有服务
```

启动后输出所有服务地址：

```
=== 所有服务已启动 ===

  SearXNG:       http://localhost:8080
  豆包 STT:      http://localhost:8787/health
  Gateway:       ws://localhost:18789
  OpenCami:      http://localhost:3000
  风铃:          http://localhost:3001
  Telegram Bot:  @your_bot_name
  局域网:        http://30.20.186.42:3000
```

## 使用方式

### 风铃 · 双模式对话（推荐日常使用）

浏览器打开 `http://localhost:3001`。两种输入方式，交互行为自动匹配：

| 输入方式 | 操作 | AI 回复方式 |
|---------|------|-----------|
| **语音** | 按住麦克风说话（或按住空格键） | 文字 **+** 语音朗读（逐句流式） |
| **文字** | 输入框打字，Enter 发送 | 仅文字（不触发 TTS） |

其他交互：

- **发送图片/视频**：点击 📎 按钮、Ctrl+V 粘贴、或拖拽到聊天区
- **图片+语音**：先添加图片，再按住说话，AI 同时理解图片和语音
- **文本/附件分区**：对话被朗读，代码/命令只显示不朗读（带语法标签和复制按钮）
- **停止生成**：点击红色停止按钮或按 Esc 键，立即停止生成和语音播放
- **会话保持**：页面刷新不丢失聊天记录（同一标签页内持久化）
- **清空对话**：左上角「清空」按钮重置会话
- **大模型音色**：右上角可切换豆包语音合成大模型音色（25+ 种）

### Telegram Bot · 随时随地

在 Telegram 中搜索你的 Bot，直接发消息。

- **发文字** → 文字回复
- **发语音** → 语音识别 → 文字回复 + 语音回复
- **发图片** → 视觉模型分析 → 文字回复（可附 caption）
- **发视频** → 自动抽帧 → 视觉模型分析 → 文字回复
- 代码块作为独立消息发送，不混入对话文字
- 仅响应配置的 Chat ID（安全限制）

### OpenCami · 全功能界面

浏览器打开 `http://localhost:3000`，通过 OpenClaw Gateway 与 AI 分身对话。

- 支持工具调用、任务调度、多轮上下文
- 适合复杂任务（开发、调研、多步操作）

### 移动端（跨网络）

启动后终端会输出一个 HTTPS 链接（由 Cloudflare Tunnel 提供）：

```
📱 移动端:  https://xxx-xxx.trycloudflare.com
            (HTTPS, 跨网络, 支持语音)
```

手机浏览器打开该链接即可，不限局域网、不需要 VPN、不影响手机代理。
可添加到主屏幕（OpenCami 支持 PWA）。

> Tunnel URL 每次重启会变化。如需固定域名，可注册 Cloudflare 账号并绑定自有域名。

### 虚拟手机（Android 模拟器）

无需真机，在电脑上启动虚拟手机测试移动端体验：

```bash
# 首次安装（约 1GB 下载）
brew install --cask android-commandlinetools
sdkmanager "system-images;android-35;google_apis;arm64-v8a" "platform-tools" "emulator"
avdmanager create avd -n devkit -k "system-images;android-35;google_apis;arm64-v8a" -d pixel_7

# 启动虚拟手机（自动打开 OpenCami）
./phone.sh start

# 关闭
./phone.sh stop
```

### 自动化测试

Playwright 移动端视口测试（iPhone / Pixel 模拟）：

```bash
.venv/bin/python -m pytest tests/mobile/test_opencami.py -v
```

语音端到端测试（TTS 合成 → STT 识别闭环）：

```bash
.venv/bin/python tests/mobile/test_voice_e2e.py
```

视觉理解测试（图片 + 视频，通过视觉模型）：

```bash
.venv/bin/python tests/mobile/test_vision.py
```

手机操作 Agent 测试（需要运行 Android 模拟器）：

```bash
./phone.sh start
.venv/bin/python tests/mobile/test_phone_agent.py
```

### 语音输入

OpenCami 设置中 STT Provider 选择 **OpenAI** 或 **Auto**，语音会通过豆包 BigModel ASR 识别。

### 语音合成 (TTS)

同一 DOUBAO_APPID/TOKEN 同时用于 STT 和 TTS。当前使用**豆包语音合成大模型**（V1 API + `volcano_tts` cluster）：

| voice_type | 名称 | 场景 |
|---|---|---|
| `zh_female_tianmeixiaoyuan_moon_bigtts` | 甜美小源（默认） | 通用 |
| `zh_female_cancan_mars_bigtts` | 灿灿 | 通用 |
| `zh_female_sajiaonvyou_moon_bigtts` | 柔美女友 | 角色扮演 |
| `ICL_zh_female_keainvsheng_tob` | 可爱女生 | 角色扮演 |

风铃右上角可在 25+ 种大模型音色中切换（含通用/角色扮演/多情感/男声）。
可通过 `.env` 中 `TTS_VOICE` 设置默认音色。

## 项目结构

```
Devkit/
├── .env.example              # 环境变量模板
├── setup.sh                  # 一键安装
├── start.sh                  # 一键启动
├── stop.sh                   # 一键停止
├── check.sh                  # 项目状态诊断（支持 --json）
├── docker-compose.yml        # Docker 服务定义（SearXNG + 部署）
├── openclaw/                 # OpenClaw Agent 配置（版本管理）
│   ├── IDENTITY.md           #   人设：名字、性格
│   ├── SOUL.md               #   行为准则、自主权边界
│   ├── USER.md               #   用户信息、管理的项目
│   ├── AGENTS.md             #   工作流指令
│   ├── TOOLS.md              #   工具权限、本地环境
│   ├── HEARTBEAT.md          #   定期巡检规则
│   ├── MEMORY.md             #   长期记忆（用户偏好、经验、背景）
│   ├── memory/               #   每日日志 (YYYY-MM-DD.md)
│   └── sync.sh               #   同步到 ~/.openclaw/workspace/
├── data/                     # 结构化数据
│   ├── contacts.yml          #   通讯录
│   ├── gifts.yml             #   人情往来记录
│   └── voice-audit/          #   对话审计日志 (YYYY-MM-DD.jsonl, 双渠道共用)
├── scripts/                  # 工具脚本
│   ├── notify.sh             #   Telegram 通知推送
│   └── heartbeat.sh          #   定期巡检（launchd 调用）
├── services/
│   ├── gateway_client.py     # OpenClaw Gateway Python 客户端（风铃+Telegram 共用）
│   ├── doubao-stt-proxy/     # 豆包语音识别代理
│   │   ├── server.py          #   FastAPI (Whisper API → 火山引擎 ASR, 自动 ffmpeg 转码)
│   │   ├── start.sh           #   独立启动脚本
│   │   ├── transcribe.sh      #   CLI 转写工具
│   │   └── requirements.txt
│   ├── voice-chat/           # 风铃（语音对话 Web 客户端）
│   │   ├── server.py          #   FastAPI (STT + Gateway 流式 + 豆包 TTS + 审计)
│   │   └── static/index.html  #   前端（push-to-talk + 流式朗读 + 工具状态 + 附件渲染）
│   ├── telegram-bot/         # Telegram Bot
│   │   └── bot.py             #   python-telegram-bot (Gateway + 豆包 STT/TTS + 审计)
│   ├── searxng/              # SearXNG 搜索引擎配置
│   │   └── settings.yml       #   Docker 挂载的配置（启用 JSON API）
│   └── heartbeat/            # 定时巡检
│       └── com.devkit.heartbeat.plist  # macOS launchd 配置
├── docker/                   # Docker 相关
│   ├── entrypoint.sh          #   容器启动脚本
│   └── verify.sh              #   全链路验证脚本
├── tests/mobile/             # 移动端自动化测试
│   ├── test_opencami.py       #   Playwright 视口测试
│   ├── test_voice_e2e.py      #   TTS→STT 语音闭环测试
│   ├── test_vision.py         #   视觉模型图片/视频理解测试
│   └── test_phone_agent.py    #   手机操作 Agent 全流程测试
├── phone.sh                  # 虚拟手机一键启动
├── .cursor/rules/            # Cursor Agent 行为规则（AI 上下文 + 初始化引导）
├── specs/                    # 需求 Spec 模板
├── .audit/                   # Cursor 调用审计日志
├── GOALS.md                  # 项目目标
├── STATUS.md                 # 当前状态
├── DECISIONS.md              # 决策记录
├── PITFALLS.md               # 踩坑手册（Agent 参考）
└── CAPABILITIES.md           # Agent 平台能力需求（选型参考）
```

## 配置说明

### AI 分身人设

AI 分身的名字、性格、行为准则通过 `openclaw/` 目录下的 Markdown 文件定义：

| 文件 | 作用 | 示例 |
|------|------|------|
| `IDENTITY.md` | 名字、角色定位、风格 | 名字、Emoji、一句话描述 |
| `SOUL.md` | 行为准则、自主权边界 | 什么自己决定、什么问用户 |
| `USER.md` | 用户信息 | 称呼、时区、工作风格 |
| `AGENTS.md` | 工作流指令 | 如何调度 Cursor、如何汇报 |
| `TOOLS.md` | 工具权限、本地环境 | 允许/禁止的 Shell 命令 |
| `HEARTBEAT.md` | 定期检查任务 | 巡检频率、检查项 |

修改后同步到运行时：

```bash
vim openclaw/IDENTITY.md       # 编辑人设
./openclaw/sync.sh              # 同步到 ~/.openclaw/workspace/
openclaw gateway restart        # 重启生效
```

### LLM 配置

LLM 由 OpenClaw Gateway 统一管理。首次运行 `openclaw onboard` 时选择 LLM provider。

风铃和 Telegram Bot 不直接调用 LLM — 它们通过 Gateway WebSocket 协议将消息发送给 Agent（希露菲），由 Gateway 选择模型并调度工具。

### OpenClaw 运行时配置

位于 `~/.openclaw/`，由 Gateway 直接使用：

| 文件 | 作用 |
|------|------|
| `openclaw.json` | 主配置：LLM provider、Channel、Gateway 端口、认证 |
| `workspace/*.md` | Agent 人设和工作指令（由 `openclaw/sync.sh` 同步） |

### 豆包 STT 代理

Whisper API 兼容的语音识别代理，将 OpenAI Whisper 格式请求转发到火山引擎 BigModel ASR。

```bash
# 独立测试
curl -F "file=@test.wav" http://localhost:8787/v1/audio/transcriptions
# 返回: {"text": "识别的文字"}

# CLI 转写
./services/doubao-stt-proxy/transcribe.sh /path/to/audio.wav
```

## 日志

```bash
tail -f /tmp/doubao-stt-proxy.log    # STT 代理
tail -f /tmp/openclaw-gateway.log    # Gateway
tail -f /tmp/opencami.log            # OpenCami
tail -f /tmp/voice-chat.log          # 风铃（语音对话）
tail -f /tmp/telegram-bot.log        # Telegram Bot
docker logs -f searxng               # SearXNG 搜索引擎
```

### 审计日志

所有对话交互（风铃 + Telegram）记录在 `data/voice-audit/` 下，按日期存储为 JSONL 格式。

```bash
# 查看今日审计
cat data/voice-audit/$(date +%Y-%m-%d).jsonl | python3 -m json.tool

# 通过 API 查看（风铃运行时）
curl http://localhost:3001/api/audit
curl http://localhost:3001/api/audit?date=2026-03-05
```

每条记录包含：事件类型（stt/chat/tts）、时间戳、渠道（web/telegram）、耗时（ms）、完整文本。

## 产品特性

### 回复内容分区：文本 vs 附件

AI 的回复自动区分**对话文本**和**附件**（代码、命令、配置等结构化内容）：

| | 文本（对话） | 附件（代码块） |
|---|---|---|
| 风铃 Web | 正常显示，逐句朗读 | 深色代码框，语言标签 + 复制按钮，不朗读 |
| Telegram | 作为普通文字消息发送 + TTS 语音 | 作为独立格式化消息发送，不 TTS |

代码块用 ` ``` ` 标记，AI 已被引导遵循此约定。

### 条件语音：语音问语音答

输入方式自动决定回复形态，避免不必要的 TTS 延迟：

| 输入 | AI 回复 | 原因 |
|------|--------|------|
| 语音（按住说话） | 文字 + 逐句语音朗读 | 用户在移动/开车，需要听 |
| 文字（打字发送） | 纯文字 | 用户在看屏幕，不需要声音 |
| Telegram 语音 | 文字 + TTS 语音消息 | 同语音逻辑 |
| Telegram 文字 | 纯文字 | 同文字逻辑 |

### 流式语音合成

语音回复时，TTS 不等全文生成完毕，而是逐句流式合成：

1. LLM 开始流式输出
2. 检测到完整句子（句号/问号/感叹号）后立即提交 TTS
3. 音频生成后排队播放
4. 结果：首句发声延迟显著降低

### 图片 / 视频输入

两个渠道都支持视觉理解，发送图片或视频后 AI 用视觉模型分析内容。

| 操作 | 风铃 (Web) | Telegram |
|------|-----------|----------|
| 图片 | 📎 按钮上传 / Ctrl+V 粘贴 / 拖拽到聊天区 | 直接发送图片 |
| 视频 | 📎 按钮上传 | 直接发送视频 |
| 视频处理 | 服务端用 ffmpeg 抽取关键帧 | 同左 |
| 图片+语音 | 先添加图片，再按住说话 | 图片附加 caption |

视觉模型由 Gateway 统一管理，无需在渠道侧单独配置。

### 统一 Agent 后端

风铃、Telegram Bot、OpenCami 三个渠道全部接入同一个 OpenClaw Gateway：

- **同一个 Agent（希露菲）**：人设、记忆、工具链全部共享
- **完整工具能力**：文件读写、Shell 命令、代码理解、Git 操作、邮件、Docker 管理等（端到端验证）
- **渠道无差异**：无论从哪个渠道提问，Agent 的能力完全一致
- **同一个 STT 引擎**（豆包 BigModel ASR，`:8787`）
- **同一个 TTS 引擎**（豆包语音合成大模型，V1 API）
- **同一份审计日志**（`data/voice-audit/`，`channel` 字段区分来源）
- **会话隔离**：各渠道独立 session，上下文互不干扰

## 常见问题

**Gateway 启动失败 "port already in use"**

```bash
./stop.sh && ./start.sh
```

**OpenCami 提示 "Gateway unreachable"**

检查 Gateway 是否在运行，以及 `OPENCLAW_GATEWAY_TOKEN` 是否正确设置。

**语音识别无响应**

确认豆包 STT 代理在运行：`curl http://localhost:8787/health`

**移动端无法使用麦克风**

HTTP 协议下浏览器禁止麦克风访问。使用 Cloudflare Tunnel 提供的 HTTPS 链接即可解决（已集成，`./start.sh` 启动后自动输出）。

## 踩坑记录

详见 [`PITFALLS.md`](PITFALLS.md) — 按错误关键词索引，含可复制的代码示例，供 Agent 开发时快速查阅。
