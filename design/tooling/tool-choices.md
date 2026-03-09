# 工具选型

`CAPABILITIES.md` 描述"需要什么能力"，本文档回答更具体的问题：

1. 当前产品运行**真正依赖**哪些工具
2. 哪些是按需接入的能力工具
3. 哪些只是开发 / 测试 / 自动化工具，不属于产品核心依赖

## 选型原则

1. 开源优先，闭源仅在不可替代时使用
2. CLI / HTTP / MCP 这类可审计接口优先
3. 优先选能被本地 runtime 稳定调用的工具，而不是只适合人工点击的工具
4. 不把开发测试工具误写成产品运行必需依赖

## 当前项目到底要什么

### A. 产品运行必需

这些工具或服务是当前产品主路径运行真正依赖的，没有它们，核心体验会直接缺失。

| 作用 | 当前选择 | 类型 | 说明 |
|------|----------|------|------|
| LLM 推理 | OpenAI 兼容接口 | API | 由 `LocalAgent` 调用，模型供应商可替换 |
| 语音识别 / 合成 | 豆包 STT/TTS | API | 当前语音主路径依赖 |
| 搜索 | SearXNG | Docker 服务 | 当前通用检索入口 |
| 定时与异步 | `Timer API` + `EventBus` | 本地服务 | 当前任务异步推进依赖 |
| 通用工具执行 | `exec` / `read_file` / `write_file` / `search` | 本地 runtime | 当前 Agent 基础工具面 |

### B. 按需接入的能力工具

这些工具不是产品运行的硬依赖，但当某个专业能力启用时，它们是优先接入方式。

| 能力域 | 优先接入 | 类型 | 说明 |
|--------|----------|------|------|
| 代码托管 | `gh` | CLI | GitHub 相关操作优先入口 |
| 邮件 | `himalaya` | CLI | IMAP/SMTP，适合 Agent 调用 |
| 日历 | `khal` + `vdirsyncer` | CLI | 适合日历读写与同步 |
| 智能家居 | `hass-cli` / `ha-mcp` | CLI / MCP | Home Assistant 统一入口 |
| 股票数据 | `akshare-one-mcp` + `mcporter` | MCP | 当前已验证的专业能力接入 |
| 文献检索 | `paperscout` | CLI | 科研检索入口 |
| 论文阅读 | `marker` | CLI | PDF → Markdown |
| 文献管理 | `papis` | CLI | 研究资料管理 |
| 通讯录 | `khard` | CLI | vCard / CardDAV 方向 |
| 外部通知 / 轻量触达 | Telegram Bot API | HTTP API | 可选外部集成，不作为核心客户端依赖 |
| 云存储 | `rclone` | CLI | 外部文件系统接入 |
| 通用扩展 | MCP 协议 | 协议 | 新专业能力的优先扩展方式 |

### C. 开发 / 测试 / 自动化工具

这些工具很有价值，但不应被误认为是"当前产品必须安装才算能跑"。

| 工具 | 角色 | 是否属于产品核心依赖 | 说明 |
|------|------|----------------------|------|
| `adb` + `UIAutomator` | Android 设备操作、端到端自动化、移动端实验 | 否 | 更像手机操作能力的实现后端，也常用于项目测试，不是当前主产品路径必需 |
| `peekaboo` | 桌面 GUI 自动化 | 否 | 属于按需启用的桌面操作能力 |
| `playwright` | Web 自动化 / 浏览器测试 | 否 | 既可用于能力扩展，也可用于开发测试 |

### `adb + UIAutomator` 到底是什么

你的判断基本对：**当前语境下，`adb + UIAutomator` 更接近项目的自动化 / 测试 / 手机操作后端，而不是产品主路径依赖。**

只有在你明确要把"手机 App 操作"做成产品能力时，它才会上升为某个专业能力的核心实现工具。否则它更应该被放在：

- 开发验证
- 自动化实验
- 手机操作能力原型

而不是和 `LLM`、`SearXNG` 这些当前运行必需依赖并列。

## 建议的接入优先级

### 第一层：必须长期维护

- OpenAI 兼容 LLM 接口
- 豆包 STT/TTS
- SearXNG
- `Timer API` + `EventBus`
- `exec` / `read_file` / `write_file` / `search`

### 第二层：按专业能力逐步接入

- `gh`
- `himalaya`
- `khal` + `vdirsyncer`
- `hass-cli`
- `akshare-one-mcp`
- `Telegram Bot API`
- `paperscout` / `marker` / `papis`
- `khard`
- `rclone`

### 第三层：开发 / 测试 / 自动化

- `adb` + `UIAutomator`
- `peekaboo`
- `playwright`

## 安装速查

> `setup.sh` 主要处理第一层和部分第二层工具。第三层工具不应默认视为产品硬依赖。

```bash
# 常用 Homebrew CLI 工具
brew install gh himalaya rclone pandoc

# Python 虚拟环境 (.venv, Python 3.12)
pip install -r requirements.txt

# Playwright（按需：Web 自动化 / 浏览器测试）
pip install playwright && playwright install chromium

# SearXNG（Docker）
# start.sh 自动管理
```

## 手动配置

部分按需能力需要凭据或本地配置：

| 工具 / 能力 | 配置文件 | 说明 |
|-------------|----------|------|
| `himalaya` | `~/.config/himalaya/config.toml` | Gmail App Password |
| `vdirsyncer` | `~/.config/vdirsyncer/config` | Google Calendar CalDAV |
| Home Assistant / Telegram / LLM | `.env` | `HASS_TOKEN`、`TELEGRAM_BOT_TOKEN`、`LLM_*` 等 |
