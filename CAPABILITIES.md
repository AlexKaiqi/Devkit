# Agent 平台能力需求

描述 Kite（数字分身）正常运作所需的平台能力。
与具体产品无关（当前选型 OpenClaw，可替换），关注的是**能力本身**。

---

## 1. 本地命令执行

在用户本机运行 shell 命令，拥有项目目录的读写权限。

**用途：**
- 调用 `cursor agent -p "..."` 派发开发任务
- 执行 `git` 操作（add / commit / push / diff / log）
- 启停本地服务（STT 代理、OpenCami、Tunnel 等）
- 运行测试脚本、构建命令
- 查看文件和日志

**约束：**
- 限定在项目目录内操作，不能访问系统敏感路径
- 禁止 `rm -rf`、`sudo`、`chmod 777` 等破坏性命令
- 代码修改由 Cursor Agent 完成，Kite 本身不直接写代码

---

## 2. 文件系统读写

直接读取和写入工作区内的文件。

**用途：**
- 维护项目文档（`STATUS.md`、`GOALS.md`、`DECISIONS.md`）
- 写入每日日志（`memory/YYYY-MM-DD.md`）和长期记忆（`MEMORY.md`）
- 记录 Cursor 调用审计日志（`.audit/`）
- 读取配置文件（`.env`、`openclaw.json`）

---

## 3. 用户通信（双向消息）

与用户进行实时文字/语音对话，支持移动端。

**用途：**
- 接收用户的目标、需求、反馈
- 汇报开发进展、决策确认
- 日常沟通和问题讨论

**要求：**
- 支持移动端访问（手机浏览器 / PWA）
- 支持跨网络访问（不依赖局域网）
- 支持 HTTPS（移动端麦克风需要安全上下文）
- 支持 Markdown 渲染（代码块、表格、列表等）
- 支持图片展示

---

## 4. 语音输入（STT）

将用户语音转为文字，作为消息输入。

**用途：**
- 用户在移动端用语音快速下达指令
- 解放双手，适合碎片化沟通场景

**当前实现：**
- 豆包 BigModel ASR，通过 STT Proxy 包装为 Whisper 兼容 API
- OpenCami 设置中选择 OpenAI provider，指向本地 STT Proxy

**要求：**
- 中文识别准确率高
- 支持流式识别（边说边转）为佳
- 延迟可接受（< 3s）

---

## 5. 语音输出（TTS）

将 Agent 回复转为语音播放给用户。

**用途：**
- 用户在不方便看屏幕时听取汇报
- 更自然的交互体验

**当前实现：**
- 标准 TTS (V1 API)：BV700_V2_streaming 等标准音色
- SeedTTS 2.0 (V3 API)：zh_female_vv_uranus_bigtts 等大模型音色
- 详见 `PITFALLS.md` 中的协议速查

**要求：**
- 中文发音自然
- 支持多音色可选
- 能与通信渠道集成（在对话界面直接播放）

---

## 6. 定时任务 / 心跳检查

定期执行检查逻辑，无需用户触发。

**用途：**
- 检查 Cursor Agent 是否仍在运行（超 30 分钟提醒）
- 检查项目是否有未提交的变更
- 检查待确认决策项
- 检查 STATUS.md 是否过期

**当前定义：** 见 `openclaw/HEARTBEAT.md`

---

## 7. 持久化记忆

跨会话保持上下文和经验。

**用途：**
- 记住用户偏好和工作风格
- 记住项目历史决策和原因
- 记住踩过的坑，避免重复犯错
- 在新会话中快速恢复上下文

**当前实现：**
- `memory/` 目录存储每日日志
- `MEMORY.md` 存储长期经验
- `.audit/` 存储 Cursor 调用记录
- `PITFALLS.md` 存储踩坑经验

**要求：**
- 支持文件形式的结构化存储
- Agent 能在会话开始时自动加载最近记忆
- 支持语义搜索（按关键词检索历史记忆）为佳

---

## 8. LLM 推理

Agent 的"大脑"，负责理解意图、拆解任务、生成回复。

**当前实现：**
- 通过 OpenAI 兼容接口调用（`LLM_BASE_URL` + `LLM_API_KEY`）
- 当前模型：见 `.env` 中 `LLM_MODEL`

