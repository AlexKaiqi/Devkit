# 能力总览

希露菲作为用户的数字分身，具备以下能力域。每个能力域的详细规格见 `specs/` 目录。

## 能力索引

| 能力域 | Spec | 状态 | 实现方式 |
|--------|------|------|----------|
| 开发代理 | [development-agent](specs/development-agent.md) | ✓ 已验证 | Cursor CLI + LocalAgent |
| 语音交互 | [voice-interaction](specs/voice-interaction.md) | ✓ 已验证 | 风铃 + Telegram + 豆包 STT/TTS |
| 知识与科研 | [knowledge-research](specs/knowledge-research.md) | ◎ 部分就绪 | paperscout + papis + pandas |
| 智能家居 | [smart-home](specs/smart-home.md) | △ 待配置 | Home Assistant + hass-cli |
| 人际管理 | [social-management](specs/social-management.md) | △ 部分就绪 | khard + YAML data/ |
| 股票分析 | [stock-analysis](specs/stock-analysis.md) | ✓ 已验证 | akshare-one-mcp (MCP) |
| 事件驱动系统 | [event-system](specs/event-system.md) | ✓ 已验证 | EventBus (asyncio) + Timer API |

## 技能矩阵

| # | 技能 | 优先级 | 当前状态 |
|---|---|---|---|
| **开发** | | | |
| 1.1 | 任务拆解与委派 | 必须 | ✓ 用户下指令 → Agent 拆解 → cursor agent 执行 |
| 1.2 | 代码质量验证 | 必须 | ✓ Agent 可读文件、理解代码结构、分析函数签名 |
| 1.3 | 版本控制 | 必须 | ✓ git status/diff/log 端到端验证 |
| 1.4 | 技术调研 | 重要 | △ SearXNG 已部署但网络不通 |
| 1.5 | 错误诊断与恢复 | 重要 | △ 踩坑手册已有，自动诊断待完善 |
| **项目管理** | | | |
| 2.1 | 任务管理 | 重要 | △ 纯文件方式，无结构化队列 |
| 2.2 | 进度汇报 | 必须 | ✓ Agent 指令中已定义格式 |
| 2.3 | 决策记录 | 重要 | ✓ DECISIONS.md 已建立 |
| 2.4 | 文档维护 | 重要 | ✓ 多份文档已建立 |
| **沟通** | | | |
| 3.1 | 多渠道对话 | 必须 | ✓ 三渠道统一 Gateway 验证 |
| 3.2 | 语音交互 | 重要 | ✓ 条件TTS, 豆包STT+TTS大模型, 25+音色 |
| 3.3 | 主动通知 | 重要 | ✓ Telegram Bot + notify.sh |
| 3.4 | 视觉理解 | 一般 | ✓ 风铃 + Telegram, 视频自动抽帧 |
| **知识管理** | | | |
| 4.1 | 经验积累 | 重要 | ✓ PITFALLS.md + MEMORY.md + memory/ |
| 4.2 | 跨会话记忆 | 重要 | ✓ MEMORY.md + memory/ 日志 |
| 4.3 | 知识检索 | 一般 | △ 文件搜索可用，语义搜索待配置 |
| **自动化** | | | |
| 5.1 | 服务管理 | 重要 | ✓ start.sh/stop.sh/check.sh |
| 5.2 | 定时巡检 | 重要 | △ heartbeat.sh 已就绪，launchd 待安装 |
| 5.3 | 日程与提醒 | 重要 | △ khal 已安装，CalDAV 待配置 |
| 5.5 | 事件驱动定时器 | 必须 | ✓ EventBus + Timer API(:8789)，[spec](specs/event-system.md) |
| 5.4a | 手机操作 | 重要 | ✓ UIAutomator + 视觉模型 + ADB |
| 5.4b | 桌面操作 | 重要 | ◎ peekaboo 已安装 |
| 5.4c | Web 操作 | 重要 | ◎ playwright 已就绪 |
| **外部集成** | | | |
| 6.1 | 代码托管 | 一般 | ✓ gh CLI 已认证 |
| 6.3 | 邮件系统 | 重要 | ✓ himalaya 配通 Gmail |
| 6.4 | 日历服务 | 重要 | △ khal 已安装，CalDAV 待配置 |
| 6.5 | 搜索引擎 | 必须 | △ SearXNG Docker 已部署，网络待修复 |
| 6.6 | IoT 中枢 | 重要 | △ hass-cli 已安装，HA 待配置 |
| 6.7 | 即时通讯 Bot | 一般 | ✓ Telegram Bot 完整实现 |
| 6.11 | A 股数据 | 重要 | ✓ akshare-one-mcp 端到端验证 |
| **科研** | | | |
| 7.1 | 文献检索 | 重要 | ◎ paperscout 已安装 |
| 7.2 | 论文阅读 | 重要 | △ marker PDF 转换可用 |
| 7.4 | 数据分析 | 重要 | ◎ pandas/numpy/scipy/matplotlib |
| **智能家居** | | | |
| 8.1 | 设备控制 | 必须 | △ hass-cli 已安装，HA 待配置 |
| **人际管理** | | | |
| 9.1 | 通讯录 | 重要 | △ khard + data/contacts.yml |
| 9.4 | 人情往来 | 一般 | △ data/gifts.yml 已建立 |

### 状态说明

- ✓ 已验证 — 通过 LocalAgent 端到端确认可用
- ◎ 已就绪 — 工具已安装，待端到端验证
- △ 部分就绪 — 需补充配置或依赖
- ✗ 尚未实现

### Agent 能力边界

所有渠道统一接入 LocalAgent，Agent 能力不受渠道限制。

**已验证可用：** 基础对话、文件读写、Shell 命令、代码理解、多步推理、Git 操作、邮件读取、Docker 管理、会话管理、MCP 工具调用

**已知限制：** 工具调用不可见（前端无法展示执行中状态）、Azure 内容过滤（偶发）、SearXNG 网络不通（Docker HTTPS 出站异常）

## 底层平台要求

| 基础能力 | 支撑的技能 |
|---|---|
| 本地命令执行 | 1.1 任务委派、1.3 版本控制、5.1 服务管理 |
| 文件系统读写 | 1.2 质量验证、2.3 决策记录、4.1 经验积累 |
| LLM 推理（含工具调用） | 所有技能的基础 |
| 语音识别 (STT) + 语音合成 (TTS) | 3.2 语音交互 |
| 定时调度（事件驱动） | 3.3 主动通知、5.2 定时巡检、5.5 定时器 — [event-system spec](specs/event-system.md) |
| 图片/视频理解 | 3.4 视觉理解 |
| MCP 插件机制 | 6.x 外部集成 |

工具选型详见 [TOOL_CHOICES.md](TOOL_CHOICES.md)。
