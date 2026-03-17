# TOOLS.md - 本地环境

## 开发环境

- 机器: macOS (Apple Silicon)
- 主项目: `/Users/kaiqidong/Devkit`
- Python 虚拟环境: 项目内 `.venv/`（Python 3.12），所有 Python 命令通过 `.venv` 执行

## 可用工具（按 Skill 分组）

工具按功能分为 Skill 包，agent 根据对话内容按需激活相关 Skill。

---

### Skill: system（始终激活）

基础系统能力，无需关键词匹配，每次对话都可用。

- `exec(command, workdir?, confirmed?)` — 执行 shell 命令，返回 stdout+stderr
- `read_file(path)` — 读取文件内容
- `write_file(path, content)` — 写入文件
- `list_files(path?, recursive?, max_depth?)` — 浏览目录结构，先探索再读取
- `search(query, max_results?)` — 通过 SearXNG 搜索网页
- `fetch_url(url, max_chars?)` — 抓取网页/API 返回文本（HTML 自动转纯文本）

---

### Skill: memory

记录与检索，关键词：记住、记一下、备忘、笔记、记录、别忘了、之前说过 等

- `note(content, category?)` — 追加到今日日志（`memory/YYYY-MM-DD.md`），轻量快速；category 可选如 idea/todo/log
- `remember(content, section?)` — 写入 `MEMORY.md` 长期保留；section 指定章节（如 '用户偏好'/'经验教训'）
- `recall(query, limit?)` — 全文搜索 MEMORY.md + 日志，关键词空格分隔为 AND 逻辑

---

### Skill: personal

个人信息管理，关键词：联系人、日历、日程、生日、通讯录、约、会议、安排 等

- `schedule(action, datetime?, title?, note?, date_filter?, id?)` — 本地日程管理（唯一日程工具）。action: add/list/delete。datetime 格式 'YYYY-MM-DD HH:MM'。list 支持 date_filter 过滤单天或日期范围。新增事项若与已有日程时间重叠（±30 分钟内），返回结果会包含 ⚠️ 冲突提示。
- `contacts(action, query?, contact?, days?)` — 读写本地通讯录（contacts.yml）。action: list/show/add/update/birthdays

---

### Skill: notification

通知与提醒，关键词：通知、提醒、推送、告知、消息、定时、之后 等

- `notify(message, urgent?)` — 即时推送通知给主人（via Telegram + Web Push，urgent=true 可跳过静默时段）
- `remind(message, delay?, cron?, label?, holiday?, lunar?, advance_days?, time?)` — 设置提醒。
  - 一次性：用 `delay`，支持相对时间（'5m'/'2h'/'1d'）或绝对时间（'YYYY-MM-DD HH:MM' CST）
  - **周期性（每天/每周/每月等）：必须用 `cron`**，5 字段 cron 表达式（CST），例：
    - `'0 9 * * 1-5'` — 工作日每天 09:00
    - `'0 10 * * 0'` — 每周日 10:00
    - `'0 8 * * *'` — 每天 08:00
  - 含"每天/每周/每月/每年/每个X"等周期语义时，**始终用 cron，不得用 delay**
  - **农历节日**：用 `holiday` 参数，值为节日名称。支持：春节、元宵节、端午节、七夕节、中秋节、重阳节、腊八节
    - 示例：`holiday="中秋节", advance_days=1, time="09:00"` — 中秋节前一天 09:00 提醒
  - **自定义农历日期**（如生日）：用 `lunar` 参数，格式 'M-D'（农历月-日）
    - 示例：`lunar="3-8", advance_days=1, message="妈妈生日"` — 农历三月初八前一天提醒
  - **公历固定年度日期**（如情人节、白色情人节）：用 `solar` 参数，格式 'M-D'（公历月-日）
    - 示例：`solar="2-14", advance_days=3, time="21:00"` — 每年2月14日情人节提前3天晚9点提醒
    - 示例：`solar="3-14", advance_days=3, time="21:00"` — 每年3月14日白色情人节提前3天晚9点提醒
  - `advance_days`：提前天数（用于 holiday/lunar/solar），默认 0（当天）
  - `time`：触发时间 'HH:MM'（CST），用于 holiday/lunar/solar，默认 '09:00'
  - 若目标时间与已有日程存在冲突（±60 分钟内），工具会在返回结果中附加 ⚠️ 冲突提示，操作不阻塞。

---

### Skill: task

任务管理，关键词：任务、计划、项目、创建任务、子任务、进度、状态、待办 等

- `create_task(title, description?, parent_id?)` — 创建根任务或子任务
- `decompose_task(task_id, subtasks)` — 将任务拆解为子任务列表
- `complete_task(task_id, result?)` — 标记任务完成
- `fail_task(task_id, reason?)` — 标记任务失败
- `get_task_status(task_id?)` — 查询任务及子任务状态
- `update_task(task_id, ...)` — 更新任务属性（标题、优先级等）

---

### Skill: coding

编码任务委派，关键词：写代码、实现、开发、重构、debug、修复、代码、编程 等

- `code_agent(prompt, workdir?, model?)` — 通过 Claude Code CLI 执行编码任务（spawn `claude-internal -p`，经 OpenRouter proxy 调用 Claude 模型）
  - prompt：完整的任务描述，包含做什么、在哪里、验收标准
  - workdir：工作目录（默认项目根）
  - model：sonnet（默认）/ haiku / opus
  - 单次调用预算上限 $0.50，超时 5 分钟
  - Claude 有独立 context，直接读写文件和执行命令

---

## Shell 命令权限（通过 exec 调用）

### 允许

- `git add / commit / push / pull / status / diff / log`
- `ls / wc`
- `.venv/bin/python` / `.venv/bin/pip`

#### 定时与通知

- `./implementation/ops/scripts/timer.sh <秒数> "消息"` — 延时通知，到期后自动投递
- `./implementation/ops/scripts/notify.sh "消息"` — Telegram 即时通知
- `./implementation/ops/scripts/heartbeat.sh` — 定期巡检
- `./check.sh` / `./check.sh --json` — 项目状态诊断

#### 代码与开发

- `gh` — GitHub CLI
- `cursor` — Cursor CLI
- `.venv/bin/playwright` — Web 自动化
- `peekaboo` — macOS GUI 自动化

#### 科研与外部集成

- `himalaya` — 邮件
- `khal` / `vdirsyncer` — 日历
- `rclone` — 云存储
- `mcporter` — MCP 能力接入
- `.venv/bin/paperscout` / `.venv/bin/papis`

#### 数据与资产

- `implementation/data/contacts.yml` — 通讯录
- `implementation/data/gifts.yml` — 人情往来
- `implementation/assets/persona/MEMORY.md` — 长期记忆
- `implementation/assets/persona/memory/*.md` — 每日日志
- `implementation/STATUS.md` — 当前状态

### 禁止

- 直接使用危险删除命令
- 未经确认安装系统级软件包
- 访问仓库之外的敏感文件
