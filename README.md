# Devkit

多 Agent 协同开发工具。通过 OpenClaw + Cursor CLI 实现：手机下指令 → AI 分身拆解任务 → Cursor 写代码 → 自动汇报结果。

## 架构

```
手机 (OpenCami)
  │
  ▼
OpenClaw Gateway (:18789)     ← AI 分身 "Kite"，全权代理，调度开发
  │
  ├── Cursor CLI               ← cursor agent -p "..." 执行开发
  │     └── Devkit 仓库         ← 本地文件系统
  │
  └── 豆包 STT 代理 (:8787)    ← 语音转文字（火山引擎 BigModel ASR）
        └── OpenCami (:3000)   ← Web UI，支持语音输入
```

全部本地运行，无数据外泄。

## 前置条件

| 依赖 | 用途 | 安装 |
|------|------|------|
| Node.js 20+ | OpenClaw / OpenCami | `brew install node` |
| Python 3.10+ | 豆包 STT 代理 | `brew install python3` |
| Cursor IDE | 代码执行 Agent | [cursor.com](https://www.cursor.com/) |
| Git | 版本管理 | `brew install git` |
| cloudflared | 移动端 HTTPS 隧道 | `brew install cloudflared`（可选） |

## 需要准备的账号和凭据

| 凭据 | 用途 | 获取方式 |
|------|------|----------|
| `DOUBAO_APPID` | 豆包语音识别 | [火山引擎控制台](https://console.volcengine.com/speech/service/8) → 语音技术 → 语音识别 |
| `DOUBAO_TOKEN` | 豆包语音识别 | 同上，创建应用获取 |
| `LLM_API_KEY` | LLM API | 任意 OpenAI 兼容服务商的 API Key |

## 从零安装

```bash
git clone <repo-url> Devkit && cd Devkit

# 1. 运行安装脚本（检查依赖、创建 .env、安装 OpenClaw/OpenCami）
./setup.sh

# 2. 编辑 .env，填入凭据
vim .env

# 3. 再次运行安装（加载 .env 并完成配置）
./setup.sh
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
./start.sh    # 启动所有服务（STT 代理 + Gateway + OpenCami）
./stop.sh     # 停止所有服务
```

启动后输出所有服务地址：

```
=== 所有服务已启动 ===

  豆包 STT:  http://localhost:8787/health
  Gateway:   ws://localhost:18789
  OpenCami:  http://localhost:3000
  局域网:    http://30.20.186.42:3000
```

## 使用方式

### 桌面端

浏览器打开 `http://localhost:3000`，直接在 OpenCami 中与 Kite 对话。

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

视觉理解测试（图片 + 视频，通过 Gemini）：

```bash
.venv/bin/python tests/mobile/test_vision.py
```

### 语音输入

OpenCami 设置中 STT Provider 选择 **OpenAI** 或 **Auto**，语音会通过豆包 BigModel ASR 识别。

### 语音合成 (TTS)

同一 DOUBAO_APPID/TOKEN 可同时用于 STT 和 TTS，支持两代模型：

**标准 TTS (V1 API)**：

| voice_type | 名称 |
|---|---|
| `BV700_V2_streaming` | 灿灿（活力女声） |
| `BV001_streaming` | 通用女声 |
| `BV002_streaming` | 通用男声 |

**SeedTTS 2.0 (V3 API)**  — 更自然的韵律，支持语音指令控制情感：

| speaker | 名称 |
|---|---|
| `zh_female_vv_uranus_bigtts` | vivi 2.0（通用，推荐） |
| `saturn_zh_female_cancan_tob` | 知性灿灿（角色扮演） |
| `saturn_zh_female_keainvsheng_tob` | 可爱女生（角色扮演） |
| `zh_male_ruyayichen_saturn_bigtts` | 儒雅逸辰（视频配音） |

> 2.0 音色需在火山引擎控制台开通"豆包语音合成模型2.0"并下单对应音色。

## 项目结构

```
Devkit/
├── .env.example              # 环境变量模板
├── setup.sh                  # 一键安装
├── start.sh                  # 一键启动
├── stop.sh                   # 一键停止
├── openclaw/                 # OpenClaw Agent 配置（版本管理）
│   ├── IDENTITY.md           #   人设：名字、性格
│   ├── SOUL.md               #   行为准则、自主权边界
│   ├── USER.md               #   用户信息
│   ├── AGENTS.md             #   工作流指令
│   ├── TOOLS.md              #   工具权限、本地环境
│   ├── HEARTBEAT.md          #   定期检查任务
│   └── sync.sh               #   同步到 ~/.openclaw/workspace/
├── services/
│   └── doubao-stt-proxy/     # 豆包语音识别代理
│       ├── server.py          #   FastAPI 服务 (Whisper API → 火山引擎 ASR)
│       ├── start.sh           #   独立启动脚本
│       ├── transcribe.sh      #   CLI 转写工具
│       └── requirements.txt
├── docker/                   # Docker 相关
│   ├── entrypoint.sh          #   容器启动脚本
│   └── verify.sh              #   全链路验证脚本
├── tests/mobile/             # 移动端自动化测试
│   ├── test_opencami.py       #   Playwright 视口测试
│   ├── test_voice_e2e.py      #   TTS→STT 语音闭环测试
│   └── test_vision.py         #   Gemini 图片/视频理解测试
├── phone.sh                  # 虚拟手机一键启动
├── .cursor/rules/            # Cursor Agent 行为规则
├── specs/                    # 需求 Spec 模板
├── .audit/                   # Cursor 调用审计日志
├── GOALS.md                  # 项目目标
├── STATUS.md                 # 当前状态
├── DECISIONS.md              # 决策记录
├── PITFALLS.md               # 踩坑手册（Agent 参考）
└── CAPABILITIES.md           # Agent 平台能力需求（选型参考）
```

## 配置说明

### OpenClaw 运行时配置

位于 `~/.openclaw/`，由 Gateway 直接使用：

| 文件 | 作用 |
|------|------|
| `openclaw.json` | 主配置：LLM provider、Channel、Gateway 端口、认证 |
| `workspace/*.md` | Agent 人设和工作指令（由 `openclaw/sync.sh` 同步） |

### 修改 Agent 配置

```bash
# 编辑项目内的配置文件
vim openclaw/SOUL.md

# 同步到 OpenClaw 运行时
./openclaw/sync.sh

# 重启 Gateway 使配置生效
openclaw gateway restart
```

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
```

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