**要求：**
- 中文理解和生成能力强
- 支持长上下文（项目文档、代码片段可能很长）
- 支持工具调用（function calling / tool use）
- 响应速度可接受（< 10s 首 token）

---

## 9. 多设备接入

同一个 Agent 实例可从多端访问。

**用途：**
- 电脑上开发时在 IDE 旁查看对话
- 外出时用手机继续沟通
- 不同设备间消息同步

**要求：**
- Web 端（桌面浏览器 + 移动浏览器）
- 消息历史跨设备同步
- 不需要为每个设备单独配置

---

## 10. 安全与隔离

保护用户数据和系统安全。

**要求：**
- 所有数据在本地处理，不上传到第三方（除 LLM API 调用）
- 命令执行有权限边界
- 外部通信（发邮件、发帖）需用户确认
- 凭据通过 `.env` 管理，不硬编码
- 支持 HTTPS 访问（Cloudflare Tunnel 或自有证书）

---

## 11. 任务管理 / Todo

管理多个并行任务的生命周期：创建、排优先级、跟踪进度、标记完成。

**用途：**
- 用户一次性交代多个目标，Agent 按优先级逐个推进
- 长时间运行的 Cursor 任务需要跟踪状态（排队中 / 执行中 / 已完成 / 失败）
- 任务间存在依赖关系时，自动按顺序编排
- 用户随时查看"当前有哪些事在做 / 排队中"

**要求：**
- 支持创建、更新状态、设置优先级
- 支持任务间依赖关系（A 完成后再启动 B）
- 持久化存储（重启后不丢失）
- 用户可通过对话查询任务列表

---

## 12. 主动推送通知

Agent 在特定事件发生时主动通知用户，而非被动等待提问。

**用途：**
- Cursor 任务完成或失败时立即通知
- 定时心跳检查发现异常时告警
- 接近 deadline 时提醒
- Git 仓库有冲突或 CI 失败时通知

**要求：**
- 能向用户的通信渠道主动发送消息
- 支持移动端推送（用户不在电脑前也能收到）
- 可配置通知级别（紧急 / 普通 / 低优先级）
- 避免打扰：工作时间外降低通知频率

---

## 13. 网络搜索 / 信息检索

在互联网上搜索信息，查阅文档和 API 用法。

**用途：**
- 遇到未知报错时搜索解决方案
- 查阅第三方库/API 的最新文档
- 了解技术选型的社区评价和最佳实践
- 替用户调研技术方案

**要求：**
- 搜索 + 读取网页内容
- 能提取网页中的关键信息（而非返回整页 HTML）
- 搜索结果有缓存，避免重复查询

---

## 14. 多任务编排

同时管理和执行多个开发任务，协调任务间的依赖和冲突。

**用途：**
- 同时给多个 Cursor Agent 派发无依赖的任务
- 一个任务失败后决定是否继续后续任务
- 监控多个后台进程的状态
- 管理子 Agent 的生命周期

**要求：**
- 支持并发派发任务（当前 maxConcurrent: 4）
- 支持后台进程管理（启动、轮询、终止）
- 子任务完成后自动汇总结果
- 失败时支持重试或降级策略

---

## 15. 视觉理解

理解用户发送的图片内容（截图、设计稿、报错截图等）。

**用途：**
- 用户用手机拍屏幕上的报错信息
- 查看 UI 截图判断样式是否符合预期
- 理解设计稿中的布局要求
- 查看图表/流程图

**要求：**
- 支持接收图片消息
- 使用多模态模型分析图片内容
- 能结合图片和文字上下文给出回复

---

## 16. 外部服务集成

调用第三方平台的 API，扩展 Agent 的能力边界。

**用途：**
- GitHub：创建 Issue、查看 PR 状态、触发 CI
- 日历/提醒：创建日程事件、设置提醒
- 飞书/Slack：跨平台消息同步
- 其他 SaaS API：按需集成

**要求：**
- 插件化架构，可按需添加新集成
- OAuth / API Key 认证管理
- 调用外部 API 前需用户授权或配置

---

## 17. 日程与时间感知

理解时间上下文，支持基于时间的决策和提醒。

