# 工具选型

CAPABILITIES.md 描述"需要什么能力"，本文档记录"用什么工具实现"。

**选型原则：**

1. 开源优先（闭源仅在不可替代时标注）
2. CLI 工具优先（AI Agent 对命令行最擅长）
3. 有 MCP Server 的优先（LLM 可直接调用）

## 自动化与 App 操作

| 能力 | CLI 工具 | MCP Server | 说明 |
|------|----------|------------|------|
| 5.4a 手机操作 | `adb` + UIAutomator | — | 已验证；升级路径 UI-TARS 模型 |
| 5.4b 桌面操作 | `peekaboo` | `@steipete/peekaboo` | MIT, Swift 原生, Homebrew 安装 |
| 5.4c Web 操作 | `playwright` CLI | `playwright-mcp` | 支持无头浏览器 |

## 外部集成

| 能力 | CLI 工具 | MCP Server | 说明 |
|------|----------|------------|------|
| 6.1 代码托管 | `gh` (GitHub CLI) | `github-mcp` | GitHub 官方 CLI，MIT |
| 6.2 团队协作 | — | 飞书插件 | 闭源但国内必需 |
| 6.3 邮件 | `himalaya` | `gmail-mcp` | Rust, IMAP/SMTP, JSON 输出 |
| 6.4 日历 | `khal` + `vdirsyncer` | `google-calendar-mcp` | CalDAV 标准 |
| 6.5 搜索引擎 | `curl` → SearXNG API | `searxng-mcp` | 自托管 Docker，零成本 |
| 6.6 IoT 中枢 | `hass-cli` | `ha-mcp` (官方) | HA 2025.9 内建 MCP |
| 6.7 即时通讯 Bot | `curl` → Telegram Bot API | — | 开放协议 |
| 6.8 天气/位置 | `curl wttr.in` | — | 零配置 |
| 6.9 云存储 | `rclone` | — | 70+ 后端 |
| 6.10 通用 API | — | MCP 协议 | 统一插件扩展 |

## 科研

| 能力 | CLI 工具 | MCP Server | 说明 |
|------|----------|------------|------|
| 7.1 文献检索 | `paperscout` | — | arXiv + S2 + DBLP + ACL |
| 7.2 论文阅读 | `marker` | — | PDF → Markdown |
| 7.3 文献管理 | `papis` | — | GPL-3, YAML 存储, BibTeX |
| 7.4 数据分析 | `pandas`/`numpy`/`scipy`/`matplotlib` | — | .venv 中已可用 |
| 7.5 实验管理 | `mlflow` | — | 开源实验追踪 |
| 7.6 学术写作 | `pandoc` + `languagetool` | — | 万能文档转换 + 语法检查 |

## 智能家居

| 能力 | CLI 工具 | MCP Server | 说明 |
|------|----------|------------|------|
| 8.1–8.5 全部 | `hass-cli` | `ha-mcp` (官方) | Home Assistant 是唯一入口 |

## 人际管理

| 能力 | CLI 工具 | MCP Server | 说明 |
|------|----------|------------|------|
| 9.1 通讯录 | `khard` | — | vCard/CardDAV 标准 |
| 9.2–9.5 | 复用邮件 + 日历 | — | LLM 润色 + himalaya + khal |

## 安装速查

> `setup.sh` 已自动处理以下安装。手动初始化时参考此清单。

```bash
# Homebrew CLI 工具
brew install gh peekaboo himalaya rclone pandoc

# Python 虚拟环境 (.venv, Python 3.12)
pip install -r requirements.txt
pip install playwright && playwright install chromium

# SearXNG (Docker)
# start.sh 自动管理
```

## 手动配置

部分工具需要凭据，无法自动化：

| 工具 | 配置文件 | 说明 |
|------|----------|------|
| himalaya | `~/.config/himalaya/config.toml` | Gmail App Password |
| vdirsyncer | `~/.config/vdirsyncer/config` | Google Calendar CalDAV |
| .env | `.env` | HASS_TOKEN、TELEGRAM_BOT_TOKEN 等 |
