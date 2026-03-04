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

### 移动端

同一局域网下，手机浏览器打开 `http://<局域网IP>:3000`。
可添加到主屏幕（OpenCami 支持 PWA）。

> 注意：HTTP 下移动端浏览器无法使用麦克风。语音输入需要 HTTPS，可通过反向代理或 Tailscale 实现。

### 语音输入

OpenCami 设置中 STT Provider 选择 **OpenAI** 或 **Auto**，语音会通过豆包 BigModel ASR 识别。

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
├── .cursor/rules/            # Cursor Agent 行为规则
├── specs/                    # 需求 Spec 模板
├── .audit/                   # Cursor 调用审计日志
├── GOALS.md                  # 项目目标
├── STATUS.md                 # 当前状态
└── DECISIONS.md              # 决策记录
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

HTTP 协议下浏览器禁止麦克风访问。解决方案：
1. 通过反向代理加 HTTPS 证书
2. 使用 Tailscale + `tailscale serve` 提供 HTTPS
