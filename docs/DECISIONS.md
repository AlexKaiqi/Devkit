# 决策记录

| 日期 | 决策 | 决策者 | 原因 |
|------|------|--------|------|
| 2026-03-05 | 主动通知渠道选 Telegram Bot | 用户 | 即时推送、支持 Markdown、curl 可调用、开放协议 |
| 2026-03-05 | 记忆系统用文件存储（MEMORY.md + memory/），persona/ 目录管理 | 希露菲 | git 版本管理 + 跨会话持久 + 可在新机器恢复 |
| 2026-03-05 | 定时巡检用 macOS launchd，不用 cron | 希露菲 | macOS 原生、支持 RunAtLoad、日志管理更好 |
| 2026-03-05 | 结构化数据用 YAML 文件（data/），不用 SQLite | 希露菲 | git 友好、人类可读、AI 可直接编辑、量级小不需要数据库 |
| 2026-03-05 | 工具选型原则：开源优先 + CLI 优先 + 闭源仅限不可替代 | 用户 | AI agent 擅长 CLI 操作，开源可控性更高 |
| 2026-03-05 | 搜索引擎用 SearXNG 自托管（Docker），不用商业搜索 API | 希露菲 | 开源、无 API Key、支持 JSON 输出、可聚合多引擎 |
| 2026-03-05 | 邮件 CLI 选 himalaya，不用 mutt/neomutt | 希露菲 | Rust 编写、现代设计、TOML 配置简洁、IMAP/SMTP 直连 |
| 2026-03-05 | macOS 桌面自动化用 peekaboo，不用 AppleScript/Hammerspoon | 希露菲 | 专为 AI agent 设计，支持 screen capture + UI map + 模拟操作 |
| 2026-03-05 | .venv 从 Python 3.9.6 升级到 3.12 | 希露菲 | 多个 pip 包（paperscout、papis 等）要求 ≥3.10 |
| 2026-03-05 | SearXNG 持久化集成到 start.sh/stop.sh | 希露菲 | 随项目启停，Docker restart unless-stopped 保证崩溃恢复 |
| 2026-03-04 | AI 分身更名 Kite → 希露菲，人设为混合风（温柔+干练） | 用户 | 用户偏好女性二次元角色，希露菲（无职转生）气质契合 |
| 2026-03-04 | LLM 层去 Gemini 绑定，改为模型无关 | 用户 | AI 管家不应绑定特定模型，底层已支持 OpenAI 兼容接口切换 |
| 2026-03-05 | 语音网页客户端命名「风铃」(FengLing) | 希露菲 | 风=Sylph(希露菲)，铃=声音，合为「风的声音」 |
| 2026-03-05 | 对话渠道双轨：风铃(Web) + Telegram Bot | 用户 | 桌面用风铃语音交互，移动端用 Telegram 随时对话 |
| 2026-03-05 | TTS 引擎选豆包语音合成 V1 API，不用 Edge TTS | 希露菲 | 与 STT 共用火山引擎凭据，质量优于 Edge TTS |
| 2026-03-05 | TTS 升级至豆包语音合成大模型（`*_bigtts` / `*_tob` 音色），默认「甜美小源」 | 用户 | 大模型音色音质更自然、情感更丰富，同 V1 API + `volcano_tts` cluster 兼容 |
| 2026-03-05 | 回复内容分区：文本(朗读) + 附件(代码块，仅展示) | 用户 | 代码被朗读体验差，分离后对话简洁、附件可复制 |
| 2026-03-05 | 视觉理解用独立 VISION_MODEL，视频用 ffmpeg 抽帧而非直传 | 希露菲 | 视觉模型可独立选型（如用更快的 flash），抽帧兼容所有 OpenAI 兼容 API |
| 2026-03-05 | LLM 默认模型从 gemini-3.1-pro-preview 切换至 gemini-2.5-flash | 用户 | Pro 模型 first token ~3.8s 太慢，flash 快 42%（~2.2s），日常对话不需要 pro 级推理 |
| 2026-03-05 | 条件 TTS：语音输入→语音回复，文字输入→纯文字 | 用户 | 文字交互不需要语音，跳过 TTS 省 0.5-1s 延迟，打字场景更干净 |
| 2026-03-05 | 风铃新增文字输入框（双模式交互） | 希露菲 | 用户有时用键盘更方便，不是每次都需要语音 |
| 2026-03-05 | 风铃/Telegram 接入 Agent 后端（原 OpenClaw Gateway，后迁移至 LocalAgent）| 用户 | Agent 人设/工具/记忆应统一管理，渠道只是 I/O 层 |
| 2026-03-05 | Gateway 客户端用 Ed25519 设备认证 + v3 签名协议 | 希露菲 | 与 Gateway 协议规范一致，本地连接自动批准，无需手动配对 |
| 2026-03-05 | Gateway 事件去重：仅处理 agent 事件，忽略 chat delta 事件 | 希露菲 | Gateway 同时发 agent 和 chat 两种事件含相同文本，取 agent 事件做流式，chat 仅作完成信号 fallback |
| 2026-03-05 | 能力状态用四级标记（✓已验证/◎已就绪/△部分就绪/✗未实现）| 希露菲 | 区分"工具安装了"和"端到端跑通了"，AI 原生项目要如实描述能力边界 |
| 2026-03-05 | A 股数据用 akshare-one-mcp（MCP），通过 mcporter 集成 | 用户+希露菲 | 免费（AKShare 库）、纯 Python、覆盖沪深 A 股、免 API Key、uvx 一键运行 |
| 2026-03-05 | 禁用 Gateway 内建 Telegram channel，延时任务改为事件驱动 Timer API | 用户+希露菲 | Gateway Telegram 与自定义 Bot 的 getUpdates 冲突(409)；cron --announce 因 operator WebSocket 无法解析用户 chat ID。新建 EventBus(asyncio pub/sub) + Timer HTTP API(:8789)，定时器绑定 session_key，到期自动投递到 Telegram。标准 asyncio 原语，无第三方依赖 |
| 2026-03-06 | 自建 LocalAgent 替代 OpenClaw Gateway，openai SDK 直连 LLM | 用户 | OpenClaw 黑盒无法优化，自建 ~300 行 Python 即可实现 agent runtime + tool calling，性能可控 |
| 2026-03-06 | openclaw/ 目录重命名为 persona/，清除 OpenClaw 依赖 | 用户+希露菲 | 不再依赖 OpenClaw，目录名应反映实际用途（Agent 人设配置） |
<!-- 每条决策一行，决策者标注「用户」或「希露菲」 -->