**用途：**
- 知道当前时间、用户时区、是否在工作时间
- "明天上午提醒我 review 那个 PR"
- 判断某个任务已经拖了多久
- 结合日历信息安排工作节奏

**要求：**
- 能获取当前时间和用户时区
- 支持延时触发（"N 小时后提醒我"）
- 能与任务管理联动（deadline 提醒）

---

## 能力矩阵

| # | 能力 | 优先级 | 当前状态 | 开启方式 |
|---|---|---|---|---|
| 1 | 本地命令执行 | 必须 | ✗ profile=messaging 不含 exec | 切换 profile 或 allow group:runtime |
| 2 | 文件系统读写 | 必须 | ✗ profile=messaging 不含 read/write | 切换 profile 或 allow group:fs |
| 3 | 用户通信 | 必须 | ✓ message 工具 + OpenCami | — |
| 4 | 语音输入 (STT) | 重要 | ✓ 豆包 ASR + STT Proxy | — |
| 5 | 语音输出 (TTS) | 重要 | ✓ 豆包 TTS V1 + V3（已验证） | — |
| 6 | 定时任务 | 重要 | ✗ cron 在 group:automation，未启用 | allow group:automation |
| 7 | 持久化记忆 | 重要 | △ 文件存储可用；语义搜索未配置 | allow group:memory + 配置 memory |
| 8 | LLM 推理 | 必须 | ✓ OpenAI 兼容接口 | — |
| 9 | 多设备接入 | 一般 | ✓ OpenCami Web + Tunnel | — |
| 10 | 安全与隔离 | 必须 | ✓ 本地运行 + .env + 权限边界 | — |
| 11 | 任务管理 / Todo | 重要 | △ 纯文件方式；无结构化工具 | 需自建或用 sessions_spawn 编排 |
| 12 | 主动推送通知 | 重要 | ✗ cron + message 可实现，但未启用 | allow group:automation + 配置 cron job |
| 13 | 网络搜索 | 重要 | ✗ web_search/web_fetch 存在但未启用 | allow group:web + 配置 BRAVE_API_KEY |
| 14 | 多任务编排 | 重要 | △ sessions_spawn 可用；exec 未启用 | allow group:runtime + group:sessions |
| 15 | 视觉理解 | 一般 | ✗ image 工具存在但未配置 imageModel | 配置 agents.defaults.imageModel |
| 16 | 外部服务集成 | 一般 | △ 飞书插件已安装；GitHub 等未接入 | 安装对应插件 |
| 17 | 日程与时间感知 | 一般 | ✗ 无日历集成；cron 未启用 | allow group:automation + 外部日历 API |

### 状态说明

- ✓ 已就绪，可直接使用
- △ 部分可用，需补充配置
- ✗ 平台支持但当前未启用

---

## 关键发现：tool profile 是最大瓶颈

当前配置 `tools.profile: "messaging"`，仅包含：
- `message`（消息发送）
- `sessions_list` / `sessions_history` / `sessions_send` / `session_status`

这意味着 Agent **无法执行命令、读写文件、搜索网络、管理定时任务**。
大部分能力在 OpenClaw 平台层面已支持，但被 profile 限制了。

### 建议的 profile 调整

```json5
{
  "tools": {
    "profile": "full",
    // 或精确控制：
    // "allow": [
    //   "group:messaging",
    //   "group:fs",
    //   "group:runtime",
    //   "group:sessions",
    //   "group:automation",
    //   "group:web",
    //   "group:memory",
    //   "image"
    // ],
    "deny": ["browser", "canvas"],
    "web": {
      "search": { "enabled": true },
      "fetch": { "enabled": true }
    }
  }
}
```

### 还需要的外部配置

| 配置项 | 用途 | 来源 |
|---|---|---|
| `BRAVE_API_KEY` | 网络搜索 | [Brave Search API](https://brave.com/search/api/) |
| `agents.defaults.imageModel` | 视觉理解 | 同 LLM provider 的多模态模型 |
| `cron` job 定义 | 心跳/定时通知 | `openclaw cron add` |
| GitHub 插件 | GitHub 集成 | OpenClaw skills / 自定义插件 |
