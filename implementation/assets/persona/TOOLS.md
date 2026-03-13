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

- `schedule(action, datetime?, title?, note?, date_filter?, id?)` — 本地日程管理（唯一日程工具）。action: add/list/delete。datetime 格式 'YYYY-MM-DD HH:MM'。list 支持 date_filter 过滤单天或日期范围。
- `contacts(action, query?, contact?, days?)` — 读写本地通讯录（contacts.yml）。action: list/show/add/update/birthdays

---

### Skill: notification

通知与提醒，关键词：通知、提醒、推送、告知、消息、定时、之后 等

- `notify(message, urgent?)` — 即时推送通知给主人（via Telegram + Web Push，urgent=true 可跳过静默时段）
- `remind(delay, message)` — 设置提醒。delay 支持相对时间（'5m'/'2h'/'1d'）或绝对时间（'YYYY-MM-DD HH:MM' CST），到时自动推送通知

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
