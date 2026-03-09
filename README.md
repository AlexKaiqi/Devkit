# Devkit — AI 原生个人分身平台

> 语音或文字下达指令 → AI 分身自主拆解、执行、汇报。全部本地运行，无数据外泄。

## Quick Start

```bash
git clone <repo-url> Devkit && cd Devkit
./setup.sh    # 检查依赖、创建 .env、安装工具链
vim .env      # 填入凭据
./start.sh    # 启动所有服务
```

或用 Cursor 打开项目，AI 会自动引导完成全部初始化。

## 文档索引

| 文档 | 内容 |
|------|------|
| [产品定义](docs/PRODUCT.md) | 是什么、能做什么、交互体验 |
| [项目目标](docs/GOALS.md) | 愿景与迭代方向 |
| [能力清单](docs/CAPABILITIES.md) | 能力总览 + 技能矩阵 |
| [系统架构](docs/ARCHITECTURE.md) | 服务拓扑与通信协议 |
| [决策记录](docs/DECISIONS.md) | 为什么这么选 |
| [工具选型](docs/TOOL_CHOICES.md) | 用什么工具实现 |
| [踩坑手册](docs/PITFALLS.md) | 常见问题速查 |
| [当前进度](STATUS.md) | 最新状态 |

## 服务与实现

| 文档 | 内容 |
|------|------|
| [服务总览](services/SERVICE_CATALOG.md) | 能力 → 服务映射 |
| [Agent 人格](persona/) | 人设 / 行为准则 / 记忆 |

## 使用方式

| 渠道 | 地址 | 说明 |
|------|------|------|
| 风铃 | `http://localhost:3001` | 语音+文字，日常推荐 |
| Telegram | 搜索你的 Bot | 随时随地 |
| OpenCami | `http://localhost:3000` | 全功能界面 |

## 前置条件

| 依赖 | 安装 |
|------|------|
| Node.js 20+ | `brew install node` |
| Python 3.12+ | `brew install python@3.12` |
| Cursor IDE | [cursor.com](https://www.cursor.com/) |
| Docker | [Docker Desktop](https://www.docker.com/) |

## 需要准备的凭据

| 凭据 | 用途 | 获取 |
|------|------|------|
| DOUBAO_APPID / TOKEN | 语音识别+合成 | [火山引擎控制台](https://console.volcengine.com/speech/service/8) |
| LLM API Key | LLM 推理 | 任意 OpenAI 兼容服务商 |
| TELEGRAM_BOT_TOKEN | Telegram Bot（可选） | [@BotFather](https://t.me/BotFather) |
